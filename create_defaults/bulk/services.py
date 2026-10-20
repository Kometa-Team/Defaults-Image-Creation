"""Shared scope services; proposals remain separate from committed definitions."""

from .common import BulkError, fingerprint
from .definitions import Definition, merge
from .generation import generate
from .preflight import ELIGIBLE, POLICY, _metrics, effective_language, preflight, select_previews
from .common import confined, sha256
from .common import atomic_bytes
import html
import os
from pathlib import Path
from urllib.parse import quote


def propose_layout(definition, translations, language, config, *, minimum=100, maximum=250):
    """Return an explicit reviewable override, never edit YAML or silently fit."""
    if language == "en" or type(minimum) is not int or type(maximum) is not int or not 10 <= minimum <= maximum <= 500:
        raise BulkError("invalid_layout_proposal", "English typography is frozen; use explicit bounded translated size range")
    item = effective_language(definition, language)
    caption = translations.resolve(item["caption"], language)
    font = confined(config.asset_dir, item["composer"]["font"], must_exist=True)
    for size in range(maximum, minimum - 1, -1):
        metrics = _metrics(str(font), font.stat().st_mtime_ns, caption.text, size)
        if not metrics["clipped"]:
            evidence = {"policy": POLICY["layout"], "font_sha256": sha256(font), "text": caption.text, "size": size, "metrics": metrics}
            item["composer"]["font_size"] = size
            item["layout"] = {"kind": "captured_fit", "measurement": {"text": caption.text, "font_sha256": evidence["font_sha256"],
                "point_size": size, "box": [1900, 1000], "minimum": minimum, "maximum": maximum, "evidence_sha256": fingerprint(evidence)}}
            base = definition.data
            base["languages"], base["applicability"] = item["languages"], item["applicability"]
            base["output"]["remote_paths"] = item["output"]["remote_paths"]
            previous = next((o["changes"] for o in base["overrides"] if o["language"] == language), {})
            changes = {"composer": {"font_size": size}, "layout": item["layout"]}
            base["overrides"] = [o for o in base["overrides"] if o["language"] != language] + [{"language": language, "changes": merge(previous, changes)}]
            return {"state": "proposal-not-approved-or-activated", "language": language, "definition": Definition.create(base).data, "measurement": evidence}
    raise BulkError("layout_blocked", "Caption cannot fit the explicitly allowed range")


def preview(definitions, translations, *, reviews=None, explicit=(), high_risk=False, representatives=0, **options):
    options = dict(options, policy="review")
    result = generate(definitions, translations, preview_selection={"explicit": explicit, "high_risk": high_risk, "representatives": representatives}, **options)
    if reviews:
        reviews.attach(result)
    result["review_html"] = str(export_previews(result, options["config"]))
    return result


def export_previews(result, config):
    directory = config.cache_dir / "preview-reports" / result["preflight"]["sha256"]
    target = directory / "index.html"
    rendered = {j["id"] for stage in result["stages"] for j in stage["manifest"]["jobs"]}
    content = '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Poster Review</title><style>body{font:15px system-ui;margin:24px;color:#202124}article{display:grid;grid-template-columns:minmax(180px,300px) minmax(0,1fr);gap:24px;padding:24px 0;border-top:1px solid #ccc}img{width:100%;height:auto}h2,p,li{overflow-wrap:anywhere}@media(max-width:600px){article{grid-template-columns:1fr}img{max-width:280px}}.blocked{color:#ad2020}</style><h1>Poster Review</h1><p>Local previews only. Rendering does not approve or publish artwork.</p>'
    for variant in sorted(result["preflight"]["variants"], key=lambda v: (v["status"] != "blocked", v["risk"]["level"] != "high", v["poster_id"], v["language"])):
        e = lambda value: html.escape(str(value))
        content += '<article><div>'
        if variant["id"] in rendered:
            path = confined(config.output_dir, variant["local_relative"], must_exist=True)
            relative = Path(os.path.relpath(path, directory)).as_posix()
            content += '<a href="' + quote(relative, safe="/") + '"><img src="' + quote(relative, safe="/") + '" alt="' + e(variant["poster_id"] + " " + variant["language"]) + '"></a>'
        content += '</div><div><h2>' + e(variant["poster_id"]) + ' / ' + e(variant["language"]) + '</h2><p>' + e(variant["status"]) + ' | ' + e(variant["risk"]["level"]) + ' risk</p><p dir="auto">' + e(variant["caption"] or "") + '</p><ul>'
        for diagnostic in variant["diagnostics"]:
            if diagnostic["severity"] != "info":
                content += '<li>' + e(diagnostic["message"]) + '</li>'
        content += '</ul><p>Validation: <code>' + e(variant["validation_fingerprint"]) + '</code></p></div></article>'
    content += '</html>'
    if not target.exists():
        atomic_bytes(target, content.encode("utf-8"))
    return target
