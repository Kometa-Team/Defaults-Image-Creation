"""Read-only production snapshots and verified existing Package E artifacts."""
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
from urllib.parse import quote

import requests

from .common import BulkError, atomic_bytes, canonical, confined, fingerprint, sha256
from .config import ROOT
from .e_validation import configuration
from .remote import ReadOnlyGitHub, RemoteInventory
from .state import Store

EVIDENCE = ROOT / "bulk/evidence/package-e"
REPOSITORY = "Kometa-Team/Default-Images"
CANARY_COMMIT = "22c5ff5225fab7dce972f369bb16bf17a7abe8e0"


def runtime_identity():
    """Bind native encoding/font extensions in addition to package versions."""
    import platform
    from importlib.metadata import version
    from PIL import features, _imaging, _imagingft
    return {"python": platform.python_version(), "platform": platform.system(),
            "packages": {name: version(name) for name in ("Pillow", "fonttools", "uharfbuzz", "python-bidi", "numpy")},
            "native_features": {name: features.version(name) for name in features.get_supported()},
            "extension_sha256": {Path(module.__file__).name: sha256(module.__file__) for module in (_imaging, _imagingft)}}


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sealed(value):
    return dict(value, sha256=fingerprint(value))


def check_seal(value):
    if value.get("sha256") != fingerprint({k: v for k, v in value.items() if k != "sha256"}):
        raise BulkError("corrupt_manifest", "Manifest envelope hash differs")
    return value


def save(path, value):
    atomic_bytes(Path(path), canonical(value) + b"\n", replace=True)


def blob_id(path):
    path = Path(path)
    digest = hashlib.sha1(f"blob {path.stat().st_size}\0".encode())
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def reference(kind):
    index = check_seal(load_json(EVIDENCE / "full-ledger-index.json"))
    binding = index["evidence"][kind]
    path = confined(EVIDENCE, binding["path"], must_exist=True)
    if sha256(path) != binding["file_sha256"]:
        raise BulkError("corrupt_reference", "Compressed Package E ledger changed")
    data = json.loads(gzip.decompress(path.read_bytes()))
    if fingerprint(data) != binding["payload_sha256"]:
        raise BulkError("corrupt_reference", "Package E ledger payload changed")
    from .planner import validate_manifest
    manifest = dict(data["manifest_header"], jobs=[r["job"] for r in data["rows"]])
    validate_manifest(manifest)
    for row in data["rows"]:
        receipt = row["receipt"]
        if (receipt["receipt_sha256"] != fingerprint({k: v for k, v in receipt.items() if k != "receipt_sha256"})
                or receipt["logical_id"] != row["job"]["id"]
                or receipt["render_fingerprint"] != row["job"]["render_fingerprint"]):
            raise BulkError("corrupt_receipt", "Package E receipt identity differs")
    # The additive canary record binds the subsequently accepted public-path
    # correction. Preserve the old ledger, receipt, and render identity verbatim.
    if kind == "english":
        accepted = check_seal(load_json(ROOT / "bulk/evidence/english-canary/visual-acceptance-20261017.json"))
        decisions = {r["id"]: r for r in accepted["decisions"]}
        for row in data["rows"]:
            decision = decisions.get(row["job"]["id"])
            if decision and row["job"]["remote_relative"] != decision["destination"]:
                job = row["job"]
                if (job["remote_relative"], decision["destination"]) != ("genre/Action & adventure.jpg", "genre/Action & Adventure.jpg"):
                    raise BulkError("unreviewed_mapping", "Unknown destination correction")
                if (decision["image_sha256"] != row["receipt"]["sha256"]
                        or decision["render_fingerprint"] != job["render_fingerprint"]
                        or decision["parameters"] != job["parameters"]
                        or decision["inputs"] != job["inputs"]):
                    raise BulkError("unreviewed_mapping", "Destination correction changed rendering context")
                row["identity_correction"] = {"old_destination": job["remote_relative"],
                    "old_validation": row["validation"]["fingerprint"], "acceptance_sha256": accepted["sha256"]}
                job["remote_relative"] = decision["destination"]
                row["validation"]["fingerprint"] = decision["validation_fingerprint"]
    return data


def snapshot(root):
    """Refresh metadata only; GET-only existing inventory, no repository writes."""
    config = configuration(Path(root) / "remote")
    token = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True).stdout.strip()
    client = ReadOnlyGitHub(REPOSITORY, token=token)
    store = Store(config.cache_dir / "state.sqlite")
    result = RemoteInventory(store, config, client).refresh()
    if result["status"] != "complete":
        raise BulkError("incomplete_snapshot", str(result))
    state = result["snapshot"]
    with store.connection() as db:
        entries = [dict(r) for r in db.execute(
            "SELECT path,sha,size,mode,type FROM remote_entries WHERE repo=? AND tree=? ORDER BY path",
            (REPOSITORY, state["tree"]))]
    pr = client._get("pulls/198")
    if not pr.get("merged") or pr.get("merge_commit_sha") != CANARY_COMMIT:
        raise BulkError("canary_merge", "Expected merged canary PR #198 not verified")
    ancestry = client._get("compare/" + CANARY_COMMIT + "..." + state["head"])
    if ancestry.get("status") not in {"identical", "ahead"}:
        raise BulkError("canary_ancestry", "Production does not descend from canary merge")
    if client.head("master") != (state["head"], state["tree"]):
        raise BulkError("baseline_drift", "Production moved during metadata inventory")
    result = sealed({"schema_version": 1, "repository": REPOSITORY, "branch": "master",
                     "head": state["head"], "tree": state["tree"], "checked": state["checked"],
                     "canary_merged": True, "canary_commit": CANARY_COMMIT,
                     "canary_ancestry": ancestry["status"], "entries": entries})
    save(Path(root) / "production-snapshot.json", result)
    return result


def published_file(root, state, entry, local=None, *, force_remote=False):
    """Reuse bytes only when they match the pinned remote Git blob identity."""
    if entry["mode"] != "100644" or entry["type"] != "blob":
        raise BulkError("remote_mode", "Only ordinary image files are supported")
    if not force_remote and local:
        path = confined(local, entry["path"])
        if path.is_file() and blob_id(path) == entry["sha"]:
            return path, "local_bytes_verified_against_remote_blob"
    target = confined(root, "published/" + entry["sha"] + Path(entry["path"]).suffix)
    if target.is_file():
        if blob_id(target) != entry["sha"]:
            raise BulkError("corrupt_cache", "Published cache Git identity differs")
        return target, "pinned_remote_download_cache"
    if entry.get("size", 0) > 20_000_000:
        raise BulkError("oversize_blob", "Published file exceeds bounded download size")
    url = "https://raw.githubusercontent.com/" + REPOSITORY + "/" + state["head"] + "/" + quote(entry["path"], safe="/")
    session = requests.Session()
    session.trust_env = False
    with session.get(url, stream=True, timeout=(15, 90), allow_redirects=False) as response:
        response.raise_for_status()
        data = bytearray()
        for chunk in response.iter_content(65536):
            data.extend(chunk)
            if len(data) > 20_000_000:
                raise BulkError("oversize_blob", "Remote response exceeds byte cap")
    if hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest() != entry["sha"] or len(data) != entry["size"]:
        raise BulkError("remote_identity", "Downloaded bytes differ from pinned tree")
    atomic_bytes(target, bytes(data))
    return target, "pinned_remote_download"
