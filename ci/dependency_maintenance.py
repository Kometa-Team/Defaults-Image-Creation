"""Exact merged-PR dependency transition, independent of historical receipts.

Select only a separately pinned successor to a known predecessor hash. Callers
still read and SHA-256-check every source with their original LF normalization,
membership, pin-envelope and activation checks. This grants no authority.
"""
from functools import lru_cache
import hashlib
import json
import subprocess
from pathlib import Path

MANIFEST = Path(__file__).with_name("dependency-maintenance-v1.json")
PIN = "bf2ac49432f5e4c2a4403c3f49c3c04a4bb7b998c5716b1e552bac2bc8653246"
DEPENDENCIES = frozenset((
    "create_defaults/canary/requirements-staging.txt",
    "create_defaults/requirements.txt",
    "create_people_posters/requirements-ddcolor.txt",
    "create_people_posters/requirements-rembg.txt",
))
PROTECTION = "create_defaults/bulk/contracts/activation/protection.py"
ADOPTION_SOURCE = "create_defaults/bulk/contracts/adoption/sources.py"
INFRASTRUCTURE = frozenset((PROTECTION, ADOPTION_SOURCE, "ci/phase4.py"))


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
        allow_nan=False, separators=(",", ":")).encode("utf8")).hexdigest()


@lru_cache(maxsize=8)
def _decode(raw):
    # Cache immutable bytes, never a path/mtime or a caller compatibility flag.
    value = json.loads(raw)
    if (fingerprint(value) != PIN or set(value["files"]) != DEPENDENCIES
            or set(value["infrastructure"]) != INFRASTRUCTURE):
        raise ValueError("Changed exact dependency provenance transition")
    return value


def selected_hash(name, expected):
    """Unlisted paths or different predecessors retain their original pin.

    Synthetic manifests keep their existing exact checks. An unrelated future
    change cannot acquire this transition by matching only a path or scope.
    Re-read the manifest on every call so changed content invalidates the cache.
    """
    value = _decode(MANIFEST.read_bytes())
    binding = value["files"].get(name, value["infrastructure"].get(name))
    if binding is not None and expected == binding["before_sha256"]:
        return binding["sha256"]
    return expected


@lru_cache(maxsize=32)
def _historical(root, commit, name):
    return subprocess.check_output(["git", "show", commit+":"+name], cwd=root).replace(b"\r\n", b"\n")


def verify_infrastructure(root):
    """Pin every infrastructure extension before accepting its narrow scope."""
    value = _decode(MANIFEST.read_bytes())
    for name, binding in value["infrastructure"].items():
        before = _historical(str(root), value["baseline_commit"], name)
        current = (Path(root)/name).read_bytes().replace(b"\r\n", b"\n")
        if (hashlib.sha256(before).hexdigest() != binding["before_sha256"]
                or hashlib.sha256(current).hexdigest() != binding["sha256"]):
            raise ValueError("Changed exact dependency infrastructure: "+name)
    return value
