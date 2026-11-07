"""Local canary evidence; existing destination posters are read only."""
from __future__ import annotations
import html
from pathlib import Path
import statistics
from PIL import Image, ImageChops, ImageStat
from bulk_regeneration_state import STATE, atomic_json, read_json, sha, STYLES
from create_people_poster import output_path, COLLECTION_CONFIG, FONTS

def _thumbnail(path, target):
    with Image.open(path) as image:
        image.thumbnail((200,300))
        canvas = Image.new("RGB",(200,300),"#cccccc")
        rgba = image.convert("RGBA")
        canvas.paste(rgba,((200-rgba.width)//2,(300-rgba.height)//2),rgba)
        canvas.save(target,"JPEG",quality=90)

def canary_report(root, manifest):
    root = Path(root)
    report = root/STATE/"review"
    report.mkdir(exist_ok=True)
    entries, body = [], []
    for item in manifest["items"]:
        if not item["selected"]:
            continue
        source = Path(manifest["source"])/item["relative"]
        source_preview = str(item["number"])+"-source.jpg"
        _thumbnail(source,report/source_preview)
        cells = ['<td>Transparent<br><img src="'+source_preview+'"></td>']
        for style in manifest["styles"]:
            poster = output_path(root,style,item["name"])
            if not poster.exists():
                cells.append("<td>"+html.escape(style)+": missing/failed</td>")
                continue
            receipt = read_json(root/STATE/"receipts"/(poster.relative_to(root).as_posix()+".json"))
            preview = str(item["number"])+"-"+style+".jpg"
            _thumbnail(poster,report/preview)
            reference = output_path(Path(manifest["source"]).parent,style,item["name"])
            entry = dict(name=item["name"],style=style,output=str(poster),bytes=poster.stat().st_size,
                         sha256=sha(poster),source_attributes=item["attributes"],
                         collection_calls=receipt["collection_calls"].get(style,0),
                         collection_config=COLLECTION_CONFIG.get(style),warnings=receipt["warnings"],
                         person_font={"bw":FONTS[0],"signature":FONTS[1],"rainier":FONTS[0],
                                      "diiivoy":FONTS[2],"diiivoycolor":FONTS[2]}[style])
            with Image.open(poster) as image:
                entry.update(dimensions=list(image.size),mode=image.mode,format=image.format)
                # Centre subject ROI, avoiding intentionally coloured template edges.
                roi = image.convert('RGB').crop((700,1100,1300,2100))
                r,g,b = roi.split()
                entry["centre_channel_difference_mean"] = sum(ImageStat.Stat(ImageChops.difference(a,c)).mean[0]
                                                               for a,c in ((r,g),(g,b),(r,b)))/3
            extra = ""
            if reference.is_file():
                old = str(item["number"])+"-"+style+"-old.jpg"
                _thumbnail(reference,report/old)
                with Image.open(reference) as image, Image.open(poster) as candidate:
                    entry["reference_dimensions"] = list(image.size)
                    a,b = image.convert("RGB").resize((200,300)),candidate.convert('RGB').resize((200,300))
                    entry["reference_thumbnail_mae"] = statistics.mean(ImageStat.Stat(ImageChops.difference(a,b)).mean)
                entry["reference"] = str(reference)
                extra = '<br>Existing local poster<br><img src="'+old+'">'
            entries.append(entry)
            cells.append("<td>"+style+'<br><img src="'+preview+'">'+extra+"</td>")
        body.append("<h2>"+html.escape(item["name"])+"</h2><table><tr>"+"".join(cells)+"</tr></table>")
    sizes = {}
    for style in manifest["styles"]:
        values = [e["bytes"] for e in entries if e["style"]==style]
        sizes[style] = dict(count=len(values),total_bytes=sum(values),mean_bytes=statistics.mean(values) if values else None,
                            max_bytes=max(values) if values else None)
    value = dict(batch_id=manifest["batch_id"],renderer=manifest["renderer"],source_git=manifest["source_git"],
                 inventory=manifest["inventory"],poster_count=len(entries),sizes=sizes,posters=entries,
                 validation_note="COLLECTION call instrumentation + existing pixel/font regression contracts. "
                   "Visual review remains required; channel metrics describe subject ROI, not a colour correction.")
    atomic_json(report/"report.json",value)
    (report/"index.html").write_text("<!doctype html><meta charset=utf-8><title>Five-style canary</title>"
        "<style>body{font:16px sans-serif;background:#eee}td{vertical-align:top;padding:10px}img{width:200px}</style>"
        "<h1>Five-style canary</h1><p>BW uses its established Comfortaa name label and no dynamic COLLECTION call. "
        "New previews above existing local references when available. "
        "References may use different subject images or legacy rendering.</p>"+"".join(body),encoding="utf8")
    return value
