"""Private, GET-only retrieval of the original sealed ZIP from a pinned Git blob."""
import base64
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
from .common import BulkError

REPOSITORY = "Kometa-Team/english-canary-artifacts"  # proposed; not created
ARCHIVE_PATH = "canary/english-canary-review-bundle.zip"
ARCHIVE_BYTES = 7256318


def validate_config(value, *, now=None):
    from .canary_staging import BUNDLE_SHA, require
    require(value.get("enabled") is True, "Private artifact intake remains disabled")
    require(value.get("repository")==REPOSITORY and value.get("visibility")=="private", "Only the approved private holding repository is allowed")
    require(type(value.get("repository_id")) is int and value["repository_id"]>0, "Pinned private repository ID required")
    require(all(isinstance(value.get(k),str) and re.fullmatch(r"[0-9a-f]{40}",value[k]) for k in ("commit","git_blob")), "Pinned artifact commit/blob required")
    require(value.get("path")==ARCHIVE_PATH and value.get("bytes")==ARCHIVE_BYTES and value.get("sha256_archive")==BUNDLE_SHA, "Approved private archive binding differs")
    require(value.get("durable_backup_confirmed") is True and value.get("deletion_requires_separate_authorization") is True, "Durable backup/deletion policy unconfirmed")
    try:end=datetime.fromisoformat(value["retain_until_utc"].replace("Z","+00:00"))
    except (KeyError,TypeError,ValueError):raise BulkError("canary_staging_stop","Private artifact retention deadline required") from None
    now=now or datetime.now(timezone.utc)
    require(end.tzinfo is not None and (end-now).total_seconds()>=90*86400, "Private artifact retention must cover at least 90 more days")
    return value


class PrivateReader:
    """One explicit short-lived read token; no ambient gh/PAT/proxy/URL fallback."""
    def __init__(self, token, config, audit):
        from .canary_staging import require
        self.config=validate_config(config);require(bool(token),"Explicit private artifact App token required")
        self.audit=audit;self.session=requests.Session();self.session.trust_env=False
        self.session.headers.update({"Authorization":"Bearer "+token,"Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"})

    def get(self, suffix):
        from .canary_staging import require
        allowed={"installation/repositories?per_page=100", "repos/"+REPOSITORY}
        base="repos/"+REPOSITORY+"/git/"
        require(suffix in allowed or re.fullmatch(re.escape(base)+r"(?:commits|blobs)/[0-9a-f]{40}",suffix) or re.fullmatch(re.escape(base)+r"trees/[0-9a-f]{40}\?recursive=1",suffix), "Private reader route outside scope")
        try:
            with self.session.get("https://api.github.com/"+suffix,timeout=(10,30),allow_redirects=False,stream=True) as response:
                self.audit.add("private_read_status",{"status":response.status_code})
                require(response.status_code==200,"Private artifact unavailable; no redirect/token fallback")
                data=bytearray()
                for block in response.iter_content(65536):
                    data.extend(block);require(len(data)<=20*1024**2,"Private artifact response exceeds bound")
            return json.loads(data)
        except (requests.RequestException,ValueError):
            raise BulkError("canary_staging_stop","Private artifact read failed; no retry or URL disclosure") from None

    def retrieve(self):
        from .canary_staging import require, BUNDLE_SHA, git_blob
        scope=self.get("installation/repositories?per_page=100")
        repos=scope.get("repositories",[])
        require(scope.get("total_count")==1 and len(repos)==1 and repos[0].get("full_name")==REPOSITORY and repos[0].get("id")==self.config["repository_id"] and repos[0].get("private") is True,"Artifact App must access only the pinned private repository")
        # Some responses expose permission booleans. Never accept write/admin if
        # present; the workflow also attenuates the minted token to Contents read.
        require(not any(repos[0].get("permissions",{}).get(k) for k in ("push","admin","maintain")),"Artifact credential has write/admin scope")
        repo=self.get("repos/"+REPOSITORY)
        require(repo.get("id")==self.config["repository_id"] and repo.get("full_name")==REPOSITORY and repo.get("private") is True and repo.get("visibility")=="private","Holding repository identity/privacy changed")
        base="repos/"+REPOSITORY+"/git/"
        commit=self.get(base+"commits/"+self.config["commit"])
        require(commit.get("sha")==self.config["commit"] and re.fullmatch(r"[0-9a-f]{40}",commit.get("tree",{}).get("sha","")),"Private artifact commit identity changed")
        tree=self.get(base+"trees/"+commit["tree"]["sha"]+"?recursive=1")
        require(tree.get("sha")==commit["tree"]["sha"] and tree.get("truncated") is False,"Incomplete private artifact tree")
        entries=[r for r in tree.get("tree",[]) if r.get("path")==ARCHIVE_PATH]
        require(len(entries)==1 and entries[0].get("type")=="blob" and entries[0].get("mode")=="100644" and entries[0].get("sha")==self.config["git_blob"],"Private artifact path/mode/blob changed")
        blob=self.get(base+"blobs/"+self.config["git_blob"])
        require(blob.get("sha")==self.config["git_blob"] and blob.get("encoding")=="base64" and blob.get("size")==ARCHIVE_BYTES,"Private artifact blob metadata differs")
        try:data=base64.b64decode(blob["content"].replace("\n","").replace("\r",""),validate=True)
        except (KeyError,ValueError,TypeError):raise BulkError("canary_staging_stop","Private artifact encoding invalid") from None
        require(len(data)==ARCHIVE_BYTES and git_blob(data)==self.config["git_blob"] and hashlib.sha256(data).hexdigest()==BUNDLE_SHA,"Private archive bytes changed")
        self.audit.add("private_archive_verified",{"archive_sha256":BUNDLE_SHA,"bytes":len(data),"private_config_sha256":self.config["sha256"]})
        return data


def fetch(output, audit):
    from .canary_staging import SETUP,envelope,require,verify_bundle,BUNDLE_NAME
    config=envelope(SETUP/"private-artifact.json");validate_config(config)
    output=Path(output);require(not output.exists(),"Private intake output must be fresh")
    reader=PrivateReader(os.environ.get("CANARY_ARTIFACT_TOKEN"),config,audit)
    try:
        data=reader.retrieve();output.mkdir(parents=True,exist_ok=False)
        with (output/BUNDLE_NAME).open("xb") as f:f.write(data)
        verify_bundle(output/BUNDLE_NAME)
        return output/BUNDLE_NAME
    finally:reader.session.close()
