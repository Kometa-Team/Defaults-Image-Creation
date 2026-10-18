"""Disabled-by-default seven-image staging. No publish/update-ref/merge API exists."""
import argparse
import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import zipfile

from PIL import Image
import requests

from .common import BulkError, canonical, fingerprint, sha256
from .config import ROOT
from .state import Store

SOURCE = "Kometa-Team/Defaults-Image-Creation"
TARGET = "Kometa-Team/Default-Images"
EVIDENCE = ROOT / "bulk/evidence/english-canary"
SETUP = ROOT / "canary"
BUNDLE_SHA = "97d82b19eb237908cbd4657c67ca16eefe089b5a6d6a5f9e1690fda6cdb597c5"
PREPARATION_SHA = "bc7657363fb253bb41965b56bd73ef650be5dc9606bfff486ac8aa76eb2d77be"
ACCEPTANCE_SHA = "139ed5b73c5ee555488163e024c85e33850207a401aa65b546d87c6b1a7f3919"
BUNDLE_NAME = "english-canary-review-bundle.zip"
RELEASE_TAG = "english-canary-approved-v1"
MAX_ARCHIVE = 16 * 1024**2
DESTINATIONS = {"based/Book.jpg", "decade/2020.jpg", "franchise/Death in Paradise (2011).jpg", "genre/Action & Adventure.jpg", "genre/Splatter.jpg", "year/2020.jpg", "year/best/2020.jpg"}


def require(condition, message):
    if not condition:
        raise BulkError("canary_staging_stop", message)


def envelope(path):
    value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    require(value.get("sha256") == fingerprint({k:v for k,v in value.items() if k != "sha256"}), "Evidence envelope changed")
    return value


def git_blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


class Audit:
    """Existing immutable SQLite events plus exclusive, hash-chained portable files."""
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=False)
        self.store = Store(self.root / "events.sqlite")
        self.previous, self.count = None, 0

    def add(self, kind, payload):
        self.count += 1
        item = {"schema_version":1, "sequence":self.count, "previous":self.previous,
                "kind":kind, "payload":payload, "at_utc":datetime.now(timezone.utc).isoformat()}
        item["sha256"] = fingerprint(item)
        with self.store.transaction() as db:
            self.store.event(db, "canary_staging_" + kind, str(self.count), item)
        with (self.root / f"{self.count:04d}.json").open("xb") as f:
            f.write(canonical(item) + b"\n")
        self.previous = item["sha256"]


def verify_audit(root):
    root=Path(root);files=sorted(root.glob("[0-9][0-9][0-9][0-9].json"));previous=None
    store=Store(root/"events.sqlite")
    with store.connection() as db:events=[json.loads(row["payload"]) for row in db.execute("SELECT payload FROM events ORDER BY sequence")]
    require(len(files)==len(events) and bool(files),"Audit database/export count mismatch")
    for number,(path,stored) in enumerate(zip(files,events),1):
        item=envelope(path)
        require(item==stored and item["sequence"]==number and item["previous"]==previous,"Audit chain/database mismatch")
        previous=item["sha256"]
    return previous


@dataclass
class Bundle:
    preparation: dict
    acceptance: dict
    index: dict
    members: dict

    @property
    def rows(self):
        return self.preparation["rows"]


def read_archive(path, expected_sha, inventory):
    path = Path(path)
    require(path.stat().st_size <= MAX_ARCHIVE and sha256(path) == expected_sha, "Archive hash/size mismatch")
    with zipfile.ZipFile(path) as z:
        infos = z.infolist()
        names = [i.filename for i in infos]
        require(len(names) == len(set(names)) and set(names) == set(inventory) | {"SHA256SUMS.json"}, "Unexpected/duplicate archive members")
        require(sum(i.file_size for i in infos) <= 64 * 1024**2, "Archive decompression limit")
        for i in infos:
            p = PurePosixPath(i.filename)
            require(not p.is_absolute() and ".." not in p.parts and "\\" not in i.filename and ":" not in i.filename, "Unsafe archive path")
            require(not stat.S_ISLNK(i.external_attr >> 16) and not i.is_dir(), "Archive links/directories forbidden")
            require(i.file_size <= 20 * 1024**2, "Archive member too large")
        members = {name:z.read(name) for name in names}
    require(json.loads(members["SHA256SUMS.json"]) == inventory, "Checksum inventory changed")
    for name, binding in inventory.items():
        data = members[name]
        require(hashlib.sha256(data).hexdigest() == binding["sha256"] and len(data) == binding["bytes"], "Archive member checksum mismatch")
    return members


def verify_bundle(path):
    prepared = envelope(EVIDENCE / "preparation-20261017.json")
    accepted = envelope(EVIDENCE / "visual-acceptance-20261017.json")
    index = envelope(EVIDENCE / "bundle-index-20261017.json")
    require(prepared["sha256"] == PREPARATION_SHA and accepted["sha256"] == ACCEPTANCE_SHA, "Accepted proof identities changed")
    require(index["archive_sha256"] == accepted["bundle_archive_sha256"] == BUNDLE_SHA, "Unapproved archive identity")
    require(accepted["preparation_sha256"] == PREPARATION_SHA and len(prepared["rows"]) == 7, "Preparation scope changed")
    members = read_archive(path, BUNDLE_SHA, index["inventory"])
    require(json.loads(members["preparation.json"]) == prepared, "Archive preparation differs from accepted report")
    decisions = {d["id"]:d for d in accepted["decisions"]}
    require(len(decisions) == len(accepted["decisions"]) == 7, "Seven individual decisions required")
    paths = set()
    for row in prepared["rows"]:
        decision = decisions.get(row["id"], {})
        require(decision.get("language") == "en" and decision.get("image_sha256") == row["sha256"], "Unaccepted image")
        require(decision.get("destination") == row["destination"] and row["destination"] not in paths, "Destination scope changed")
        paths.add(row["destination"])
        require(decision["validation_fingerprint"] == row["validation_fingerprint"] and decision["render_fingerprint"] == row["render_fingerprint"], "Accepted renderer/validation changed")
        require(decision["review_context"]["renderer"] == prepared["renderer"], "Renderer identity changed")
        require(decision["accepted_published_comparison"] == row["published"], "Published comparison changed")
        proposed = members["output/" + row["local_relative"]]
        old = members[row["published"]["local_verified_backup"]]
        require(hashlib.sha256(proposed).hexdigest() == row["sha256"] and hashlib.sha256(old).hexdigest() == row["published"]["sha256"], "Image byte mismatch")
        require(git_blob(old) == row["published"]["git_blob"], "Backup Git identity mismatch")
        with Image.open(BytesIO(proposed)) as image:
            image.load()
            require(image.format == "JPEG" and image.mode == "RGB" and image.size == (2000,3000), "Invalid proposed JPEG")
    require("genre/Action & Adventure.jpg" in paths and "genre/Action & adventure.jpg" not in paths, "Mandatory destination case changed")
    return Bundle(prepared, accepted, index, members)


def validate_authorization(policy, auth, *, source_sha, helper_sha, workflow_sha, now=None):
    require(policy.get("staging_enabled") is True, "Staging is disabled in reviewed policy")
    require(policy.get("target_repository")==TARGET and policy.get("source_environment")=="english-canary-stage" and policy.get("source_ref")=="refs/heads/main" and policy.get("publication_enabled") is False,"Policy target/environment/publishing scope mismatch")
    require(policy.get("reviewer_confirmed") is True and policy.get("rollback_owner_confirmed") is True, "Proposed ownership not confirmed")
    require(policy.get("primary_reviewer") == policy.get("rollback_owner") == "bullmoose20", "Unexpected owner/reviewer")
    require(auth.get("authorized") is True and auth.get("action") == "stage_seven_english_images_only", "Separate staging authorization absent")
    require(auth.get("target_repository") == TARGET and auth.get("target_branch") == "master", "Wrong target")
    require(auth.get("bundle_sha256") == BUNDLE_SHA and auth.get("preparation_sha256") == PREPARATION_SHA and auth.get("acceptance_sha256") == ACCEPTANCE_SHA, "Authorization artifact identity mismatch")
    require(auth.get("source_commit") == source_sha and auth.get("helper_sha256") == helper_sha and auth.get("workflow_sha256") == workflow_sha, "Unapproved implementation/source")
    require(auth.get("reviewer") == auth.get("rollback_owner") == "bullmoose20" and auth.get("owner_confirmation") is True, "Owner confirmation missing")
    require(auth.get("writer_reservation_confirmed") is True and auth.get("artifact_retention_confirmed") is True, "Writer reservation/durable backup missing")
    require(re.fullmatch(r"[0-9a-f]{40}", auth.get("expected_target_head", "")) is not None, "Pinned target HEAD required")
    require(auth.get("expected_target_head") == policy.get("expected_target_head"), "Policy/authorization target HEAD differs")
    require(type(auth.get("source_release_asset_id")) is int and auth["source_release_asset_id"]>0,"Pinned source release asset ID required")
    require(auth.get("publish_authorized") is False and auth.get("merge_authorized") is False, "Staging authorization must exclude publishing/merging")
    require(isinstance(auth.get("expires_at_utc"),str),"Authorization expiry required")
    try:
        end = datetime.fromisoformat(auth["expires_at_utc"].replace("Z", "+00:00"))
    except ValueError as error:
        raise BulkError("canary_staging_stop","Invalid authorization expiry") from error
    now = now or datetime.now(timezone.utc)
    require(end.tzinfo is not None and now < end and (end-now).total_seconds() <= 86400, "Expired/overlong authorization")
    return "canary/english-" + auth["sha256"][:12]


def check_environment(value, branches):
    rules = [r for r in value.get("protection_rules", []) if r.get("type") == "required_reviewers"]
    require(len(rules) == 1 and rules[0].get("prevent_self_review") is True, "Required reviewer/self-review protection missing")
    reviewers = rules[0].get("reviewers", [])
    require(len(reviewers) == 1 and reviewers[0].get("type") == "User" and reviewers[0].get("reviewer",{}).get("login") == "bullmoose20", "Required reviewer must be bullmoose20")
    require(value.get("deployment_branch_policy") == {"protected_branches":False,"custom_branch_policies":True}, "Selected deployment branches required")
    require([(b.get("name"),b.get("type")) for b in branches] == [("main","branch")], "Environment must allow only main branch")
    # GitHub does not reliably return admin-bypass state in this response. Its
    # independently reviewed settings evidence is a separate authorization condition.


def runtime_write_gate(authorization_sha):
    policy=envelope(SETUP/"staging-policy.json");auth=envelope(SETUP/"staging-authorization.json")
    require(policy.get("staging_enabled") is True and policy.get("reviewer_confirmed") is True and policy.get("rollback_owner_confirmed") is True,"Staging transport disabled")
    require(auth.get("authorized") is True and auth["sha256"]==authorization_sha,"Staging transport authorization absent/changed")
    require(auth.get("publish_authorized") is False and auth.get("merge_authorized") is False,"Unexpected production authority")
    expiry=datetime.fromisoformat(auth["expires_at_utc"].replace("Z","+00:00"))
    require(expiry.tzinfo is not None and datetime.now(timezone.utc)<expiry,"Staging authorization expired")


class GitHub:
    """Only seven-object staging endpoints; no ref-update, deletion or merge method."""
    def __init__(self, token, audit, expected_head, authorization_sha):
        runtime_write_gate(authorization_sha)
        require(bool(token), "Explicit staging App token required; no ambient fallback")
        self.session = requests.Session(); self.session.trust_env = False
        self.session.headers.update({"Authorization":"Bearer " + token,"Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"})
        self.audit, self.expected_head, self.staging_commit = audit, expected_head, None
        self.authorization_sha = authorization_sha
        accepted=envelope(EVIDENCE/"visual-acceptance-20261017.json")
        require(accepted["sha256"]==ACCEPTANCE_SHA,"Accepted metadata changed")
        self.accepted_image_hashes={d["image_sha256"] for d in accepted["decisions"]}

    def call(self, method, endpoint, payload=None):
        allowed_posts = {"git/blobs","git/trees","git/commits","git/refs","pulls"}
        require(method == "GET" or (method == "POST" and endpoint in allowed_posts), "Forbidden API method/endpoint")
        require(not endpoint.startswith(("/","http")) and ".." not in endpoint, "Unsafe endpoint")
        if method == "POST":
            runtime_write_gate(self.authorization_sha)
            require(isinstance(payload,dict) and "force" not in payload,"Force/update semantics forbidden")
            if endpoint == "git/blobs":
                require(set(payload)=={"encoding","content"} and payload.get("encoding")=="base64","Only exact base64 image blobs allowed")
                try:data=base64.b64decode(payload["content"],validate=True)
                except (ValueError,TypeError) as error:raise BulkError("canary_staging_stop","Invalid blob encoding") from error
                require(hashlib.sha256(data).hexdigest() in self.accepted_image_hashes,"Blob is not one of seven accepted images")
            elif endpoint == "git/refs":
                require(set(payload)=={"ref","sha"} and re.fullmatch(r"refs/heads/canary/english-[0-9a-f]{12}",payload.get("ref","")) is not None,"Ref outside staging namespace")
                require(payload["ref"]=="refs/heads/canary/english-"+self.authorization_sha[:12],"Ref not bound to authorization")
                require(self.staging_commit is not None and payload["sha"]==self.staging_commit,"Unverified staging commit")
            elif endpoint == "git/trees":
                rows=payload.get("tree",[])
                require(len(rows)==7 and {r.get("path") for r in rows}==DESTINATIONS,"Tree scope differs from seven-file allowlist")
                require(all(r.get("mode")=="100644" and r.get("type")=="blob" and re.fullmatch(r"[0-9a-f]{40}",r.get("sha","")) for r in rows),"Deletion/rename/non-image entry forbidden")
            elif endpoint == "git/commits":
                require(payload.get("parents")==[self.expected_head],"Unapproved commit parent")
            elif endpoint == "pulls":
                require(payload.get("draft") is True and payload.get("base")=="master" and payload.get("head")=="canary/english-"+self.authorization_sha[:12],"Only the authorization-bound draft canary PR is allowed")
        response = self.session.request(method, "https://api.github.com/repos/"+TARGET+"/"+endpoint,
            json=payload, timeout=(10,30), allow_redirects=False, stream=True)
        self.audit.add("http_result", {"method":method,"endpoint":endpoint,"status":response.status_code})
        data = bytearray()
        for part in response.iter_content(65536):
            data.extend(part); require(len(data) <= 20*1024**2, "API response too large")
        response.close()
        if response.status_code == 404 and method == "GET": return None
        require(200 <= response.status_code < 300, "GitHub request failed; no automatic write retry")
        return json.loads(data)

    def check_token_scope(self):
        # Installation API has a different fixed path; never takes caller URLs.
        response = self.session.get("https://api.github.com/installation/repositories?per_page=100",timeout=(10,30),allow_redirects=False)
        require(response.status_code == 200, "Cannot verify installation token scope")
        value = response.json(); response.close()
        require(value.get("total_count") == 1 and [r["full_name"] for r in value.get("repositories",[])] == [TARGET], "Token must be scoped only to Default-Images")

    def head(self):
        value = self.call("GET","git/ref/heads/master"); require(value is not None,"Missing master")
        return value["object"]["sha"]

    def snapshot(self):
        head = self.head(); commit = self.call("GET","git/commits/"+head)
        require(commit.get("sha")==head,"Target commit identity mismatch")
        return head, commit["tree"]["sha"], self.files(commit["tree"]["sha"])

    def files(self, tree):
        value = self.call("GET","git/trees/"+tree+"?recursive=1")
        require(value.get("sha") == tree and value.get("truncated") is False, "Complete verified tree required")
        entries = value["tree"]; require(len(entries) == len({e["path"] for e in entries}),"Duplicate tree entries")
        return {e["path"]:{"sha":e["sha"],"mode":e["mode"],"type":e["type"]} for e in entries if e["type"] != "tree"}

    def blob(self, data):
        value = self.call("POST","git/blobs",{"encoding":"base64","content":base64.b64encode(data).decode()})
        require(value["sha"] == git_blob(data),"Created blob identity mismatch"); return value["sha"]

    def tree(self, base, replacements):
        return self.call("POST","git/trees",{"base_tree":base,"tree":[{"path":p,"sha":s,"mode":"100644","type":"blob"} for p,s in sorted(replacements.items())]})["sha"]

    def commit(self, tree, parent, message):
        result = self.call("POST","git/commits",{"tree":tree,"parents":[parent],"message":message})
        require([p["sha"] for p in result["parents"]] == [parent] and result["tree"]["sha"] == tree,"Commit ancestry/tree mismatch")
        self.staging_commit=result["sha"]
        return result["sha"]

    def create_ref(self, branch, commit):
        require(re.fullmatch(r"canary/english-[0-9a-f]{12}",branch) is not None,"Ref outside staging namespace")
        require(self.call("GET","git/ref/heads/"+branch) is None,"Staging ref exists; stop for reconciliation")
        result = self.call("POST","git/refs",{"ref":"refs/heads/"+branch,"sha":commit})
        require(result["ref"] == "refs/heads/"+branch and result["object"]["sha"] == commit,"Staging ref mismatch")

    def pull(self, branch, commit, auth_sha):
        require(re.fullmatch(r"canary/english-[0-9a-f]{12}",branch) is not None,"Invalid PR head")
        result = self.call("POST","pulls",{"title":"English canary: seven accepted images — do not merge","base":"master","head":branch,"draft":True,
            "body":"Staging only. Accepted seven-image archive "+BUNDLE_SHA+". Authorization "+auth_sha+". Exact commit "+commit+". No publication/merge authority."})
        require(result.get("draft") is True and result["base"]["ref"] == "master" and result["head"]["sha"] == commit,"PR identity mismatch")
        return {"number":result["number"],"url":result["html_url"],"draft":True}


def stage_objects(client, bundle, expected_head, branch, auth_sha, audit):
    head, base_tree, original = client.snapshot()
    require(head == expected_head, "Target HEAD drift before staging")
    rows = bundle.rows
    require(len(rows) == 7 and {r["destination"] for r in rows} == DESTINATIONS,"Exactly seven approved destinations required")
    for row in rows:
        matches = [p for p in original if p.casefold() == row["destination"].casefold()]
        require(matches == [row["destination"]],"Missing/case-conflicting destination")
        require(original[row["destination"]] == {"sha":row["published"]["git_blob"],"mode":"100644","type":"blob"},"Published blob/mode changed")
    require(client.head() == expected_head,"Target HEAD drift before first write")
    replacements = {}
    for row in rows:
        data = bundle.members["output/"+row["local_relative"]]
        require(hashlib.sha256(data).hexdigest() == row["sha256"],"Candidate bytes changed")
        audit.add("write_intent",{"operation":"create_blob","path":row["destination"],"sha256":row["sha256"]})
        replacements[row["destination"]] = client.blob(data)
    tree = client.tree(base_tree,replacements)
    expected_files = dict(original)
    for path,checksum in replacements.items(): expected_files[path] = {"sha":checksum,"mode":"100644","type":"blob"}
    require(client.files(tree) == expected_files,"Candidate tree includes extra changes")
    commit = client.commit(tree,head,"Stage seven individually accepted English canary images; authorization "+auth_sha)
    require(client.head() == expected_head,"Target HEAD drift before staging ref creation")
    audit.add("write_intent",{"operation":"create_new_staging_ref","branch":branch,"commit":commit,"overwrite_existing":False})
    client.create_ref(branch,commit)
    require(client.head() == expected_head,"Target HEAD drift after staging ref; stop, preserve branch")
    audit.add("write_intent",{"operation":"create_draft_target_pr","branch":branch,"commit":commit,"merge_authorized":False})
    pull = client.pull(branch,commit,auth_sha)
    require(client.head() == expected_head,"Target HEAD drift after PR; stop for review")
    audit.add("staging_result",{"base":head,"candidate_commit":commit,"changed_paths":sorted(replacements),"pull":pull,"production_ref_updated":False})
    return {"base":head,"tree":tree,"candidate_commit":commit,"paths":sorted(replacements),"pull":pull}


class LocalGit:
    """Real local Git objects; never creates a staging ref/PR and has no remote."""
    def __init__(self, root, bundle):
        self.root = Path(root); self.root.mkdir(parents=True,exist_ok=False)
        self.git("init","--initial-branch=offline-baseline")
        self.git("config","user.name","Offline staging rehearsal")
        self.git("config","user.email","canary-staging@example.invalid")
        self.git("config","core.autocrlf","false")
        for row in bundle.rows:
            p=self.root/row["destination"];p.parent.mkdir(parents=True,exist_ok=True)
            p.write_bytes(bundle.members[row["published"]["local_verified_backup"]])
        (self.root/"unrelated-sentinel.txt").write_bytes(b"Unrelated content remains unchanged.\n")
        self.git("add","--all");self.git("commit","-m","Offline published-byte fixture")
        self.baseline_refs=self.git("show-ref"); self.index=self.root.parent/"candidate-index"
        require(self.git("remote","-v")==b"","Local fixture must have no remotes")

    def git(self,*args,data=None,index=False,raw=False):
        env=dict(os.environ)
        if index:env["GIT_INDEX_FILE"]=str(self.index)
        result=subprocess.run(["git","-C",str(self.root),*args],input=data,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,check=True)
        return result.stdout if raw else result.stdout.strip()

    def head(self):return self.git("rev-parse","HEAD").decode()
    def files(self,tree):
        rows=self.git("ls-tree","-r","-z",tree).split(b"\0");result={}
        for row in rows:
            if not row:continue
            meta,path=row.split(b"\t",1);mode,kind,checksum=meta.decode().split()
            result[path.decode()]={"sha":checksum,"mode":mode,"type":kind}
        return result
    def snapshot(self):
        tree=self.git("rev-parse","HEAD^{tree}").decode();return self.head(),tree,self.files(tree)
    def blob(self,data):return self.git("hash-object","-w","--stdin",data=data).decode()
    def tree(self,base,replacements):
        self.git("read-tree",base,index=True)
        for path,checksum in sorted(replacements.items()):self.git("update-index","--add","--cacheinfo","100644",checksum,path,index=True)
        return self.git("write-tree",index=True).decode()
    def commit(self,tree,parent,message):return self.git("commit-tree",tree,"-p",parent,"-m",message).decode()
    def create_ref(self,branch,commit):self.would_create_ref={"branch":branch,"commit":commit}
    def pull(self,branch,commit,auth_sha):return {"dry_run":True,"created":False,"would_open_draft":True}


def dry_run(bundle_path, root):
    root=Path(root).resolve();allowed=(ROOT.parent/"config/canary-staging").resolve()
    require(root.is_relative_to(allowed) and root!=allowed and not root.exists(),"Use a fresh isolated config/canary-staging child")
    root.mkdir(parents=True);audit=Audit(root/"audit")
    bundle=verify_bundle(bundle_path);client=LocalGit(root/"repository",bundle)
    baseline=client.head()
    audit.add("local_only",{"network_client_constructed":False,"remotes":[],"archive_sha256":BUNDLE_SHA,"accepted_images":7,"staging_authorized":False})
    result=stage_objects(client,bundle,baseline,"canary/english-"+ACCEPTANCE_SHA[:12],ACCEPTANCE_SHA,audit)
    diff=client.git("diff-tree","--no-commit-id","--name-only","-r","-z",baseline,result["candidate_commit"]).decode().split("\0")
    require(set(filter(None,diff))==set(result["paths"]),"Local dry-run diff not exactly seven files")
    for row in bundle.rows:
        data=client.git("cat-file","blob",result["candidate_commit"]+":"+row["destination"],raw=True)
        require(hashlib.sha256(data).hexdigest()==row["sha256"],"Local candidate hash mismatch")
    require(client.head()==baseline and client.git("show-ref")==client.baseline_refs and client.git("remote","-v")==b"" and client.git("status","--porcelain")==b"","Local refs/worktree changed")
    report={"schema_version":1,"kind":"offline_seven-image_staging_infrastructure_dry_run","archive_sha256":BUNDLE_SHA,"acceptance_sha256":ACCEPTANCE_SHA,
        "local_base_commit":baseline,"local_candidate_commit":result["candidate_commit"],"exact_changed_paths":result["paths"],"verified_candidate_hashes":7,
        "helper_sha256":hashlib.sha256(Path(__file__).read_bytes().replace(b"\r\n",b"\n")).hexdigest(),"local_refs_unchanged":True,"local_worktree_unchanged":True,"network_requests":0,"remote_writes":0,"staging_branches_created":0,"pull_requests_created":0,"production_authorized":False}
    audit.add("dry_run_complete",report);report["audit_tail_sha256"]=audit.previous;report["sha256"]=fingerprint(report)
    with (root/"dry-run.json").open("xb") as f:f.write(canonical(report)+b"\n")
    require(verify_audit(root/"audit")==report["audit_tail_sha256"],"Audit verification failed")
    print(json.dumps(report));return report


def gh_json(endpoint):
    result=subprocess.run(["gh","api",endpoint],stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True,timeout=60)
    return json.loads(result.stdout)


def fetch_bundle(asset_id, output):
    require(re.fullmatch(r"[1-9][0-9]*",str(asset_id)) is not None,"Positive source asset ID required")
    release=gh_json("repos/"+SOURCE+"/releases/tags/"+RELEASE_TAG)
    require(release.get("draft") is False and release.get("prerelease") is True,"Bundle intake requires the separately authorized source prerelease; no source write token fallback")
    assets=[a for a in release.get("assets",[]) if str(a["id"])==str(asset_id)]
    require(len(assets)==1,"Asset not in approved source release")
    asset=assets[0]
    require(asset["name"]==BUNDLE_NAME and asset["size"]==7256318 and asset.get("digest")=="sha256:"+BUNDLE_SHA,"Source asset metadata/hash mismatch")
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    subprocess.run(["gh","release","download",RELEASE_TAG,"--repo",SOURCE,"--pattern",BUNDLE_NAME,"--dir",str(output)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True,timeout=180)
    require({p.name for p in output.iterdir()}=={BUNDLE_NAME},"Unexpected downloaded files")
    verify_bundle(output/BUNDLE_NAME)


def preflight_staging(bundle_path, asset_id):
    policy=envelope(SETUP/"staging-policy.json");auth=envelope(SETUP/"staging-authorization.json")
    require(policy.get("staging_enabled") is True,"Staging remains disabled; no credentials/network accessed")
    implementation=auth.get("source_commit","")
    require(isinstance(implementation,str) and re.fullmatch(r"[0-9a-f]{40}",implementation) is not None,"Approved implementation commit required")
    current=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT.parent,text=True).strip()
    subprocess.run(["git","merge-base","--is-ancestor",implementation,current],cwd=ROOT.parent,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    changed=subprocess.check_output(["git","diff","--name-only",implementation,current],cwd=ROOT.parent,text=True).splitlines()
    require(set(changed)<= {"create_defaults/canary/staging-authorization.json","create_defaults/canary/staging-policy.json"},"Implementation changed after approval; only explicit activation/authorization JSON follow-up allowed")
    require(subprocess.check_output(["git","status","--porcelain","--untracked-files=no"],cwd=ROOT.parent,text=True).strip()=="","Trusted workflow checkout must be clean")
    helper_sha=hashlib.sha256(Path(__file__).read_bytes().replace(b"\r\n",b"\n")).hexdigest()
    workflow=ROOT.parent/".github/workflows/english-poster-canary.yml"
    require(workflow.is_file(),"Reviewed workflow is not installed")
    workflow_sha=hashlib.sha256(workflow.read_bytes().replace(b"\r\n",b"\n")).hexdigest()
    branch=validate_authorization(policy,auth,source_sha=implementation,helper_sha=helper_sha,workflow_sha=workflow_sha)
    require(str(auth.get("source_release_asset_id"))==str(asset_id),"Authorization asset ID mismatch")
    require(auth.get("admin_bypass_disabled_confirmed") is True,"Environment bypass settings not confirmed")
    require(os.environ.get("GITHUB_ACTIONS")=="true" and os.environ.get("GITHUB_REPOSITORY")==SOURCE and os.environ.get("GITHUB_EVENT_NAME")=="workflow_dispatch" and os.environ.get("GITHUB_REF")=="refs/heads/main","Only approved manual workflow on source main may stage")
    require(os.environ.get("CANARY_STAGING_CONFIRMED")=="true" and os.environ.get("GITHUB_ACTOR")!="bullmoose20","Explicit confirmation and independent dispatcher required")
    require(os.environ.get("CANARY_POLICY_VARIABLE")=="true","Repository staging variable is disabled")
    environment=gh_json("repos/"+SOURCE+"/environments/english-canary-stage")
    policies=gh_json("repos/"+SOURCE+"/environments/english-canary-stage/deployment-branch-policies")
    require(policies.get("total_count")==1,"Exactly one allowed environment branch policy required")
    check_environment(environment,policies.get("branch_policies",[]))
    bundle=verify_bundle(bundle_path)
    require(auth.get("destinations")==sorted(r["destination"] for r in bundle.rows),"Authorization exact path list differs")
    require(auth.get("expected_target_head")==bundle.preparation["published_snapshot"]["head"],"Changed baseline needs a fresh comparison, not authorization substitution")
    return bundle,auth,branch,current


def execute_staging(bundle_path, asset_id, audit_root, *, preflight_only=False):
    audit=Audit(audit_root)
    try:
        bundle,auth,branch,current=preflight_staging(bundle_path,asset_id)
        audit.add("authorized_staging_preflight",{"authorization_sha256":auth["sha256"],"checkout_commit":current,"reviewer":"bullmoose20","archive_sha256":BUNDLE_SHA,"publish_authorized":False})
        if preflight_only:return
        client=GitHub(os.environ.get("CANARY_APP_TOKEN"),audit,auth["expected_target_head"],auth["sha256"]);client.check_token_scope()
        return stage_objects(client,bundle,auth["expected_target_head"],branch,auth["sha256"],audit)
    except Exception as error:
        audit.add("stopped",{"error_type":type(error).__name__,"automatic_retry":False,"automatic_cleanup":False})
        raise


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);commands=parser.add_subparsers(dest="command",required=True)
    for name in ("verify","dry-run","authorize","stage"):
        p=commands.add_parser(name);p.add_argument("--bundle",required=True,type=Path)
        if name=="dry-run":p.add_argument("--root",required=True,type=Path)
        if name in {"authorize","stage"}:p.add_argument("--asset-id",required=True);p.add_argument("--audit-root",required=True,type=Path)
    p=commands.add_parser("audit-verify");p.add_argument("--root",required=True,type=Path)
    p=commands.add_parser("fetch");p.add_argument("--asset-id",required=True);p.add_argument("--out",required=True,type=Path)
    args=parser.parse_args(argv)
    if args.command=="audit-verify":print(verify_audit(args.root))
    elif args.command=="fetch":fetch_bundle(args.asset_id,args.out)
    elif args.command=="verify":verify_bundle(args.bundle);print("Seven exact accepted images and sealed archive verified; no staging authority")
    elif args.command=="dry-run":dry_run(args.bundle,args.root)
    else:execute_staging(args.bundle,args.asset_id,args.audit_root,preflight_only=args.command=="authorize")


if __name__=="__main__":main()
