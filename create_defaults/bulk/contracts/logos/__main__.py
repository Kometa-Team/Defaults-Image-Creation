"""Build private, clearly synthetic M4 evidence. No approval or upload commands."""

import argparse
import base64
from html import escape
import json
from pathlib import Path

from ...common import BulkError, atomic_bytes, canonical, confined, fingerprint
from ..models import Contract, Identity
from ..adoption.models import read_canonical
from ..playlist.validation import HERE as PLAYLIST
from .calibration import HERE, evaluate, gallery, load_corpus, write_report
from .storage import LogoArchive, status
from .workflow import Selection, prepare


def generate_evidence(root):
    archive=LogoArchive(Path(root))  # Existing M1 production-root/link guards.
    root=archive.contracts.root
    report=evaluate()
    gallery(confined(root,"calibration-gallery"),report)
    corpus=load_corpus();pair=corpus["pairs"][0];raw=base64.b64decode(corpus["png_base64"][pair["master_sha256"]])
    path=confined(root,"preview-inputs/synthetic-master.png")
    try:atomic_bytes(path,raw)
    except FileExistsError:
        if path.read_bytes()!=raw:raise BulkError("logo_evidence_conflict","Synthetic evidence source differs")
    ref={"path":"preview-inputs/synthetic-master.png","sha256":pair["master_sha256"]}
    examples=[]
    for name,path,variant,category in (("playlist",PLAYLIST/"contract-v1.json","timeline-order","Playlist"),
                                       ("overlay",HERE/"overlay-fixture-v1.json","color","Overlays")):
        selected=Selection.fixture(Contract.from_bytes(path.read_bytes()),variant)
        item=Identity.from_dict({"schema_version":1,"kind":"item-identity","id":category.lower()+".m4-synthetic",
            "category":category,"display_name":"Synthetic M4 example","rendered_caption":"TIMELINE ORDER" if name=="playlist" else "",
            "source":ref,"local_path":"private/synthetic-example.png","public_path":None,"semantic_member":None})
        review=prepare(selected,source_root=root,item=item,submitter="synthetic-example-no-real-confirmation",sources={"master":ref,"white":None},
            background="#123456" if name=="playlist" else None,exception_types=["source_preserving"] if name=="playlist" else [],
            reason="Explicit M4 synthetic preview evidence only, no actual human approval",request_id="m4.example."+name)
        snap=archive.start(name,review,expected_revision=0,selection=selected,source_root=root)
        p=read_canonical(review.bundle.payload()["preview_json"])
        examples.append({"name":name,"status":status(snap,review),"snapshot_sha256":snap.sha256,"preview":p})
    cards=[]
    for example in examples:
        p=example["preview"]
        images=['<figure><img src="logo-artifacts/'+p["context"]["source"]["sha256"]+'.png"><figcaption>Original unmodified input PNG</figcaption></figure>']
        for label,panel in [("Default",p["default"]),("Requested",p["requested"])]+[(m["id"],m) for m in p["members"]]:
            images.append('<figure><img src="logo-artifacts/'+panel["artifact_sha256"]+'.png"><figcaption>'+escape(label)+' — '+escape(panel.get("validation","required member"))+'</figcaption></figure>')
        cards.append('<article><h2>'+escape(example["name"])+' — '+escape(example["status"]["preview_completeness"])+'</h2><p>Pending synthetic review; no submitter or maintainer decision.</p>'+''.join(images)+'</article>')
    text='<!doctype html><meta charset="utf-8"><title>M4 private synthetic previews</title><style>body{font:16px sans-serif;background:#ddd}figure{display:inline-block;background:#567;padding:16px;margin:10px}img{max-width:440px}article{border:1px solid #888;margin:16px;padding:16px}</style><h1>M4 isolated synthetic evidence</h1><p>No real logo/design approval. Playlist images show logo treatments only: no poster caption, background or layout compliance is asserted. Overlay previews use the existing source-preserving trim/resize renderer and both required sizes.</p><a href="calibration-gallery/review.html">60 sealed calibration controls</a>'+''.join(cards)
    write_report(root,"review.html",text.encode("utf-8"))
    summary={"examples":examples,"calibration":report["summaries"],"corpus_sha256":report["corpus_sha256"],"publication_authorized":False}
    write_report(root,"evidence-report.json",canonical(summary))
    return {"gallery":str(root/"review.html"),"report":str(root/"evidence-report.json"),"calibration":report["summaries"],"publication_authorized":False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root",required=True)
    args=parser.parse_args()
    try:print(json.dumps(generate_evidence(args.evidence_root),indent=2));return 0
    except (BulkError,OSError) as error:
        print(json.dumps({"blocked":True,"code":getattr(error,"code","io_error"),"details":str(error)}));return 2


if __name__=="__main__":raise SystemExit(main())
