"""M5 impact, including exact category/evidence scope; no invalidation writes."""

from ..expanded.graph import compare


def assess(previous, current, *, changed=()):
    report = compare(previous,current)
    index = current.index();old = previous.index()
    extra = index.impact(changed)
    affected = set(report["affected_outputs"]) | set(extra["affected_outputs"])
    report["affected_outputs"] = sorted(affected)
    direct=set(report["direct_outputs"]) | set(extra["direct_outputs"])
    report["direct_outputs"]=sorted(direct)
    report["transitive_outputs"]=sorted(affected-direct)
    report["required_companions"]=sorted((set(report["required_companions"]) | set(extra["required_companions"]))-affected)
    report["affected_contracts"] = sorted({(index.outputs.get(i) or old.outputs[i])["category"] for i in affected})
    report["unaffected_outputs"] = sorted((old.outputs.keys() | index.outputs.keys())-affected)
    report["unresolved"] = sorted(set(report["unresolved"]+extra["unresolved"]))
    report["impact_complete"] = not report["unresolved"]
    for key in report["evidence_requiring_review"]:
        values = report["evidence_requiring_review"][key]+extra["evidence_requiring_review"][key]
        report["evidence_requiring_review"][key] = [{"output":i,"sha256":h} for i,h in sorted({(v["output"],v["sha256"]) for v in values})]
    report["activation_blocked"] = not report["impact_complete"]
    return report
