"""Small permanent visual samples, separate from disposable migration outputs."""

import html
import json
import shutil

from PIL import Image, ImageDraw

from create_people_poster import digest
from jost_migration import STYLES, migration_fingerprint
from people_remote_inventory import blob_sha
from people_workspaces import atomic_json, reject_links
from compare_people_renderers import preview, compare_images


def comparison_report(migration, mid, limit=25):
    if not 1 <= limit <= 100:
        raise ValueError("Visual comparisons are limited to 1-100 selected people, never the whole collection")
    manifest = migration.load(mid)
    report_dir = migration.root / "reports" / mid
    report_dir.mkdir(parents=True, exist_ok=True)
    inventory = migration.remote()
    for style in STYLES:
        inventory.refresh(style)
    items = migration.items(mid, manifest)
    failures = [{"name":r["name"],"error":r["error"]} for r in items if r["selected"] and r["status"] in {"failed","conflict"}]
    rows = [r for r in items if r["selected"] and r["status"] in {"validated", "verified"}]
    priority = set(manifest["sample_numbers"])
    rows = sorted(rows, key=lambda r: (r["number"] not in priority, r["number"]))[:limit]
    if not rows:
        raise ValueError("Render a sample before generating comparisons")
    sections, catalog, details = [], {}, []
    for row in rows:
        number = row["number"]
        directory = report_dir / "samples" / str(number)
        reject_links(directory)
        directory.mkdir(parents=True, exist_ok=True)
        source = migration.source(manifest, row)
        with Image.open(source) as image:
            preview(image, (400, 600)).save(directory / "source-preview.png")
        cells = [f'<figure><a href="{html.escape(source.as_uri(), quote=True)}"><img src="samples/{number}/source-preview.png" alt="Transparent source"></a><figcaption>Local transparent source</figcaption></figure>']
        images, text_images, errors, differences = [], [], [], {}
        catalog[str(number)] = {}
        metrics = json.loads(row["metrics"])
        output_rows = {r["style"]: r for r in migration.outputs(mid, number)}
        for style in STYLES:
            output = migration.target(mid, row, style)
            if digest(output) != output_rows[style]["sha256"]:
                raise ValueError("Comparison input differs from the validated generated image")
            catalog[str(number)][style] = digest(output)
            new = directory / (style + "-jost.jpg")
            shutil.copyfile(output, new)
            old = directory / (style + "-existing.jpg")
            expected = row["destinations"][style]["previous_blob"]
            entry = inventory.lookup(style, row["destination"])
            current = entry["sha"] if entry else None
            have_old = False
            if expected and current == expected:
                if not old.is_file() or blob_sha(old.read_bytes()) != expected:
                    inventory.fetch_image(style, row["destination"], old)
                have_old = True
            elif expected:
                errors.append(style + ": destination changed since scan; baseline not replaced")
            else:
                errors.append(style + ": destination absent at scan")
            if have_old:
                differences[style] = compare_images(old,new)
            for label, path in (("Existing " + style, old if have_old else None), ("Jost " + style, new)):
                if path:
                    with Image.open(path) as image:
                        dimensions = list(image.size)
                        thumb = path.with_name(path.stem + "-preview.jpg")
                        canvas = preview(image, (400, 600))
                        draw = ImageDraw.Draw(canvas)
                        draw.rectangle((0, 16, 399, 132), outline="#ffcc00", width=2)
                        canvas.save(thumb, "JPEG", quality=92)
                        text = path.with_name(path.stem + "-text.png")
                        image.crop((0, 80, min(2000, image.width), min(660, image.height))).save(text)
                    relative = path.relative_to(report_dir).as_posix()
                    thumb_rel = thumb.relative_to(report_dir).as_posix()
                    text_rel = text.relative_to(report_dir).as_posix()
                    cells.append(f'<figure><a href="{relative}"><img src="{thumb_rel}" alt="{html.escape(label)}"></a><figcaption>{html.escape(label)} {dimensions}<br><a href="{text_rel}">Full-resolution text</a></figcaption></figure>')
                    text_images.append(f'<figure><a href="{text_rel}"><img src="{text_rel}" alt="{html.escape(label)} text"></a><figcaption>{html.escape(label)}</figcaption></figure>')
                    images.append({"label": label, "dimensions": dimensions, "sha256": digest(path), "blob": blob_sha(path.read_bytes())})
                else:
                    cells.append(f'<figure><figcaption>{html.escape(label)} unavailable</figcaption></figure>')
        detail = {"name": row["name"], "source_hash": row["source_hash"], "source_metrics": metrics,
                  "images": images, "differences": differences, "exceptions": errors}
        details.append(detail)
        notes = sorted(set(metrics.get("warnings",[]) + errors))
        warning = '<p class="warning">' + html.escape('; '.join(notes)) + '</p>' if notes else ''
        sections.append('<section><h2>' + html.escape(row["name"]) + '</h2>' + warning + '<div class="posters">' + ''.join(cells)
                        + '</div><details><summary>Text at full resolution</summary>' + ''.join(text_images)
                        + '</details><details><summary>Hashes, placement and warnings</summary><pre>'
                        + html.escape(json.dumps(detail, indent=2, ensure_ascii=False)) + '</pre></details></section>')
    review = {"migration": mid, "manifest_hash": json_hash_manifest(manifest), "renderer": migration_fingerprint(),
              "font": {"family": "Jost", "version": "3.710", "weight": 260, "preferred_size": 190, "sha256": manifest["font_hash"]},
              "outputs": catalog, "details": details, "failures":failures,
              "note": "Foreground bounds come from the local alpha mask, not from flattened old JPEGs. Earlier raw-cutout provenance is unverified; visual review is required."}
    atomic_json(report_dir / "review.json", review)
    token = digest(report_dir / "review.json")
    document = ('<!doctype html><html lang="en"><meta charset="utf-8"><title>Jost migration review</title>'
                '<style>body{font:15px system-ui;margin:24px;color:#222;background:#fff}h1{font-size:26px}h2{font-size:20px}section{border-top:1px solid #ccc;margin-top:28px;padding-top:12px}.warning{color:#8a3412}.posters{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px}figure{margin:0}img{max-width:100%;height:auto}figcaption{overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere}details{margin:16px 0}@media(max-width:760px){.posters{grid-template-columns:repeat(2,minmax(0,1fr))}}</style>'
                '<h1>Jost migration review</h1><p>' + html.escape(mid) + ' | Jost 260 / 190px</p><p>'
                + html.escape(review["note"]) + '</p><p>Review SHA-256: <code>' + token + '</code></p>'
                + ('<h2>Failed or conflicting inputs</h2><pre>' + html.escape(json.dumps(failures,indent=2,ensure_ascii=False)) + '</pre>' if failures else '')
                + ''.join(sections) + '</html>')
    (report_dir / "index.html").write_text(document, encoding="utf-8")
    return {"people": len(rows), "review_sha256": token, "report": str(report_dir / "index.html")}


def json_hash_manifest(manifest):
    from jost_migration import json_hash
    return json_hash(manifest)
