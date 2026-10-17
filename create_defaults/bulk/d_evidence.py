"""Explicit development evidence runs. No publication, approval or production cutover."""

import argparse
import base64
from collections import Counter
import gc
import html
import json
from pathlib import Path
import time

from PIL import Image, ImageChops, ImageStat
import psutil

from create_defaults.poster_text import FontLayout
from .catalog import load_catalog
from .common import atomic_bytes, canonical, fingerprint, sha256
from .config import CATEGORIES, Config, ROOT
from .generators import GENERATORS
from .languages import LanguageSnapshot, refresh, translations_from_snapshot
from .preflight import export_report, preflight
from .remote import ReadOnlyGitHub


def save(path, value):
    atomic_bytes(path, canonical(value) + b"\n")


def audit(config, snapshot):
    translated = translations_from_snapshot(snapshot, config.cache_dir / "translations")
    started = time.perf_counter()
    resources, summaries, missing, coverage = {}, [], [], Counter()
    process = psutil.Process()
    peak = process.memory_info().rss
    for category in CATEGORIES:
        if category == "Overlays":
            continue
        definitions = load_catalog([category])
        from .planner import Planner
        prepared = Planner(config, generators=GENERATORS).expand(definitions)
        for language in snapshot.select(["all"]):
            report, effective = preflight(definitions, translated, config=config, generators=GENERATORS, categories=[category],
                                          languages=[language], registry=snapshot, policy="audit", resources=resources, prepared=prepared)
            summary = {"category": category, "language": language, "sha256": report["sha256"], "coverage": report["coverage"], "metrics": report["metrics"],
                       "diagnostics": dict(Counter(d["code"] for v in report["variants"] for d in v["diagnostics"] if d["severity"] != "info"))}
            summaries.append(summary)
            missing.extend(report["missing_translations"])
            coverage.update(report["coverage"])
            peak = max(peak, process.memory_info().rss)
            print(json.dumps(summary), flush=True)
            del report, effective
            gc.collect()
    result = {"schema_version": 1, "registry_sha256": snapshot.fingerprint, "source": snapshot.data["provenance"],
              "languages": list(snapshot.select(["all"])), "scopes": summaries, "coverage": dict(coverage), "missing_translations": missing,
              "elapsed_seconds": time.perf_counter() - started, "peak_observed_parent_rss": peak, "unique_sources_hashed": len(resources["hashes"]),
              "poster_renders": 0, "scope": "All 21 categories, all discovered poster resources; validation only, not Package E production rendering"}
    save(config.cache_dir / "complete-audit.json", result)
    export_report({"status": "partial" if coverage.get("blocked") else "complete", "registry_sha256": snapshot.fingerprint,
                   "variants": [], "missing_translations": missing}, config.cache_dir / "contributor-audit")
    return result


def arabic(config):
    client = ReadOnlyGitHub("google/fonts")
    font_blob = "f1d01edce4ebaedcbe9a06fc75fec07b304ec3df"
    license_blob = "14c589f6384505ede3f8e52627d397513af3662d"
    target = config.cache_dir / "arabic-evaluation"
    target.mkdir(parents=True, exist_ok=True)
    for name, blob in (("NotoSansArabic[wdth,wght].ttf", font_blob), ("OFL.txt", license_blob)):
        path = target / name
        if not path.exists():
            response = client.blob(blob)
            data = base64.b64decode(response["content"].replace("\n", ""), validate=True)
            from create_people_posters.github_inventory_core import blob_sha
            if response["sha"] != blob or blob_sha(data) != blob:
                raise ValueError("Candidate Git blob verification failed")
            atomic_bytes(path, data)
        from create_people_posters.github_inventory_core import blob_sha
        if blob_sha(path.read_bytes()) != blob:
            raise ValueError("Cached candidate/license differs from official Git blob")
    path = target / "NotoSansArabic[wdth,wght].ttf"
    layout = FontLayout(path)
    samples = ["\u0643\u062a\u0627\u0628", "\u0628\u0646\u0627\u0621\u064b \u0639\u0644\u0649 \u0643\u062a\u0627\u0628", "\u0623\u0641\u0644\u0627\u0645 Kometa 2026", "\u0627\u0644\u062c\u0648\u0627\u0626\u0632: (2025) - 12!", "\u0623\u064e\u0641\u0652\u0644\u064e\u0627\u0645\u064c"]
    probes = []
    for index, text in enumerate(samples):
        layout.validate(text)
        image, metrics = layout.caption(text, 180, "white")
        file = target / ("probe-" + str(index) + ".png")
        if not file.exists():
            image.save(file)
        shaped = layout.positions(text, 180)[0]
        isolated = [glyph for character in text for glyph, _, _ in layout.positions(character, 180)[0]]
        probes.append({"text": text, "metrics": metrics, "shaped_glyph_count": len(shaped), "shaped_glyphs_sha256": fingerprint(shaped),
                       "joining_changes_isolated_sequence": [g for g, _, _ in shaped] != isolated, "image_sha256": sha256(file), "file": file.name})
    result = {"status": "candidate-evaluated-not-approved", "source": "https://github.com/google/fonts/tree/main/ofl/notosansarabic",
              "upstream": "https://github.com/notofonts/arabic", "font_git_blob": font_blob, "font_sha256": sha256(path),
              "license_git_blob": license_blob, "license_sha256": sha256(target / "OFL.txt"), "license": "SIL OFL 1.1; copyright 2022 The Noto Project Authors",
              "probes": probes, "production_status": "RTL variants blocked: font selection, layout overrides and mixed-bidi/anchor visual approval required",
              "shaping": "Existing FontLayout: uharfbuzz + python-bidi, exact font outlines; no OS fallback"}
    snapshot_file = config.cache_dir / "translation-refresh.json"
    if snapshot_file.exists():
        pinned = json.loads(snapshot_file.read_text())
        registry = LanguageSnapshot.load(pinned["metrics"]["snapshot_file"])
        translated = translations_from_snapshot(registry, config.cache_dir / "translations")
        strings = []
        def collect(value):
            if isinstance(value, dict):
                for child in value.values():
                    collect(child)
            elif isinstance(value, str) and value.strip():
                strings.append(value)
        collect(translated.sources.get("ar", {}))
        import unicodedata
        points = {ord(char) for text in strings for char in unicodedata.normalize("NFC", text) if char not in "\n\r\t" and unicodedata.category(char) != "Cf"}
        result["resource_glyph_coverage"] = {"scope": "All nonempty pinned defaults/ar.yml strings, a superset of poster keys; not visual language acceptance",
            "snapshot": registry.fingerprint, "strings": len(strings), "distinct_codepoints": len(points),
            "missing_codepoints": ["U+" + format(point, "04X") for point in sorted(points - layout.cmap.keys())]}
    save(target / ("evidence-" + fingerprint(result) + ".json"), result)
    content = '<!doctype html><meta charset="utf-8"><title>Arabic Font Candidate</title><style>body{font:16px system-ui;background:#222;color:#fff}img{max-width:100%;background:#333}</style><h1>Noto Sans Arabic: Not Approved</h1>'
    for probe in probes:
        content += '<h2 dir="auto">' + html.escape(probe["text"]) + '</h2><img src="' + probe["file"] + '" alt="Arabic shaping probe">'
    if not (target / "index.html").exists():
        atomic_bytes(target / "index.html", content.encode())
    return result


def overlay_parity(config):
    from .overlays import generate
    from .workers import WorkerLimits
    baseline = ROOT.parent / "config/phase1-validation-20261016/representative-final"
    sources = []
    for name in ("overlay-standard-genre", "overlay-standard-network"):
        result = json.loads((baseline / name / "result.json").read_text())
        sources.append(Path(result["parameters"]["logo"]).relative_to(ROOT).as_posix())
    catalog = json.loads((Path(__file__).parent / "catalog/overlays-v1.json").read_text())
    sources.extend(group["inputs"][0] for group in catalog["groups"])
    sources = sorted(set(sources))
    cold = generate(config, sources=sources, limits=WorkerLimits(workers=2, recycle_after=20))
    warm = generate(config, sources=sources, limits=WorkerLimits(workers=2, recycle_after=20))
    comparisons = []
    visual = '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Overlay Comparison</title><style>body{font:15px system-ui;margin:24px}.pair{display:flex;gap:24px;flex-wrap:wrap}.pair div{padding:20px;background:#222;color:white}.pair img{max-width:100%;object-fit:contain}pre{white-space:pre-wrap}</style><h1>Overlay Comparison</h1><p>Preserved ImageMagick references and current Python. Differences are measured, not silently accepted.</p>'
    for name in ("overlay-standard-genre", "overlay-bigger-genre", "overlay-standard-network", "overlay-bigger-network"):
        captured = json.loads((baseline / name / "result.json").read_text())
        source = Path(captured["parameters"]["logo"])
        if sha256(source) not in captured["input_hashes"].values():
            raise ValueError("Historical overlay source bytes changed")
        legacy = baseline / name / "legacy.png"
        if sha256(legacy) != captured["images"]["legacy"]["sha256"]:
            raise ValueError("Historical reference bytes changed")
        current = config.output_dir / captured["expected_destination"]
        with Image.open(legacy) as left, Image.open(current) as right:
            a, b = left.convert("RGBA"), right.convert("RGBA")
            item = {"case": name, "source_sha256": sha256(source), "legacy_sha256": sha256(legacy), "python_sha256": sha256(current),
                    "legacy_dimensions": list(a.size), "python_dimensions": list(b.size), "legacy_reference": "Preserved Phase 1 representative-final, not newly rerun ImageMagick"}
            if a.size == b.size:
                difference = ImageChops.difference(a, b)
                means = ImageStat.Stat(difference).mean
                item.update(rgb_mae=sum(means[:3]) / 3, alpha_mae=means[3], maximum_rgba_difference=max(v[1] for v in difference.getextrema()),
                            rgba_pixel_identical=difference.getbbox(alpha_only=False) is None)
                for color in ("black", "white"):
                    bg = Image.new("RGBA", a.size, color)
                    visible = ImageChops.difference(Image.alpha_composite(bg, a).convert("RGB"), Image.alpha_composite(bg, b).convert("RGB"))
                    item["composited_" + color + "_rgb_mae"] = sum(ImageStat.Stat(visible).mean) / 3
            comparisons.append(item)
            import os
            from urllib.parse import quote
            directory = config.cache_dir / "overlay-review"
            left_url = quote(Path(os.path.relpath(legacy, directory)).as_posix(), safe="/")
            right_url = quote(Path(os.path.relpath(current, directory)).as_posix(), safe="/")
            visual += '<h2>' + html.escape(name) + '</h2><div class="pair"><div><p>Legacy</p><img src="' + left_url + '" alt="Legacy overlay"></div><div><p>Python</p><img src="' + right_url + '" alt="Python overlay"></div></div><pre>' + html.escape(json.dumps(item, indent=2)) + '</pre>'
    result = {"status": "rendered-differences-retained-for-review", "jobs": len(cold["manifest"]["jobs"]), "groups": len(catalog["groups"]),
              "cold": cold["execution"]["metrics"], "warm": warm["execution"]["metrics"], "comparisons": comparisons,
              "limitations": "Pillow Lanczos is not ImageMagick Lanczos; raw pixel differences are reported, not hidden by changed thresholds"}
    evidence = config.cache_dir / "overlay-parity" / fingerprint(result)
    save(evidence / "evidence.json", result)
    atomic_bytes(config.cache_dir / "overlay-review/index.html", visual.encode(), replace=True)
    return result


def smoke():
    """Small offline, real-composer CI artifact, not a production benchmark."""
    import yaml
    from .definitions import Definition
    from .languages import local_snapshot
    from .overlays import generate as overlays
    from .preflight import variant_id
    from .review import Reviews
    from .services import preview, propose_layout
    from .state import Store
    from .translations import Translations
    from .workers import WorkerLimits
    root = ROOT.parent / "config/package-d-smoke"
    config = Config(cache_dir=root / "cache", workspace_dir=root / "work", output_dir=root / "output")
    definition = load_catalog(posters=["based.based-book.217e49bd"])[0]
    source = root / "fr.yml"
    if not source.exists():
        # Read-only source excerpt: Translations a7bddf45, defaults/fr.yml.
        atomic_bytes(source, yaml.safe_dump({"key_names": {"based_on_a_book": "Bas\u00e9s sur un livre"}}, allow_unicode=False).encode())
    translated = Translations({"en": ROOT / "fixtures/english/en.yml", "fr": source})
    proposal = propose_layout(definition, translated, "fr", config)
    save(root / "layout-proposal.json", proposal)
    reviews = Reviews(Store(config.cache_dir / "state.sqlite"), config)
    previewed = preview((Definition.create(proposal["definition"]),), translated, config=config, posters=[definition.id], languages=["en", "fr", "ar"],
        reviews=reviews, explicit=[variant_id(definition.id, "en"), variant_id(definition.id, "fr")], limits=WorkerLimits(workers=2))
    overlaid = overlays(config, groups=["genre"], sources=["logos_genre/Experimental.png"], limits=WorkerLimits(workers=2))
    reviews.attach(overlaid)
    batch = reviews.batch([v["id"] for v in previewed["preflight"]["variants"]] + [v["id"] for v in overlaid["preflight"]["variants"]], scope="Offline CI smoke; no images individually inspected or approved")
    start = time.perf_counter()
    items = reviews.query()
    query_seconds = time.perf_counter() - start
    result = {"scope": "Two real poster previews, two overlays, one blocked missing-resource variant; not full production throughput",
        "poster_status": previewed["status"], "poster_preflight": previewed["preflight"]["metrics"],
        "poster_workers": [s["execution"]["metrics"] for s in previewed["stages"]], "overlay_workers": overlaid["execution"]["metrics"],
        "review_query_seconds": query_seconds, "review_items": len(items), "batch": batch,
        "preview_html": str(Path(previewed["review_html"]).relative_to(root)), "approved": 0, "published": 0}
    save(root / "smoke-evidence.json", result)
    print(json.dumps(result), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["audit", "arabic", "overlays", "refresh", "smoke"])
    args = parser.parse_args()
    root = ROOT.parent / "config/package-d"
    config = Config(cache_dir=root / "cache", workspace_dir=root / "work", output_dir=root / "output")
    if args.action == "smoke":
        smoke()
        return
    if args.action == "refresh":
        from .languages import observed_client
        snapshot, metrics = refresh(config.cache_dir / "translations", observed_client())
        record = {"snapshot": snapshot.data, "metrics": metrics}
        save(config.cache_dir / ("translation-refresh-" + fingerprint(record) + ".json"), record)
        if not (config.cache_dir / "translation-refresh.json").exists():
            save(config.cache_dir / "translation-refresh.json", record)
        print(json.dumps(metrics), flush=True)
        return
    if args.action == "audit":
        evidence = json.loads((config.cache_dir / "translation-refresh.json").read_text())
        snapshot = LanguageSnapshot.load(evidence["metrics"]["snapshot_file"])
        result = audit(config, snapshot)
        print(json.dumps({k: v for k, v in result.items() if k not in {"scopes", "missing_translations"}}), flush=True)
    else:
        print(json.dumps(arabic(config) if args.action == "arabic" else overlay_parity(config)), flush=True)


if __name__ == "__main__":
    main()
