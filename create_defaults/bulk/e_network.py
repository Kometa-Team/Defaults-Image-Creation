"""Explicit GET-only Package E source pinning and published-path reconciliation."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import subprocess
import time
from urllib.parse import urlsplit

import requests
from PIL import Image, ImageChops, ImageStat

from .common import BulkError, fingerprint, reject_links, sha256
from .config import Config, ROOT
from .e_validation import configuration, save
from .languages import observed_client, refresh, LanguageSnapshot, translations_from_snapshot
from .remote import ReadOnlyGitHub, RemoteInventory
from .state import Store


class BudgetSession(requests.Session):
    def __init__(self, repository, maximum=250):
        super().__init__()
        self.repository, self.maximum = repository, maximum
        self.observations = []
        self.started = time.monotonic()

    def request(self, method, url, **kwargs):
        parsed = urlsplit(url)
        if method != "GET" or parsed.scheme != "https" or parsed.netloc != "api.github.com" or not parsed.path.startswith("/repos/" + self.repository + "/"):
            raise BulkError("network_boundary", "Only GETs to the selected authoritative repository are allowed")
        if len(self.observations) >= self.maximum or time.monotonic() - self.started > 600:
            raise BulkError("network_budget", "Bounded source-inventory request/time budget exceeded")
        result = super().request(method, url, **kwargs)
        remaining = result.headers.get("X-RateLimit-Remaining")
        self.observations.append({"method": method, "path": parsed.path, "status": result.status_code,
                                  "rate_remaining": int(remaining) if remaining else None})
        if remaining and int(remaining) < 100:
            result.close()
            raise BulkError("network_budget", "Conservative authenticated rate reserve reached")
        return result


def token():
    result = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True)
    return result.stdout.strip()


def pin_translations(root):
    root = reject_links(root).resolve()
    configuration(root)
    session = BudgetSession("Kometa-Team/Translations")
    client = ReadOnlyGitHub("Kometa-Team/Translations", token=token(), session=session)
    snapshot, metrics = refresh(root / "cache/translations", client)
    record = {"snapshot": snapshot.data, "metrics": metrics, "requests": session.observations,
              "scope": "Read-only authoritative resource refresh; no translation or font approval"}
    save(root / "translation-refresh.json", record)
    print(json.dumps({"snapshot": snapshot.fingerprint, "source": snapshot.data["provenance"],
                      "languages": list(snapshot.select(["all"])), "metrics": metrics,
                      "requests": len(session.observations)}), flush=True)
    return record


def audit_translations(root):
    root = reject_links(root).resolve()
    record = json.loads((root / "translation-refresh.json").read_text())
    snapshot = LanguageSnapshot.load(record["metrics"]["snapshot_file"])
    from .d_evidence import audit
    result = audit(configuration(root), snapshot)
    matrix = defaultdict(Counter)
    for scope in result["scopes"]:
        matrix[scope["language"]].update(scope["coverage"])
    summary = {key: value for key, value in result.items() if key not in {"scopes", "missing_translations"}}
    summary["matrix"] = {key: dict(value) for key, value in sorted(matrix.items())}
    summary["audit_file_sha256"] = sha256(root / "cache/complete-audit.json")
    summary["scope_count"] = len(result["scopes"])
    summary["approval"] = "No new font, fitting, language or artwork approval"
    save(root / "language-readiness.json", summary)
    print(json.dumps(summary), flush=True)
    return summary


def published(root, baseline, generated=None, samples=0):
    root, baseline = reject_links(root).resolve(), reject_links(baseline).resolve()
    config = configuration(root)
    session = BudgetSession(config.github_repository)
    client = ReadOnlyGitHub(config.github_repository, token=token(), session=session)
    store = Store(config.cache_dir / "state.sqlite")
    inventory = RemoteInventory(store, config, client)
    refreshed = inventory.refresh()
    if refreshed["status"] != "complete":
        raise BulkError("inventory_incomplete", "No trustworthy published reconciliation without complete tree metadata")
    original = json.loads((baseline / "baseline.json").read_text())
    preflight = json.loads((baseline / "cache/preflight" / original["preflight_sha256"] / "preflight.json").read_text())
    rows = []
    for v in preflight["variants"]:
        if v["private"]:
            assert v["remote_relative"] is None
            rows.append({"id": v["id"], "category": v["category"], "expected": None, "status": "private_excluded"})
        else:
            remote = inventory.lookup(v["remote_relative"])
            rows.append({"id": v["id"], "category": v["category"], "expected": v["remote_relative"],
                         "local": v["local_relative"], "status": remote["status"],
                         **({"blob": remote["entry"]["sha"], "published_bytes": remote["entry"]["size"]} if remote["status"] == "found" else {}),
                         **({"conflicts": remote["entries"]} if remote["status"] == "case_conflict" else {})})
    save(root / "path-ledger.json", rows)
    comparisons = []
    if samples:
        if not generated:
            raise BulkError("missing_generated_outputs", "Selective comparisons require actual locally verified generation")
        selected = []
        for category in sorted({r["category"] for r in rows}):
            candidates = sorted((r for r in rows if r["category"] == category and r["status"] == "found"), key=lambda r: r["expected"])
            if candidates:
                selected.append(candidates[0])
        for r in selected[:samples]:
            local = Path(generated) / "output" / r["local"]
            if not local.is_file():
                continue
            old = inventory.fetch_image(r["expected"])
            a_hash, b_hash = sha256(old), sha256(local)
            with Image.open(old) as a, Image.open(local) as b:
                same_size = a.size == b.size
                aa, bb = a.convert("RGBA"), b.convert("RGBA")
                pixels = same_size and ImageChops.difference(aa, bb).getbbox(alpha_only=False) is None
                metrics = {"same_dimensions": same_size, "decoded_pixel_identical": pixels}
                if same_size:
                    means = ImageStat.Stat(ImageChops.difference(aa, bb)).mean
                    metrics["rgb_mae"] = sum(means[:3]) / 3
            comparisons.append({"path": r["expected"], "published_blob": r["blob"],
                "published_sha256": a_hash, "generated_sha256": b_hash, "same_bytes": a_hash == b_hash,
                **metrics, "classification": "exact_bytes" if a_hash == b_hash else "exact_decoded_pixels" if pixels else "different_requires_reference_classification"})
    summary = {"snapshot": refreshed["snapshot"], "expected_contracts": len(rows),
        "counts": dict(Counter(r["status"] for r in rows)),
        "by_category": {category: dict(Counter(r["status"] for r in rows if r["category"] == category)) for category in sorted({r["category"] for r in rows})},
        "path_ledger_sha256": fingerprint(rows), "comparisons": comparisons,
        "not_compared": sum(r["status"] == "found" for r in rows) - len(comparisons),
        "requests": session.observations,
        "private_policy": "Both Awards intermediates have no expected published destination",
        "retired": "D02 green Splatter removed; red genre/Splatter.jpg remains authoritative; original retirement evidence unchanged",
        "scope": "Pinned GET-only tree metadata and bounded selected blobs, no clone or remote mutation"}
    save(root / "published-summary.json", summary)
    print(json.dumps({k: v for k, v in summary.items() if k not in {"requests", "by_category", "comparisons"}}), flush=True)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["translations", "audit", "published"])
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--generated", type=Path)
    parser.add_argument("--samples", type=int, choices=range(0, 26), default=0)
    args = parser.parse_args(argv)
    if args.operation == "translations":
        pin_translations(args.root)
    elif args.operation == "audit":
        audit_translations(args.root)
    else:
        if not args.baseline:
            parser.error("published requires --baseline")
        published(args.root, args.baseline, args.generated, args.samples)


if __name__ == "__main__":
    main()

