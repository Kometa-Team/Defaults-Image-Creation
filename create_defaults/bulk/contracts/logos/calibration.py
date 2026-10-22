"""Sealed synthetic controls and family-disjoint evaluation; no policy approval."""

import base64
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw

from ...common import BulkError, canonical, fingerprint
from .assets import encode_png, inspect_png
from .comparison import compare
from .wash import white_wash

HERE = Path(__file__).parent
CORPUS_SHA256 = "3d62c3fdc83f41f21d00132cedaf9b7c9d50476300807e3158c13f829576859d"


def build_corpus():
    """Development authoring only; labels arise from documented construction.

    These are synthetic reference labels, not maintainer judgments of real
    brands. No production logo is read, repaired, rendered or re-reviewed.
    """
    blobs, pairs = {}, []
    def add(image):
        raw = encode_png(image)
        h = hashlib.sha256(raw).hexdigest()
        blobs[h] = base64.b64encode(raw).decode()
        return h
    for family in range(6):
        color = Image.new("RGBA", (80+family*2, 56), (0,0,0,0))
        draw = ImageDraw.Draw(color)
        rgb = (40+family*20, 100, 190, 255)
        # Distinct family shapes, not several exports leaking across partitions.
        draw.rectangle((8,8,22,44),fill=rgb)
        draw.rectangle((12,14,18,25+family),fill=(0,0,0,0))
        draw.polygon([(32,44),(40+family,8),(51+family,44)],fill=rgb)
        draw.rectangle((62,10+family,69+family,43),fill=rgb)
        white,_ = white_wash(color)
        master = add(color)
        high = white.resize((white.width*3,white.height*3),Image.Resampling.NEAREST)
        aa = high.resize(white.size,Image.Resampling.LANCZOS)
        padded = Image.new("RGBA",(white.width+20,white.height+16));padded.paste(white,(10,8))
        missing = white.copy();ImageDraw.Draw(missing).rectangle((60,0,white.width,56),fill=(0,0,0,0))
        symbol = white.copy();ImageDraw.Draw(symbol).polygon([(53,25),(58,15),(60,29)],fill="white")
        filled = white.copy();ImageDraw.Draw(filled).rectangle((12,14,18,25+family),fill="white")
        lockup = white.copy();ImageDraw.Draw(lockup).line((22,28,65,28),fill="white",width=4)
        cases = [("exact","equivalent",white),("resolution","equivalent",high),
                 ("antialias","equivalent",aa),("padding","equivalent",padded),
                 ("missing_letter","structural_mismatch",missing),("altered_symbol","structural_mismatch",symbol),
                 ("proportions","structural_mismatch",white.resize((white.width+35,white.height),Image.Resampling.NEAREST)),
                 ("cutout_removed","structural_mismatch",filled),("clipping","structural_mismatch",white.crop((15,0,white.width,56))),
                 ("intentional_lockup","intentional_different_lockup",lockup)]
        for case,label,image in cases:
            pairs.append({"id":f"family-{family}.{case}","family":f"family-{family}","split":"calibration" if family<3 else "held_out",
                          "case":case,"label":label,"master_sha256":master,"white_sha256":add(image)})
    return {"schema_version":1,"kind":"synthetic-logo-calibration-corpus","labels":"construction-ground-truth-not-human-policy-approval",
            "families_disjoint":True,"pairs":pairs,"png_base64":blobs}


def load_corpus():
    raw = (HERE / "corpus-v1.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != CORPUS_SHA256:
        raise BulkError("logo_corpus_pin","Sealed corpus changed")
    corpus = json.loads(raw)
    groups = [{p["family"] for p in corpus["pairs"] if p["split"] == split} for split in ("calibration","held_out")]
    if groups[0] & groups[1] or not all(groups): raise BulkError("logo_corpus_leakage","Family split is not disjoint")
    for checksum,encoded in corpus["png_base64"].items():
        if inspect_png(base64.b64decode(encoded,validate=True)).sha256 != checksum:
            raise BulkError("logo_corpus_asset","Corpus PNG differs from its pin")
    return corpus


def evaluate(*, grid=64):
    corpus = load_corpus()
    assets = {h:inspect_png(base64.b64decode(data,validate=True)) for h,data in corpus["png_base64"].items()}
    measurements, summaries = [], {}
    for pair in corpus["pairs"]:
        report = compare(assets[pair["master_sha256"]], assets[pair["white_sha256"]],grid=grid)
        measurements.append(dict(pair,diagnostics=report))
    for split in ("calibration","held_out"):
        rows = [r for r in measurements if r["split"] == split]
        positives = [r for r in rows if r["label"] == "equivalent"]
        negatives = [r for r in rows if r["label"] != "equivalent"]
        summaries[split] = {"pairs":len(rows),"positive_pairs":len(positives),"negative_or_lockup_pairs":len(negatives),
            "false_matches":sum(r["diagnostics"]["outcome"] == "MATCH" for r in negatives),
            "false_mismatches":sum(r["diagnostics"]["outcome"] == "MISMATCH" for r in positives),
            "positive_manual_reviews":sum(r["diagnostics"]["outcome"] == "REVIEW REQUIRED" for r in positives),
            "negative_manual_reviews":sum(r["diagnostics"]["outcome"] == "REVIEW REQUIRED" for r in negatives),
            "measured_mismatches":sum(r["diagnostics"]["outcome"] == "MISMATCH" for r in rows),
            "automatic_matches":0,"automatic_match_coverage":0}
    return {"corpus_sha256":CORPUS_SHA256,"grid":grid,"summaries":summaries,"measurements":measurements,
            "family_disjoint":True,"approved_policy":False,"automatic_match_enabled":False,
            "limitation":"Synthetic diagnostic validation only; real maintainer labels, stability studies and exact policy approval remain required"}


def gallery(root, report):
    """Private synthetic evidence only, no official artwork filenames/destinations."""
    from html import escape
    root = Path(root)
    root.mkdir(parents=True,exist_ok=True)
    corpus = load_corpus()
    for checksum,encoded in corpus["png_base64"].items():
        path=root/(checksum+".png")
        raw=base64.b64decode(encoded,validate=True)
        if path.exists() and path.read_bytes()!=raw: raise BulkError("logo_gallery_conflict","Evidence path differs")
        path.write_bytes(raw)
    washed={}
    for pair in corpus["pairs"]:
        source=pair["master_sha256"]
        if source not in washed:
            image=inspect_png(base64.b64decode(corpus["png_base64"][source])).image()
            white,_=white_wash(image);raw=encode_png(white);h=hashlib.sha256(raw).hexdigest()
            (root/(h+".png")).write_bytes(raw);washed[source]=h
    cards=[]
    for row in report["measurements"]:
        cards.append(f'<article><h2>{escape(row["id"])}</h2><p>{escape(row["split"])} · {escape(row["label"])} · {escape(row["diagnostics"]["outcome"])}</p>'
                     f'<figure><img src="{row["master_sha256"]}.png"><figcaption>Original synthetic master</figcaption></figure>'
                     f'<figure><img src="{washed[row["master_sha256"]]}.png"><figcaption>Derived default white: unchanged renderer operation</figcaption></figure>'
                     f'<figure><img src="{row["white_sha256"]}.png"><figcaption>Separate white candidate</figcaption></figure></article>')
    (root/"review.html").write_text('<!doctype html><meta charset="utf-8"><title>M4 synthetic calibration controls</title><style>body{font:16px sans-serif;background:#ddd}article{border:1px solid #888;padding:16px;margin:16px}figure{display:inline-block;background:#567;padding:16px}img{max-width:300px;image-rendering:auto}</style><h1>Synthetic M4 controls — no policy or artwork approval</h1><p>Logo-only evidence. Families are disjoint. Original source bytes are preserved. No automatic MATCH is enabled.</p>'+''.join(cards),encoding="utf-8")
    (root/"calibration-report.json").write_bytes(canonical(report))


def stability_report():
    """Diagnostic grid-sensitivity experiment, never selection of a tolerance."""
    corpus=load_corpus();rows=[]
    for pair in corpus["pairs"]:
        if pair["case"] not in {"resolution","antialias"}:continue
        master=inspect_png(base64.b64decode(corpus["png_base64"][pair["master_sha256"]]))
        white=inspect_png(base64.b64decode(corpus["png_base64"][pair["white_sha256"]]))
        observations=[]
        for grid in (64,128):
            result=compare(master,white,grid=grid)
            observations.append({"grid":grid,"outcome":result["outcome"],"alpha_absolute_sum":result["soft_alpha_absolute_sum"],
                "sample_count":result["sample_count"],"soft_intersection_sum":result["soft_intersection_sum"],"soft_union_sum":result["soft_union_sum"]})
        rows.append({"id":pair["id"],"split":pair["split"],"observations":observations})
    return {"corpus_sha256":CORPUS_SHA256,"measurement_grids_not_acceptance_thresholds":[64,128],"pairs":rows,
            "verdict_changes":sum(r["observations"][0]["outcome"]!=r["observations"][1]["outcome"] for r in rows),
            "automatic_match_enabled":False,"approved_policy":False}
