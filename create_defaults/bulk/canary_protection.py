"""Auditable native-environment setup receipt; hidden UI settings remain manual evidence."""
from datetime import datetime,timezone
import re
from .common import BulkError

REQUIRED_HOSTED_CASES={"all_five_self_approvals","cross_approval","eligible_outside_dispatch_handled","outside_approval_denied","no_admin_bypass","trusted_branch_only","probe_secret_isolated"}


def validate_receipt(receipt, *, environment_sha, implementation, auth, now=None):
    from .canary_staging import MAINTAINERS,SOURCE,require
    require(receipt.get("verified") is True and receipt.get("method")=="github_settings_ui_and_hosted_probe", "Verified auditable environment setup receipt required")
    require(receipt.get("repository")==SOURCE and receipt.get("environment")=="english-canary-stage" and receipt.get("environment_snapshot_sha256")==environment_sha and receipt.get("implementation_commit")==implementation,"Setup receipt source/environment/version changed")
    require(receipt.get("sha256")==auth.get("setup_receipt_sha256"),"Setup receipt does not match exact staging authorization")
    inspector=receipt.get("checked_by")
    require(inspector in {"YozoraXCII","chazlarson","meisnate12","badja-dev"} and receipt.get("checked_by_id")==MAINTAINERS.get(inspector),"Setup must be inspected by a verified source administrator")
    require(receipt.get("admin_bypass_disabled_ui_observed") is True and receipt.get("ui_evidence_retained_privately") is True and re.fullmatch(r"[0-9a-f]{64}",receipt.get("ui_evidence_sha256") or ""),"Private UI no-bypass inspection evidence missing")
    require(receipt.get("source_branch_protection_reviewed") is True,"Trusted source workflow/branch protection review missing")
    require(receipt.get("hidden_setting_machine_verified") is False,"Manual UI evidence must not claim machine verification")
    try:
        checked=datetime.fromisoformat(receipt["checked_at_utc"].replace("Z","+00:00"))
        expiry=datetime.fromisoformat(receipt["expires_at_utc"].replace("Z","+00:00"))
    except (KeyError,TypeError,ValueError):raise BulkError("canary_staging_stop","Setup receipt timestamps missing/invalid") from None
    now=now or datetime.now(timezone.utc)
    require(checked.tzinfo is not None and expiry.tzinfo is not None and checked<=now<expiry and (expiry-checked).total_seconds()<=86400,"Stale/overlong setup inspection receipt")
    try:authorization_end=datetime.fromisoformat(auth["expires_at_utc"].replace("Z","+00:00"))
    except (KeyError,TypeError,ValueError):raise BulkError("canary_staging_stop","Setup-bound authorization expiry required") from None
    require(authorization_end.tzinfo is not None and now<authorization_end<=expiry,"Staging authorization must end within setup inspection validity")
    report=receipt.get("hosted_verification",{})
    require(report.get("verified") is True and set(report.get("passed_cases",[]))==REQUIRED_HOSTED_CASES and re.fullmatch(r"[0-9a-f]{64}",report.get("report_sha256") or ""),"Actual hosted approval verification report missing/incomplete")
    ids=report.get("run_ids",[])
    require(isinstance(ids,list) and bool(ids) and all(type(i) is int and i>0 for i in ids),"Hosted verification run IDs required")
    return {"setup_receipt_sha256":receipt["sha256"],"checked_by":inspector,"hidden_setting_machine_verified":False,"ui_evidence_sha256":receipt["ui_evidence_sha256"],"hosted_report_sha256":report["report_sha256"],"hosted_run_ids":ids}


def approval_comment(auth,run_id):
    return "english-canary-stage authorization="+auth["sha256"]+" setup="+auth["setup_receipt_sha256"]+" run="+str(run_id)+" attempt=1 setup-reviewed"


def verify_hosted_runs(receipt, implementation, get):
    """Verify positive native run/approval records; negative UI tests remain attested."""
    from .canary_staging import MAINTAINERS,SOURCE,require,check_native_approval
    self_reviewed=set();cross=False;outside=False
    ids=receipt["hosted_verification"]["run_ids"]
    require(len(ids)==len(set(ids)),"Duplicate hosted run evidence")
    for run_id in ids:
        base="repos/"+SOURCE+"/actions/runs/"+str(run_id)
        run=get(base)
        require(run.get("id")==run_id and run.get("repository",{}).get("full_name")==SOURCE and run.get("head_sha")==implementation and run.get("head_branch")=="main" and run.get("event")=="workflow_dispatch" and run.get("path")==".github/workflows/english-canary-approval-check.yml" and run.get("conclusion")=="success" and run.get("run_attempt")==1,"Hosted approval probe identity/result changed")
        proof=check_native_approval(get(base+"/approvals"),{"id":receipt["environment_id"]},expected_comment="english-canary-approval-check")
        actor=run.get("actor",{});login=actor.get("login")
        if login in MAINTAINERS:
            require(actor.get("id")==MAINTAINERS[login],"Hosted initiator identity changed")
            if any(a["login"]==login for a in proof["approvers"]):self_reviewed.add(login)
            if any(a["login"]!=login for a in proof["approvers"]):cross=True
        else:outside=True
    if not outside:
        require(receipt["hosted_verification"].get("outside_dispatch_not_applicable") is True,"Eligible outside-initiator hosted evidence missing")
        collaborators=get("repos/"+SOURCE+"/collaborators?affiliation=all&per_page=100")
        require(isinstance(collaborators,list) and 0<len(collaborators)<100,"Complete bounded collaborator inventory unavailable")
        require(all(c.get("login") in MAINTAINERS or (c.get("permissions",{}).get("push") is False and c.get("role_name") in {"read","triage"}) for c in collaborators),"An eligible outside writer exists; actual outside-dispatch test required")
    require(self_reviewed==set(MAINTAINERS) and cross,"Actual five-self/cross hosted evidence incomplete")
