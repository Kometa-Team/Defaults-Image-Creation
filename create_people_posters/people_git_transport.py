"""Explicitly approved native Git transport, retaining individual ledger receipts.

No live approval is embedded. REST publication and README authority are unchanged.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time

from people_github import GitHubClient, GitHubError, repository_mapping
from people_remote_inventory import blob_sha, path_key
from people_workspaces import reject_links

SOURCE_MEMBERS = ("people_git_transport.py", "people_publication_state.py", "publish_people_github.py")


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def need(value):
    if not value:
        raise ValueError("Native Git approval, artifact or checkpoint integrity mismatch")


def failure(category, retryable=False, ambiguous=False):
    return GitHubClient.reliability_error(category, 0, retryable, ambiguous)


ASKPASS = '''import os,sys
url=os.environ["PEOPLE_GIT_URL"]
prompt=sys.argv[1] if len(sys.argv)==2 else ""
if prompt in ("Username for '"+url+"': ","Username for 'https://github.com': "):
    sys.stdout.write("x-access-token\\n")
elif prompt in ("Password for '"+url.replace("https://","https://x-access-token@")+"': ","Password for 'https://x-access-token@github.com': "):
    sys.stdout.write(os.environ["PEOPLE_GIT_AUTH"]+"\\n")
else:sys.exit(1)
'''
PUSH_GUARD = '''import os,sys
if len(sys.argv)!=3 or sys.argv[1]!="origin" or sys.argv[2]!=os.environ["PEOPLE_GIT_URL"]:sys.exit(1)
rows=sys.stdin.read().splitlines()
if len(rows)!=1:sys.exit(1)
parts=rows[0].split()
if len(parts)!=4 or parts[1]!=os.environ["PEOPLE_GIT_TIP"] or parts[2]!="refs/heads/"+os.environ["PEOPLE_GIT_BRANCH"] or parts[3]!=os.environ["PEOPLE_GIT_PARENT"]:sys.exit(1)
'''


class GitTransport:
    """Isolated SHA-1 bare repository; no checkout, filters, stored PAT or raw errors."""
    def __init__(self, workspace, repo, branch, token, *, local_remote=None, timeout=7200):
        need(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo))
        need(branch == "master" and type(timeout) is int and 60 <= timeout <= 86400)
        self.root = Path(workspace).absolute();reject_links(self.root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.repo, self.branch, self.timeout = repo, branch, timeout
        self.local = local_remote is not None
        self.url = str(Path(local_remote).absolute()) if self.local else "https://github.com/"+repo+".git"
        if self.local:
            reject_links(self.url);need((Path(self.url)/"HEAD").is_file())
        self._auth = token
        from create_people_posters.people_diagnostics import register_secret
        register_secret(token)
        self.directory = self.root/"objects.git"
        self.hooks = self.root/"hooks";reject_links(self.hooks);self.hooks.mkdir(exist_ok=True)
        self._helper_bytes = {self.root/"askpass.py":ASKPASS.encode(),self.root/"guard.py":PUSH_GUARD.encode(),
            self.root/"askpass.sh":b'#!/bin/sh\nexec "$PEOPLE_GIT_PYTHON" "$PEOPLE_GIT_HELPERS/askpass.py" "$@"\n',
            self.hooks/"pre-push":b'#!/bin/sh\nexec "$PEOPLE_GIT_PYTHON" "$PEOPLE_GIT_HELPERS/guard.py" "$@"\n'}
        for path, data in self._helper_bytes.items():self._helper(path,data)
        # Git silently ignores hooks on a noexec filesystem. Never permit that.
        need(os.access(self.hooks/"pre-push", os.X_OK))
        reject_links(self.directory)
        if not self.directory.exists():
            self._run(["init", "--bare", "--object-format=sha1", str(self.directory)], bare=False)
            self.git("config", "remote.origin.url", self.url)
            if not self.local:
                self.git("config", "remote.origin.promisor", "true")
                self.git("config", "remote.origin.partialclonefilter", "blob:none")
        for name in ("config","HEAD","objects","objects/info","objects/pack","refs","hooks","shallow","info/grafts"):
            reject_links(self.directory/name)
        need(not (self.directory/"objects/info/alternates").exists() and not (self.directory/"info/grafts").exists())
        # Refuse contaminated local configuration, helpers and promisor endpoints.
        allowed = {"core.repositoryformatversion", "core.filemode", "core.bare", "core.ignorecase", "core.symlinks", "remote.origin.url",
                   "remote.origin.promisor", "remote.origin.partialclonefilter"}
        for item in self.git("config", "--local", "--null", "--list").split(b"\0"):
            if not item:continue
            key, value = item.decode().split("\n", 1)
            need(key in allowed)
            if key == "remote.origin.url":need(value == self.url)
            if key == "core.bare":need(value == "true")
            if key == "core.repositoryformatversion":need(value == "0")
            if key == "core.ignorecase":need(value in {"true", "false"})  # Every command overrides this for raw index paths.
            if key == "core.symlinks":need(value == "false")  # Git init may record unavailable symlink support.
            if key == "remote.origin.promisor":need(not self.local and value == "true")
            if key == "remote.origin.partialclonefilter":need(not self.local and value == "blob:none")

    @staticmethod
    def _helper(path, data):
        reject_links(path)
        if path.exists():need(path.is_file() and path.read_bytes() == data)
        else:
            with path.open("xb") as out:out.write(data);out.flush();os.fsync(out.fileno())
            path.chmod(0o700)

    def environment(self, *, network=False, index=None, parent=None, tip=None):
        # An allowlist excludes inherited traces, injected Git config and credentials.
        env = {k:os.environ[k] for k in ("PATH", "SystemRoot", "WINDIR", "TEMP", "TMP", "LANG", "LC_ALL") if k in os.environ}
        env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT="0",
                   GIT_NO_LAZY_FETCH="1", GIT_NO_REPLACE_OBJECTS="1", GIT_ASKPASS=str(self.root/"askpass.sh"),
                   PEOPLE_GIT_PYTHON=sys.executable, PEOPLE_GIT_HELPERS=str(self.root),
                   PEOPLE_GIT_URL=self.url, PEOPLE_GIT_BRANCH=self.branch)
        if index:env["GIT_INDEX_FILE"] = str(index)
        if parent:env["PEOPLE_GIT_PARENT"] = parent
        if tip:env["PEOPLE_GIT_TIP"] = tip
        if network and not self.local:env["PEOPLE_GIT_AUTH"] = self._auth
        return env

    @staticmethod
    def _stop(process):
        if process.poll() is None:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                try:os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:pass
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                if os.name != "nt":
                    try:os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:pass
                process.kill();process.wait()

    def _run(self, args, *, data=None, infile=None, outfile=None, bare=True, network=False, write=False, **env_args):
        if self.directory.exists() and (network or args[0] in {"hash-object","write-tree","read-tree","update-index","config"}):
            for name in ("config","HEAD","objects","objects/info","objects/pack","refs","hooks","shallow"):
                reject_links(self.directory/name)
            need(not (self.directory/"objects/info/alternates").exists() and not (self.directory/"info/grafts").exists())
            if args[0] in {"fetch","write-tree"} and (self.directory/"objects").is_dir():
                for child in (self.directory/"objects").iterdir():reject_links(child)
        if network:
            need(set(self.hooks.iterdir()) == {self.hooks/"pre-push"})
            for path, expected in self._helper_bytes.items():
                reject_links(path);need(path.is_file() and path.read_bytes() == expected)
            need(os.access(self.hooks/"pre-push",os.X_OK))
        command = ["git"]
        if bare:command += ["--git-dir", str(self.directory)]
        command += ["-c", "core.hooksPath="+str(self.hooks), "-c", "core.longpaths=true",
            "-c", "core.ignoreCase=false", "-c", "core.precomposeUnicode=false", "-c", "credential.helper=",
            "-c", "http.followRedirects=false", "-c", "http.extraHeader=", "-c", "protocol.allow=never",
            "-c", "protocol."+("file" if self.local else "https")+".allow="+("always" if network else "never"),
            "-c", "pack.window=0", "-c", "pack.threads=1", "-c", "pack.compression=1",
            "-c", "pack.useBitmaps=false", "-c", "push.followTags=false", "-c", "gc.auto=0",
            "-c", "maintenance.auto=false", *args]
        # Git/server stderr may contain secrets. Drain a bounded RAM buffer,
        # never a file, trace, exception message or persisted diagnostic.
        errors = bytearray()
        options = dict(start_new_session=True) if os.name != "nt" else dict(creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        process = subprocess.Popen(command, stdin=infile if infile is not None else subprocess.PIPE,
            stdout=outfile if outfile is not None else subprocess.PIPE, stderr=subprocess.PIPE,
            env=self.environment(network=network, **env_args), **options)
        stream = process.stderr
        def drain():
            try:
                while True:
                    chunk = stream.read(8192)
                    if not chunk:break
                    errors.extend(chunk[:max(0,65536-len(errors))])
            finally:stream.close()
        reader = threading.Thread(target=drain,daemon=True);reader.start()
        process.stderr = None  # communicate must not race the bounded drain.
        try:out, _ = process.communicate(data, timeout=self.timeout)
        except (KeyboardInterrupt, BaseException) as error:
            self._stop(process)
            reader.join()
            if isinstance(error, subprocess.TimeoutExpired):
                raise failure("git_timeout", True, write) from None
            raise
        reader.join()
        if process.returncode:
            raw = b"\n".join(line for line in bytes(errors).lower().splitlines() if line.startswith((b"fatal:",b"error:")))
            transient = bool(re.search(rb"curl (?:6|7|18|28|35|52|55|56)\b", raw) or any(t in raw for t in
                (b"could not resolve host", b"connection timed out", b"connection reset")))
            status = re.search(rb"(?:http|returned error:)\s*(\d{3})\b",raw)
            status = int(status.group(1)) if status else 0
            if not 100 <= status <= 599:status = 0
            if status:transient = status in {429,500,502,503,504}
            category = "git_validation" if status == 422 else "git_network" if transient else "git_rejected"
            # Never include raw Git output, remote messages, command or environment.
            error = failure(category, transient, write);error.status = status
            raise error from None
        need(out is None or len(out) <= 64*1024**2)
        return out or b""

    def git(self, *args, **kwargs):return self._run(list(args), **kwargs)

    def remote_head(self):
        raw = self.git("ls-remote", "--exit-code", "origin", "refs/heads/"+self.branch, network=True)
        rows = raw.decode().splitlines();need(len(rows) == 1)
        sha, ref = rows[0].split();need(re.fullmatch("[0-9a-f]{40}", sha) and ref == "refs/heads/"+self.branch)
        return sha

    def fetch(self, expected):
        need(self.remote_head() == expected)
        args = ["fetch", "--no-tags"]
        if not self.local:args += ["--filter=blob:none", "--depth=1"]
        self.git(*args, "origin", "refs/heads/"+self.branch, network=True)
        need(self.git("rev-parse", "FETCH_HEAD").strip().decode() == expected)
        need(self.remote_head() == expected)

    def tree(self, commit):
        result = {}
        for record in self.git("ls-tree", "-rz", commit).split(b"\0"):
            if record:
                meta, path = record.split(b"\t", 1);mode, kind, sha = meta.decode().split()
                name = path.decode("utf8");need(name not in result)
                result[name] = dict(mode=mode, type=kind, sha=sha)
        return result

    def blob(self, row):
        need(re.fullmatch('[0-9a-f]{40}',row['blob']))
        reject_links(self.directory/'objects'/row['blob'][:2]/row['blob'][2:])
        verified = set()
        for key, expected in (("prepared", "published_hash"), ("source", "source_hash")):
            path = Path(row[key]);reject_links(path)
            if key == "source" and not path.exists():continue
            identity = (str(path.absolute()),row[expected])
            if identity in verified:continue
            need(path.is_file() and path.stat().st_size < 100*1024**2)
            h = hashlib.sha256()
            with path.open("rb") as src:
                for chunk in iter(lambda:src.read(1024*1024), b""):h.update(chunk)
            need(h.hexdigest() == row[expected])
            verified.add(identity)
        with Path(row["prepared"]).open("rb") as src:
            sha = self.git("hash-object", "-w", "--stdin", infile=src).strip().decode()
        need(sha == row["blob"])
        return sha

    def prepare_window(self, publisher, batch, window, rows, acknowledge):
        baseline = self.tree(window["parent"]);keys = {}
        for path in baseline:
            key = path_key(path);need(key not in keys);keys[key] = path
        updates = []
        for row in rows:
            path = row["path"];parts = path.split("/")
            need(len(parts) == 3 and parts[1] == "Images" and parts[-1].endswith(".jpg")
                 and all(p not in {"", ".", ".."} for p in parts) and "\\" not in path
                 and all(ord(c) >= 32 and c != ":" for c in path))
            need(path_key(path) not in keys or keys[path_key(path)] == path)
            current = baseline.get(path)
            need(current is None or current["type"] == "blob" and current["mode"] == "100644")
            for n in range(1, len(parts)):need("/".join(parts[:n]) not in baseline)
            old = publisher.ledger.db.execute("SELECT sha FROM baselines WHERE batch=? AND repo=? AND path=?",
                (batch, self.repo, path)).fetchone();need(old is not None)
            if current and current["sha"] == row["blob"]:continue
            need((current["sha"] if current else None) == (old[0] or None))
            acknowledged = publisher.ledger.db.execute("SELECT object_sha FROM publication_git_members WHERE batch=? AND repo=? AND number=? AND path=?",
                (batch,self.repo,window["number"],path)).fetchone()[0]
            if acknowledged:
                need(acknowledged == row["blob"])
                self.git("cat-file", "-e", row["blob"]+"^{blob}")
            else:
                self.blob(row);acknowledge(path,row["blob"])
            updates.append(dict(path=path,mode="100644",type="blob",sha=row["blob"]))
        index = self.root/"index";reject_links(index)
        # An interrupted update-index cannot own a live lock after the child exits.
        # Preserve stale lock evidence rather than deleting it; use a fresh index.
        index = self.root/("index-"+os.urandom(12).hex())
        self.git("read-tree",window["parent"],index=index)
        if updates:
            raw = b"".join(b"100644 "+e["sha"].encode()+b"\t"+e["path"].encode("utf8")+b"\0" for e in updates)
            self.git("update-index","-z","--index-info",data=raw,index=index)
            found=self.git("cat-file","--batch-check",data=b"".join(e["sha"].encode()+b"\n" for e in updates)).splitlines()
            need(len(found)==len(updates))
            for entry,line in zip(updates,found):
                fields=line.split();need(len(fields)==3 and fields[0].decode()==entry["sha"] and fields[1]==b"blob")
        # blob:none intentionally omits inherited JPEGs. All changed blobs were
        # checked above; every other index entry comes from the verified parent.
        # Full tree equality and strict pack construction are checked before push.
        tree = self.git("write-tree","--missing-ok",index=index).strip().decode();settings = publisher.reliable_settings()
        person = dict(name=settings["author"],email=settings["email"],date=window["date"])
        payload = dict(tree=tree,parents=[window["parent"]],author=person,committer=person,
            message=f"chore: sync posters - batch {batch} git window {window['number']} [skip readme]\n")
        epoch = int(datetime.fromisoformat(window["date"].replace("Z","+00:00")).timestamp())
        lines = ["tree "+tree,"parent "+window["parent"]]+[
            f"{role} {person['name']} <{person['email']}> {epoch} +0000" for role in ("author","committer")]
        raw = ("\n".join(lines)+"\n\n"+payload["message"]).encode()
        identity=publisher.commit_identity(payload)
        reject_links(self.directory/'objects'/identity[:2]/identity[2:])
        commit = self.git("hash-object","-w","-t","commit","--stdin",data=raw).strip().decode() if updates else window["parent"]
        need(not updates or commit == publisher.commit_identity(payload))
        return dict(tip=commit,tree=tree,commit_payload=payload,changed=len(updates))

    def pack_size(self, tip, parent):
        # A full non-thin, no-delta pack; no pack-size assumption from JPEG bytes.
        with tempfile.TemporaryFile(dir=self.root) as pack:
            self.git("pack-objects", "--revs", "--stdout", "--window=0", "--threads=1",
                "--no-reuse-delta", "--no-reuse-object", "--compression=1",
                data=(tip+"\n^"+parent+"\n").encode(), outfile=pack)
            return pack.tell()

    def push(self, parent, tip):
        need(os.access(self.hooks/"pre-push", os.X_OK))
        need(self.remote_head() == parent)
        self.git("push", "--porcelain", "--no-follow-tags", "--no-thin", "origin",
            tip+":refs/heads/"+self.branch, network=True, write=True, parent=parent, tip=tip)


class NativePublication:
    """One commit per durable size-bounded window; individual poster receipts."""
    def __init__(self, publisher, *, transport=None, contract=None, approval=None):
        self.p=publisher;self.ledger=publisher.ledger;self.transport=transport
        if contract is None:
            path=Path(os.environ.get("PEOPLE_GIT_APPROVAL_FILE",""));reject_links(path)
            raw=path.read_bytes();approval=os.environ.get("PEOPLE_GIT_APPROVAL_SHA256","")
            need(hashlib.sha256(raw).hexdigest()==approval);contract=json.loads(raw)
        self.a,self.approval=contract,approval

    def validate(self,batch):
        a=self.a;p=self.p
        expected={"version","backend","batch","repo","branch","origin_head","origin_review_sha256",
            "reconciliation_sha256","rows_binding","initial_head","initial_published_paths","published_rows_sha256",
            "units_sha256","settings_sha256","source_bindings","target_source_bytes","max_pack_bytes",
            "max_posters","git_timeout","previous_approval"}
        need(set(a)==expected and a["version"]==2 and a["backend"]=="git-pack-v2")
        need(re.fullmatch("[0-9a-f]{64}",self.approval or ""))
        need(a["batch"]==batch and a["branch"]==p.branch=="master"
             and set(p.repositories.values())=={a["repo"]} and len(p.repositories)==1)
        need(all(repository_mapping().get(style)==repo for style,repo in p.repositories.items()))
        for key in ("target_source_bytes","max_pack_bytes","max_posters","git_timeout"):need(type(a[key]) is int)
        need(1<=a["target_source_bytes"]<=1_500_000_000 and 1024<=a["max_pack_bytes"]<=1_850_000_000)
        need(0<=a["max_posters"]<=100000 and 60<=a["git_timeout"]<=86400)
        need(set(a["source_bindings"])==set(SOURCE_MEMBERS))
        for name,sha in a["source_bindings"].items():need(hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()==sha)
        reconciliation=self.ledger.state.parent/"reconciliation.json";reject_links(reconciliation)
        raw=reconciliation.read_bytes();need(hashlib.sha256(raw).hexdigest()==a["reconciliation_sha256"])
        plan=json.loads(raw)["styles"][next(iter(p.repositories))]
        need(plan["unit"]==batch and not plan["filename_case_conflicts"])
        rows=self.ledger.rows(batch,a["repo"]);need(rows and self.ledger.unit_binding(rows)==a["rows_binding"]==plan["entries_sha256"])
        need(all(r["repo"]==a["repo"] and r["style"]==next(iter(p.repositories)) and r["branch"]==a["branch"] for r in rows))
        need(len({path_key(r["path"]) for r in rows})==len(rows))
        bases={r[0]:r[1] or None for r in self.ledger.db.execute("SELECT path,sha FROM baselines WHERE batch=? AND repo=?",(batch,a["repo"]))}
        need(bases==plan["baselines"])
        control=self.ledger.db.execute("SELECT * FROM publication_controls WHERE batch=? AND repo=?",(batch,a["repo"])).fetchone()
        need(control and control["origin_head"]==a["origin_head"] and hashlib.sha256(control["settings"].encode()).hexdigest()==a["settings_sha256"])
        need(canonical(p.reliable_settings())==canonical(json.loads(control["settings"])))
        need(os.getenv("PEOPLE_PUBLICATION_EXPECTED_HEAD","")==a["origin_head"]
             and os.getenv("PEOPLE_PUBLICATION_LEGACY_REVIEW_SHA256","")==a["origin_review_sha256"])
        units=[dict(r) for r in self.ledger.db.execute("SELECT * FROM publication_units WHERE batch=? AND repo=? AND unit!='readme' ORDER BY unit",(batch,a["repo"]))]
        need(digest(units)==a["units_sha256"])
        contracts=[(sha,json.loads(raw)) for sha,raw in self.ledger.db.execute(
            "SELECT approval,contract FROM publication_git_controls WHERE batch=? AND repo=? ORDER BY rowid",(batch,a["repo"]))]
        previous=""
        for sha,old in contracts:
            need(old["previous_approval"]==previous);previous=sha
            need(old["rows_binding"]==a["rows_binding"] and old["origin_review_sha256"]==a["origin_review_sha256"]
                 and old["reconciliation_sha256"]==a["reconciliation_sha256"] and old["settings_sha256"]==a["settings_sha256"])
            paths=set(old["initial_published_paths"])
            need(len(paths)==len(old["initial_published_paths"]) and digest([r for r in rows if r["path"] in paths])==old["published_rows_sha256"])
        paths=set(a["initial_published_paths"])
        need(len(paths)==len(a["initial_published_paths"]) and digest([r for r in rows if r["path"] in paths])==a["published_rows_sha256"])
        if contracts and contracts[-1][0]==self.approval:need(canonical(contracts[-1][1])==canonical(a))
        else:
            need(a["previous_approval"]==previous and control["head"]==a["initial_head"])
            need({r["path"] for r in rows if r["status"]=="published"}==paths)
            need(not any(json.loads(r[0])["stage"]!="completed" for r in self.ledger.db.execute(
                "SELECT data FROM publication_git_windows WHERE batch=? AND repo=?",(batch,a["repo"]))))
            head=control["origin_head"]
            for unit in sorted(units,key=lambda u:int(u["unit"])):
                data=json.loads(unit["data"]);number=int(unit["unit"]);group=rows[number*50:(number+1)*50]
                need(unit["binding"]==self.ledger.unit_binding(group) and data["parent"]==head)
                members=[r[0] for r in self.ledger.db.execute("SELECT path FROM publication_unit_members WHERE batch=? AND repo=? AND unit=? ORDER BY path",(batch,a["repo"],unit["unit"]))]
                need(members==[r["path"] for r in group])
                if data["status"]=="completed":
                    need(data["stage"]=="published" and data["intent"] is None)
                    need(not data["updates"] or p.commit_identity(data["commit_payload"])==data["commit"])
                    need(all(r["status"]=="published" and r["commit_sha"]==data["commit"] for r in group));head=data["commit"]
                else:need(data["stage"]=="preparing" and not data["done"] and not data["intent"] and not data["attempts"])
            if not contracts:need(head==control["head"])
            with self.ledger.db:self.ledger.db.execute("INSERT INTO publication_git_controls VALUES (?,?,?,?)",(batch,a["repo"],self.approval,canonical(a).decode()))
        windows=[(n,json.loads(raw)) for n,raw in self.ledger.db.execute("SELECT number,data FROM publication_git_windows WHERE batch=? AND repo=? ORDER BY number",(batch,a["repo"]))]
        head=(contracts[0][1] if contracts else a)["initial_head"];active=0
        for n,w in windows:
            need(w["version"]==2 and w["number"]==n and w["stage"] in {"preparing","prepared","push_intent","pushed","remote_verified","completed"})
            need(w["parent"]==head and w["approval"] in {self.approval}|{sha for sha,c in contracts})
            members=self.ledger.git_members(batch,a["repo"],n);need(self.ledger.unit_binding(members)==w["binding"])
            if w["stage"]!="preparing":self.verify_intent(w)
            if w["stage"]=="completed":
                need(active==0 and all(r["status"]=="published" and r["commit_sha"]==w["tip"] for r in members));head=w["tip"]
            else:active+=1;need(w["approval"]==self.approval)
        need(active<=1 and head==control["head"])
        return rows,dict(control),windows

    def _save(self,batch,window,stage=None):
        if stage:window["stage"]=stage
        self.ledger.git_window(batch,self.a["repo"],window["number"],window)
        self.p.checkpoint_hook("git_"+window["stage"])

    def publish(self,batch):
        p=self.p;a=self.a
        with self.ledger.publication_lock():
            self.ledger.reliability_schema();self.ledger.git_schema()
            rows,control,windows=self.validate(batch)
            if getattr(p.client,"sandbox",None):p.validate()
            t=self.transport or GitTransport(self.ledger.state/"native-git-v2",a["repo"],a["branch"],p.client.token,timeout=a["git_timeout"])
            self.transport=t
            while True:
                rows=self.ledger.rows(batch,a["repo"])
                window=next((w for n,w in windows if w["stage"]!="completed"),None)
                if window is None:
                    if all(r["status"]=="published" for r in rows):break
                    consumed=sum(len(self.ledger.git_members(batch,a["repo"],n)) for n,w in windows if w["approval"]==self.approval and w["stage"]=="completed")
                    if a["max_posters"] and consumed>=a["max_posters"]:
                        current=self.ledger.db.execute("SELECT head FROM publication_controls WHERE batch=? AND repo=?",(batch,a["repo"])).fetchone()[0]
                        need(t.remote_head()==current)
                        return dict(canary_complete=True,head=current)
                    number=windows[-1][0]+1 if windows else 0
                    ratio=max(1.02,max((w["pack_bytes"]/max(1,w["source_bytes"]) for n,w in windows),default=1.02))*1.08
                    limit=min(a["target_source_bytes"],max(1,int((a["max_pack_bytes"]-4096)/ratio)))
                    selected=[];total=0
                    for row in rows:
                        if row["status"]=="published":continue
                        need(row["status"]!="conflict")
                        path=Path(row["prepared"]);reject_links(path);need(path.is_file() and path.stat().st_size<100*1024**2)
                        size=path.stat().st_size
                        if selected and (total+size>limit or a["max_posters"] and consumed+len(selected)>=a["max_posters"]):break
                        need(size<=a["target_source_bytes"])
                        selected.append(row);total+=size
                    need(selected)
                    head=self.ledger.db.execute("SELECT head FROM publication_controls WHERE batch=? AND repo=?",(batch,a["repo"])).fetchone()[0]
                    window=dict(version=2,number=number,approval=self.approval,parent=head,tip=head,tree="",commit_payload={},changed=0,
                        binding=self.ledger.unit_binding(selected),date=datetime.fromtimestamp(int(p.clock()),timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        stage="preparing",status="pending",source_bytes=total,pack_bytes=0,attempts=0,first_failure=0,not_before=0,error={},write_error=None)
                    if windows:window['not_before']=max(0,windows[-1][1].get('finished_at',0)+60)
                    with self.ledger.db:
                        self.ledger.db.executemany("INSERT INTO publication_git_members VALUES (?,?,?,?,?,?)",[(batch,a["repo"],number,i,r["path"],"") for i,r in enumerate(selected)])
                        # Journal and membership are inserted atomically before any Git operation.
                        self.ledger.db.execute("INSERT INTO publication_git_windows VALUES (?,?,?,?)",(batch,a["repo"],number,canonical(window).decode()))
                    windows.append((number,window));p.checkpoint_hook("git_preparing")
                need(window["approval"]==self.approval and window["status"] not in {"blocked","permanently_failed"})
                try:
                    if window["first_failure"] and p.clock()-window["first_failure"]>p.reliable_settings()["max_elapsed"]:raise failure("retry_budget_exhausted")
                    while p.clock()<window["not_before"]:p.sleep(min(30,window["not_before"]-p.clock()))
                    selected=self.ledger.git_members(batch,a["repo"],window["number"])
                    need(self.ledger.unit_binding(selected)==window["binding"])
                    if window["stage"]=="preparing":
                        t.fetch(window["parent"])
                        baseline=t.tree(window["parent"])
                        for row in rows:
                            if row["status"]=="published":
                                need(baseline.get(row["path"])==dict(sha=row["blob"],mode="100644",type="blob"))
                        def acknowledge(path,sha):
                            with self.ledger.db:self.ledger.db.execute("UPDATE publication_git_members SET object_sha=? WHERE batch=? AND repo=? AND number=? AND path=?",(sha,batch,a["repo"],window["number"],path))
                            p.checkpoint_hook("git_object_prepared")
                        while True:
                            window.update(t.prepare_window(p,batch,window,selected,acknowledge))
                            window["pack_bytes"]=t.pack_size(window["tip"],window["parent"])
                            if window["pack_bytes"]<=a["max_pack_bytes"]:break
                            need(len(selected)>1)
                            keep=max(1,int(len(selected)*a["max_pack_bytes"]/window["pack_bytes"]*0.90));keep=min(len(selected)-1,keep)
                            selected=selected[:keep]
                            window.update(binding=self.ledger.unit_binding(selected),source_bytes=sum(Path(r["prepared"]).stat().st_size for r in selected))
                            with self.ledger.db:
                                self.ledger.db.execute("DELETE FROM publication_git_members WHERE batch=? AND repo=? AND number=? AND position>=?",(batch,a["repo"],window["number"],keep))
                                self.ledger.db.execute("UPDATE publication_git_windows SET data=? WHERE batch=? AND repo=? AND number=?",(canonical(window).decode(),batch,a["repo"],window["number"]))
                            p.checkpoint_hook("git_window_split")
                        self._save(batch,window,"prepared")
                    self.verify_local(window,selected)
                    if window["stage"] in {"prepared","push_intent"}:
                        self._save(batch,window,"push_intent")
                        head=t.remote_head();need(head in {window["parent"],window["tip"]})
                        if head!=window["tip"]:
                            if window["write_error"]:need(window["write_error"]["retryable"])
                            t.push(window["parent"],window["tip"]);p.checkpoint_hook("git_push_ack")
                        self._save(batch,window,"pushed")
                    t.fetch(window["tip"])
                    need(p.client.head(a["repo"],a["branch"])==(window["tip"],window["tree"]))
                    self.verify_local(window,selected);window.setdefault('finished_at',p.clock());self._save(batch,window,"remote_verified")
                    self.ledger.git_complete_window(batch,a["repo"],window["number"],window)
                    window.update(self.ledger.git_window(batch,a["repo"],window["number"]))
                    if window["changed"]:self.ledger.readme(batch,a["repo"],"pending")
                    p.checkpoint_hook("git_completed")
                    print(json.dumps(dict(event="git_window_completed",window=window["number"],posters=len(selected),pack_bytes=window["pack_bytes"],**self.ledger.reliability_progress(batch,a["repo"]))),flush=True)
                    if not all(r["status"]=="published" for r in self.ledger.rows(batch,a["repo"])):p.sleep(60)
                except GitHubError as error:
                    if window["stage"]=="push_intent" and getattr(error,"ambiguous",False):
                        window["write_error"]=dict(category=getattr(error,"category","unclassified"),retryable=bool(getattr(error,"retryable",False)))
                        self._save(batch,window)
                    if window["stage"] in {"push_intent","pushed","remote_verified"}:
                        try:head=t.remote_head()
                        except GitHubError as read_error:error=read_error;head=None
                        if head is not None:
                            if head not in {window["parent"],window["tip"]}:
                                error=failure("remote_conflict")
                            elif head==window["tip"] and window["stage"]=="push_intent":
                                self._save(batch,window,"pushed");continue
                    if not getattr(error,"retryable",False):
                        window.update(status="blocked",error=dict(category=getattr(error,"category","unclassified")))
                        self._save(batch,window);raise error
                    p._schedule_retry(batch,a["repo"],window["number"],window,error,p.reliable_settings(),persist=lambda value:self._save(batch,value))
                except (ValueError,OSError):
                    window.update(status="blocked",error=dict(category="integrity_or_storage"));self._save(batch,window);raise
            # Include audit and pre-helper GET failures in the same durable retry
            # budget. The existing helper still owns dispatch/correlation/indexes.
            while True:
                head=self.ledger.db.execute("SELECT head FROM publication_controls WHERE batch=? AND repo=?",(batch,a["repo"])).fetchone()[0]
                state=self.ledger.unit(batch,a["repo"],"readme",[],dict(stage="readme",parent=head,commit=head))
                need(state["status"]!="blocked")
                while p.clock()<state["not_before"]:p.sleep(min(30,state["not_before"]-p.clock()))
                try:
                    self.audit_artwork(batch);p.publish_readme_reliable(batch,p.reliable_settings());break
                except GitHubError as error:
                    state=self.ledger.unit(batch,a["repo"],"readme",[])
                    if not getattr(error,"retryable",False):
                        state.update(status="blocked",error=dict(category=getattr(error,"category","unclassified")))
                        p._save(batch,a["repo"],"readme",state);raise
                    p._schedule_retry(batch,a["repo"],"readme",state,error,p.reliable_settings())
            return dict(artwork_verified=True,verified=self.ledger.verified(batch))

    def verify_intent(self,window):
        need(re.fullmatch('[0-9a-f]{40}',window['parent']) and re.fullmatch('[0-9a-f]{40}',window['tip']))
        payload=window["commit_payload"];need(payload["parents"]==[window["parent"]] and payload["tree"]==window["tree"])
        settings=self.p.reliable_settings();person=dict(name=settings["author"],email=settings["email"],date=window["date"])
        need(payload["author"]==payload["committer"]==person)
        need(payload["message"]==f"chore: sync posters - batch {self.a['batch']} git window {window['number']} [skip readme]\n")
        need(not window["changed"] or self.p.commit_identity(payload)==window["tip"])
        need(window["changed"] or window["tip"]==window["parent"])
        need(window["pack_bytes"]<=self.a["max_pack_bytes"])

    def verify_local(self,window,rows):
        self.verify_intent(window)
        t=self.transport;need(self.ledger.unit_binding(rows)==window["binding"])
        before=t.tree(window["parent"]);expected=dict(before)
        for row in rows:expected[row["path"]]=dict(sha=row["blob"],mode="100644",type="blob")
        need(t.tree(window["tip"])==expected and t.git("rev-parse",window["tip"]+"^{tree}").strip().decode()==window["tree"])
        need(window["pack_bytes"]<=self.a["max_pack_bytes"])

    def audit_artwork(self,batch):
        p=self.p;repo=self.a["repo"];style=next(iter(p.repositories));rows=self.ledger.rows(batch,repo)
        need(all(r["status"]=="published" and r["commit_sha"] for r in rows))
        head,_=p.inventory.refresh(style,force=True)
        control=self.ledger.db.execute("SELECT head FROM publication_controls WHERE batch=? AND repo=?",(batch,repo)).fetchone()[0]
        rm=self.ledger.readme_state(batch,repo)
        if head!=control:
            # The unchanged correlated README helper performs the strict run/diff checks.
            need(rm["status"] in {"waiting","verified"})
            from people_readme_publication import ReadmePublication
            from publish_people_github import _ReadmeClient
            helper=ReadmePublication(_ReadmeClient(p.client),p.inventory,p.ledger,sleep=p.sleep,now=p.clock)
            run=helper.find_run(repo,rm["details"]);need(run is not None and run.get("head_sha")==control)
            comparison=p.client.request("GET",f"/repos/{repo}/compare/{control}...{head}")
            allowed={"README.md"}|{r["path"].split('/')[0]+"/README.md" for r in rows}
            need(comparison.get("status")=="ahead" and 1<=comparison.get("total_commits",0)<=10 and comparison.get("files"))
            need(all(r["filename"] in allowed and r["status"] in {"added","modified"} for r in comparison["files"]))
        for row in rows:
            found=p.check_destination(style,row["path"]);need(found and found["sha"]==row["blob"] and found["mode"]=="100644" and found["type"]=="blob")
        need(p.client.head(repo,self.a["branch"])[0]==head)
