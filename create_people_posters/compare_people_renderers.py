"""Generate local PowerShell/Pillow comparisons from preserved pipeline inputs."""

from __future__ import annotations

import argparse
import html
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from create_people_poster import SCRIPT_DIR, STYLES, digest, output_path, render_batch
from people_workspaces import atomic_json, reject_links


def structural_similarity(first, second):
    a = first.convert("L").resize((256, 384), Image.Resampling.LANCZOS)
    b = second.convert("L").resize(a.size, Image.Resampling.LANCZOS)
    x, y = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    # Global structural similarity is supplemented by separate label/body metrics.
    vx, vy, covariance = x.var(), y.var(), ((x - x.mean()) * (y - y.mean())).mean()
    return float((2*x.mean()*y.mean()+6.5025)*(2*covariance+58.5225) /
                 ((x.mean()**2+y.mean()**2+6.5025)*(vx+vy+58.5225)))


def compare_images(reference, candidate):
    with Image.open(reference) as ref, Image.open(candidate) as new:
        ref.load()
        new.load()
        contract = ref.size == new.size and ref.format == new.format
        if ref.format == "PNG":
            contract = contract and new.mode == "RGBA" and new.getchannel("A").getextrema()[0] < 255
        if ref.size != new.size:
            return {"contract": False, "reference_size": ref.size, "python_size": new.size}
        def visible(image):
            if "A" in image.getbands() or "transparency" in image.info:
                return Image.alpha_composite(Image.new("RGBA", image.size, (128,128,128,255)),image.convert("RGBA")).convert("RGB")
            return image.convert("RGB")
        reference_rgb, candidate_rgb = visible(ref), visible(new)
        a, b = np.asarray(reference_rgb, dtype=np.float32), np.asarray(candidate_rgb, dtype=np.float32)
        delta = np.abs(a-b)
        score = structural_similarity(reference_rgb, candidate_rgb)
        result = {"contract": contract, "dimensions": list(new.size), "format": new.format,
                  "exact_bytes": digest(reference) == digest(candidate),
                  "reference_mode": ref.mode, "python_mode": new.mode,
                  "mae": float(delta.mean()), "rmse": float(np.sqrt(((a-b)**2).mean())),
                  "ssim_global": score, "label_mae": float(delta[:min(660,len(delta))].mean()),
                  "body_mae": float(delta[min(700,len(delta)-1):].mean())}
        if "A" in ref.getbands():
            alpha_a, alpha_b = ref.convert("RGBA").getchannel("A"), new.convert("RGBA").getchannel("A")
            result.update(reference_bbox=alpha_a.getbbox(), python_bbox=alpha_b.getbbox(),
                          alpha_mae=float(np.abs(np.asarray(alpha_a,dtype=float)-np.asarray(alpha_b,dtype=float)).mean()))
        result["review"] = score < .99 or result["mae"] > 3 or result.get("alpha_mae", 0) > 1
        return result


def preview(image, size=(200, 300)):
    canvas = Image.new("RGB", size, "#cccccc")
    draw = ImageDraw.Draw(canvas)
    for y in range(0, size[1], 16):
        for x in range(0, size[0], 16):
            if (x//16+y//16) % 2:
                draw.rectangle((x,y,x+15,y+15),fill="#eeeeee")
    image = image.convert("RGBA")
    image.thumbnail(size)
    canvas.paste(image, ((size[0]-image.width)//2,(size[1]-image.height)//2),image)
    return canvas


def make_sheet(name, references, candidates, target):
    sheet = Image.new("RGB", (len(STYLES)*220, 680), "white")
    draw = ImageDraw.Draw(sheet)
    for index, style in enumerate(STYLES):
        x = index*220
        draw.text((x+8,4),style,fill="black")
        for y, paths, label in ((35,references,"ImageMagick"),(365,candidates,"Pillow")):
            draw.text((x+8,y-18),label,fill="black")
            with Image.open(paths[style]) as image:
                sheet.paste(preview(image),(x+8,y))
    sheet.save(target, "JPEG", quality=93)


def cases_from_sources(sources, variants):
    cases = []
    for config in sources:
        root = config / "people_dirs"
        originals = sorted(p for p in (root / "original").rglob("*") if p.is_file()
                           and p.suffix.lower() in {".jpg",".jpeg",".png",".webp",".bmp",".tif",".tiff"}
                           and ".history" not in p.parts)
        for original in originals:
            name = original.stem
            choices = [config / "sel_downloads" / (name+".png"), output_path(root,"transparent",name)]
            cutout = next((p for p in choices if p.is_file()), None)
            if cutout:
                cases.append({"name":name,"original":original,"cutout":cutout,"variant":"unchanged"})
    if not cases:
        raise ValueError("No paired preserved photographs/cutouts found in --source-config")
    if len({c["name"] for c in cases}) != len(cases):
        raise ValueError("Duplicate names in source configs; provide distinct jobs")
    if variants:
        base = cases[0]
        for name, variant in (("Zoe Unicode", "unicode"), ("Grayscale Portrait", "grayscale"),
                              ("Wide Portrait", "wide"), ("Edge Portrait", "edge"),
                              ("Long Name With Five Words", "long")):
            cases.append(dict(base,name=("Zo\u00eb Garc\u00eda" if variant=="unicode" else name),variant=variant))
    return cases


def stage_case(root, case):
    name = case["name"]
    with Image.open(case["original"]) as original, Image.open(case["cutout"]) as cutout:
        original, cutout = original.convert("RGB"), cutout.convert("RGBA")
        if case["variant"] == "grayscale":
            original = original.convert("L").convert("RGB")
            alpha = cutout.getchannel("A")
            cutout = cutout.convert("L").convert("RGBA")
            cutout.putalpha(alpha)
        elif case["variant"] == "wide":
            wide = Image.new("RGBA", (cutout.width*2, cutout.height))
            wide.alpha_composite(cutout, (cutout.width//2, 0))
            cutout = wide
        elif case["variant"] == "edge":
            bounds = cutout.getchannel("A").getbbox()
            if bounds:
                cutout = cutout.crop((0, bounds[1]+max(1,cutout.height//30), cutout.width, cutout.height))
        (root / "original").mkdir(parents=True, exist_ok=True)
        (root / "Downloads").mkdir(parents=True, exist_ok=True)
        original.save(root / "original" / (name+".jpg"), "JPEG", quality=95)
        cutout.save(root / "Downloads" / (name+".png"), "PNG")


def run_comparison(sources, output, variants=False):
    output = Path(output).resolve()
    reject_links(output)
    if output.exists():
        raise ValueError("Comparison output already exists; select a new directory to preserve earlier evidence")
    ps = shutil.which("pwsh") or (shutil.which("powershell") if os.name=="nt" else None)
    if not ps or not shutil.which("magick"):
        raise ValueError("Comparison reference requires PowerShell and ImageMagick; Python rendering itself does not")
    cases = cases_from_sources([Path(p).resolve() for p in sources],variants)
    output.mkdir(parents=True)
    provenance = []
    for engine in ("powershell", "python"):
        root = output / engine / "people_dirs"
        (root / "Downloads").mkdir(parents=True)
        (root / "original").mkdir()
        for case in cases:
            name = case["name"]
            stage_case(root, case)
            if engine=="python":
                provenance.append({"name":name,"variant":case["variant"],"source_photo":str(case["original"]),
                                   "source_cutout":str(case["cutout"]),"photo_sha256":digest(case["original"]),"cutout_sha256":digest(case["cutout"])})
    env = os.environ.copy()
    env["PEOPLE_CONFIG_DIR"] = str(output / "powershell")
    started=time.perf_counter()
    with (output / "reference.log").open("w",encoding="utf-8") as log:
        result=subprocess.run([ps,"-NoLogo","-NoProfile","-ExecutionPolicy","Bypass","-File",str(SCRIPT_DIR / "create_people_poster.ps1")],
                              env=env,cwd=SCRIPT_DIR,stdout=log,stderr=subprocess.STDOUT,timeout=1800)
    ps_seconds=time.perf_counter()-started
    if result.returncode:
        raise ValueError("PowerShell reference failed; inspect reference.log")
    started=time.perf_counter()
    python_report=render_batch(output / "python")
    py_seconds=time.perf_counter()-started
    if python_report["failed"]:
        raise ValueError("Python renderer failed; inspect python/logs/create_people_poster.json")
    comparisons=[]
    for case in cases:
        name=case["name"]
        refs={style:output_path(output / "powershell" / "people_dirs",style,name) for style in STYLES}
        news={style:output_path(output / "python" / "people_dirs",style,name) for style in STYLES}
        metrics={style:compare_images(refs[style],news[style]) for style in STYLES}
        for paths, key in ((refs,"reference_subject_bbox"),(news,"python_subject_bbox")):
            with Image.open(paths["transparent"]) as cutout:
                bounds=cutout.getchannel("A").getbbox()
                for style, measurement in metrics.items():
                    if style == "original":
                        measurement[key]=None
                    elif bounds and style not in {"transparent","signature"}:
                        shift=max(0,500-bounds[1])
                        measurement[key]=[bounds[0],bounds[1]+shift,bounds[2],min(3000,bounds[3]+shift)]
                    else:
                        measurement[key]=bounds
        for measurement in metrics.values():
            a,b=measurement["reference_subject_bbox"],measurement["python_subject_bbox"]
            measurement["subject_bbox_max_delta"]=max(abs(x-y) for x,y in zip(a,b)) if a and b else None
            measurement["bbox_method"]="derived from paired alpha mask and reference placement; original has no alpha mask"
        sheet=f'case-{len(comparisons)+1}.jpg'
        make_sheet(name,refs,news,output / sheet)
        comparisons.append({"name":name,"styles":metrics,"sheet":sheet})
        print('[COMPARED]',name,flush=True)
    report={"source_provenance":provenance,"powershell_seconds":round(ps_seconds,3),"python_seconds":round(py_seconds,3),
            "cases":comparisons,"contracts_passed":all(m["contract"] for c in comparisons for m in c["styles"].values()),
            "review_required":sum(m.get("review",True) for c in comparisons for m in c["styles"].values()),
            "note":"Metrics are screening aids, not a declaration of visual equivalence. Inspect side-by-side sheets."}
    atomic_json(output / "report.json",report)
    sections=[]
    for case in comparisons:
        rows=''.join(f'<tr><td>{html.escape(style)}</td><td>{m.get("mae",0):.3f}</td><td>{m.get("ssim_global",0):.6f}</td><td>{"REVIEW" if m.get("review",True) else "inspect"}</td></tr>' for style,m in case["styles"].items())
        sections.append(f'<h2>{html.escape(case["name"])}</h2><a href="{case["sheet"]}"><img style="max-width:100%" src="{case["sheet"]}"></a><table><tr><th>Style</th><th>MAE</th><th>Global SSIM</th><th>Review</th></tr>{rows}</table>')
    document='<!doctype html><meta charset="utf-8"><title>People Renderer Comparison</title><h1>ImageMagick / Pillow</h1><p>'+html.escape(report['note'])+'</p>'+''.join(sections)
    (output / "index.html").write_text(document,encoding="utf-8")
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-config",type=Path,nargs="+",required=True,help="Preserved local pipeline jobs; no repositories are modified")
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--variants",action="store_true",help="Also test grayscale, edge, wide, long-name and Unicode variants of a real portrait")
    args=parser.parse_args()
    try:
        report=run_comparison(args.source_config,args.output,args.variants)
        print(json.dumps({k:v for k,v in report.items() if k not in {"cases","source_provenance"}},indent=2))
        return 0 if report["contracts_passed"] else 1
    except (ValueError,OSError,subprocess.SubprocessError) as error:
        print(str(error),file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
