"""Export compact Package D observations, never images, databases or bulk output."""

from collections import Counter
import json
from pathlib import Path

from .common import atomic_bytes, canonical, fingerprint, sha256
from .config import ROOT
from .preflight import consolidate_missing, export_report


def audit_summary(audit):
    missing = consolidate_missing(audit["missing_translations"])
    by_language = {}
    diagnostics = Counter()
    for scope in audit["scopes"]:
        language = scope["language"]
        row = by_language.setdefault(language, {"variants": 0, "coverage": {}, "diagnostics": {}})
        row["variants"] += sum(scope["coverage"].values())
        for key, count in scope["coverage"].items():
            row["coverage"][key] = row["coverage"].get(key, 0) + count
        for key, count in scope["diagnostics"].items():
            row["diagnostics"][key] = row["diagnostics"].get(key, 0) + count
            diagnostics[key] += count
    variants = sum(sum(s["coverage"].values()) for s in audit["scopes"])
    return {"schema_version": 1, "registry_sha256": audit["registry_sha256"], "source": audit["source"],
            "languages": audit["languages"], "language_category_scopes": len(audit["scopes"]), "variants_audited": variants,
            "coverage": audit["coverage"], "by_language": by_language, "diagnostics": dict(diagnostics),
            "deduplicated_missing_or_invalid_keys": len(missing),
            "key_variant_links": sum(r["rendered_variant_count"] for r in missing),
            "note": "Key links can overlap when a variant requires multiple keys; they are not additional rendered variants",
            "elapsed_seconds": audit["elapsed_seconds"], "peak_observed_parent_rss": audit["peak_observed_parent_rss"],
            "unique_sources_hashed": audit["unique_sources_hashed"], "poster_renders": audit["poster_renders"],
            "scope": audit["scope"]}, missing


def sanitize(value):
    if isinstance(value, dict):
        return {key: sanitize(child) for key, child in value.items()}
    if isinstance(value, list):
        return [sanitize(child) for child in value]
    if isinstance(value, str):
        for root in (str(ROOT.parent), ROOT.parent.as_posix()):
            if value.startswith(root):
                return value[len(root):].lstrip("/\\").replace("\\", "/")
    return value


def main():
    cache = ROOT.parent / "config/package-d/cache"
    destination = Path(__file__).parent / "evidence/package-d"
    def save(name, value):
        atomic_bytes(destination / name, canonical(sanitize(value)) + b"\n", replace=True)
    refresh = json.loads((cache / "translation-refresh.json").read_text())
    save("translation-snapshot.json", refresh["snapshot"])
    networks = sorted(cache.glob("translation-network-*.json"), key=lambda p: p.stat().st_mtime_ns)
    if networks:
        save("translation-network.json", json.loads(networks[-1].read_text()))
    arabic = sorted((cache / "arabic-evaluation").glob("evidence-*.json"), key=lambda p: p.stat().st_mtime_ns)
    if arabic:
        save("arabic-candidate.json", json.loads(arabic[-1].read_text()))
        license_path = cache / "arabic-evaluation/OFL.txt"
        notice = "\n".join(line.rstrip() for line in license_path.read_text(encoding="utf-8").splitlines()) + "\n"
        atomic_bytes(destination / "arabic-candidate-OFL.txt", notice.encode("utf-8"), replace=True)
    overlay_files = sorted((cache / "overlay-parity").glob("*/evidence.json"), key=lambda p: p.stat().st_mtime_ns)
    if overlay_files:
        latest = json.loads(overlay_files[-1].read_text())
        original = json.loads((cache / "overlay-parity.json").read_text())
        save("overlay-observations.json", {"initial_cold": original["cold"], "initial_warm": original["warm"],
             "comparisons": latest["comparisons"], "jobs": original["jobs"], "groups": original["groups"], "limitations": latest["limitations"]})
    smoke = ROOT.parent / "config/package-d-smoke/smoke-evidence.json"
    if smoke.exists():
        save("focused-render-observation.json", json.loads(smoke.read_text()))
    linux = ROOT.parent / "config/package-d/linux-ci-1055/output"
    windows = ROOT.parent / "config/package-d-smoke/output"
    if linux.exists() and windows.exists():
        from PIL import Image, ImageChops
        comparisons = []
        for file in sorted(p for p in linux.rglob("*") if p.is_file()):
            relative = file.relative_to(linux)
            local = windows / relative
            with Image.open(file) as a, Image.open(local) as b:
                same_pixels = a.size == b.size and ImageChops.difference(a.convert("RGBA"), b.convert("RGBA")).getbbox(alpha_only=False) is None
            comparisons.append({"relative": relative.as_posix(), "linux_sha256": sha256(file), "windows_sha256": sha256(local), "same_decoded_rgba_pixels": same_pixels, "same_bytes": sha256(file) == sha256(local)})
        save("cross-platform-smoke.json", {"linux_run": "https://github.com/Kometa-Team/Defaults-Image-Creation/actions/runs/39005656222",
             "comparisons": comparisons, "note": "Both JPEGs are byte-identical. Both PNGs have identical decoded pixels but different compression bytes; renderer fingerprints include platform/environment."})
    audit_file = cache / "complete-audit-corrected.json"
    if not audit_file.exists():
        audit_file = cache / "complete-audit.json"
    if audit_file.exists():
        audit = json.loads(audit_file.read_text())
        summary, missing = audit_summary(audit)
        summary["raw_audit_sha256"] = sha256(audit_file)
        if audit.get("correction"):
            summary["correction"] = audit["correction"]
        summary["contributor_audit_sha256"] = fingerprint(missing)
        save("translation-audit-summary.json", summary)
        # Full affected-ID mappings stay in ignored local reports, not git.
        report = {"status": "partial" if summary["coverage"].get("blocked") else "complete", "registry_sha256": summary["registry_sha256"], "variants": [], "missing_translations": missing}
        export_report(report, cache / "contributor-audit-deduplicated" / fingerprint(missing))
        print(json.dumps(summary), flush=True)
    print("Exported compact observations only: " + str(destination), flush=True)


if __name__ == "__main__":
    main()
