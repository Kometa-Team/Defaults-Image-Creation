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
PIN = "8deb50e4f2b2e18b9688fd3bbcc427e2d67cdf6051f6794f206f07acb69dd590"
DEPENDENCIES = frozenset((
    "create_defaults/canary/requirements-staging.txt",
    "create_defaults/requirements.txt",
    "create_people_posters/requirements-ddcolor.txt",
    "create_people_posters/requirements-rembg.txt",
))
PROTECTION = "create_defaults/bulk/contracts/activation/protection.py"
ADOPTION_SOURCE = "create_defaults/bulk/contracts/adoption/sources.py"
# The People repair changes only the production-manifest literal in the
# already-approved protection implementation. Preserve the immutable PR23
# transition and bind this later intersection to exact predecessor/successor
# bytes, including the repair before the dependency import was integrated.
PEOPLE_PROTECTION_PREDECESSORS = frozenset((
    "5a02a0b79dedb2191d9eb8e60676f779e9a529819dca9a17e6cc0d7fd114e5b3",
    "6adaa795f47483ded43999c321bf98972598e5fc9890db8ad7b738b22c996893",
))
PEOPLE_PROTECTION_SHA256 = "a35be7c2b8180164e0eae2a735198041cf2eac755ca200a4b9d844b010b2d930"
INFRASTRUCTURE = frozenset((PROTECTION, ADOPTION_SOURCE, "ci/phase4.py",
    "create_defaults/phase4/tests/test_ci_transactions.py",
    "create_defaults/bulk/tests/test_canary_staging.py",
    "create_defaults/bulk/tests/test_logo_workflow.py"))


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
        expected = binding["sha256"]
    if name == PROTECTION and expected in PEOPLE_PROTECTION_PREDECESSORS:
        return PEOPLE_PROTECTION_SHA256
    from ci.people_storage_maintenance import selected_hash as storage_hash
    return storage_hash(name, expected)


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
                or hashlib.sha256(current).hexdigest() != selected_hash(name, binding["sha256"])):
            raise ValueError("Changed exact dependency infrastructure: "+name)
    return value


def historical_dependency_bytes(name, current, root):
    """Verify current bytes, then recover exact prior bytes for frozen fixtures.

    This is a historical test view, never a current dependency or renderer pin.
    Neither a changed successor nor an unlisted source can use this path.
    """
    value = _decode(MANIFEST.read_bytes())
    binding = value["files"].get(name)
    normalized = current.replace(b"\r\n", b"\n")
    if binding is None or hashlib.sha256(normalized).hexdigest() != binding["sha256"]:
        raise ValueError("Changed current dependency for historical view: "+name)
    before = _historical(str(root), value["dependency_commit"]+"^", name)
    if hashlib.sha256(before).hexdigest() != binding["before_sha256"]:
        raise ValueError("Changed historical dependency predecessor: "+name)
    return before


def current_calibration_expectation(historical):
    """Exact dependency-specific test expectation, never policy approval.

    Preserve the sealed historical report. Change only the measured runtime
    version and its derived policy fingerprint in a separate current expectation;
    both complete canonical report hashes are pinned. No field is ignored.
    """
    binding = _decode(MANIFEST.read_bytes())["logo_calibration"]
    if fingerprint(historical) != binding["before_sha256"]:
        raise ValueError("Changed historical calibration evidence")
    result = json.loads(json.dumps(historical))
    if len(result["measurements"]) != binding["measurements"]:
        raise ValueError("Changed calibration membership")
    for row in result["measurements"]:
        diagnostics = row["diagnostics"]
        if (diagnostics["settings"]["Pillow"] != binding["before_version"]
                or diagnostics["policy_sha256"] != binding["before_policy_sha256"]):
            raise ValueError("Changed historical calibration provenance")
        diagnostics["settings"]["Pillow"] = binding["version"]
        diagnostics["policy_sha256"] = binding["policy_sha256"]
    if fingerprint(result) != binding["sha256"]:
        raise ValueError("Changed current calibration expectation")
    return result
