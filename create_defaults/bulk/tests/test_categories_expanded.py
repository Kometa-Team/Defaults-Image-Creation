"""Real M5 loader/expander/planner integration; no drawing or production state."""

from copy import deepcopy
from dataclasses import replace
import json

import pytest
import yaml

from create_defaults.bulk.common import BulkError,fingerprint
from create_defaults.bulk.config import CATEGORIES
from create_defaults.bulk.contracts.categories.validation import validate_selection,validate_overlays
from create_defaults.bulk.contracts.categories.release import Implementation,RELEASE_SHA256
from create_defaults.bulk.contracts.expanded.resolution import resolve,plan
from create_defaults.bulk.contracts.expanded.validation import approved_english,require_current
from create_defaults.bulk.contracts.adoption.models import read_canonical
from create_defaults.bulk.tests.test_categories import CASES,context


@pytest.fixture(scope="module")
def prepared(category_implementation,category_prepared):
    return category_implementation,category_prepared


def selection(tmp_path,category,prepared,*,inherit=False):
    impl,data=prepared
    cases=[c for c in CASES if c["category"]==category and not c["definition"].get("dependencies")]
    first=next(c for c in cases if category not in {"Franchise","Genre","Seasonal","Universe"} or c["job"]["raw_parameters"]["white_wash"])
    p,parts,a,member=context(first,data)
    selected=[first]+[next(c for c in CASES if c["identity"]==i) for i in member["companions"]]
    rows=[deepcopy(c["definition"]) for c in selected]
    profiles={}
    if inherit:
        rows[0]["extends"]="adversarial"
        rows[0]["composer"].pop("logo_resize")
        profiles={"adversarial":{"composer":{"logo_resize":1234}}}
    path=tmp_path/(category.lower()+".yml");profile=tmp_path/"profiles.yml"
    path.write_text(yaml.safe_dump({"schema_version":1,"category":category,"definitions":rows}),encoding="utf8")
    profile.write_text(yaml.safe_dump({"schema_version":1,"profiles":profiles}),encoding="utf8")
    current=resolve([path],profiles_path=profile)
    manifest=plan(current,approved_english(),categories=(category,))
    assignments={c["job"]["id"]:context(c,data)[2] for c in selected}
    return current,manifest,assignments


@pytest.mark.parametrize("category",[c for c in CATEGORIES if c!="Overlays"])
def test_actual_final_planner_jobs_validate_all_poster_categories(tmp_path,category,prepared):
    impl,_=prepared
    current,manifest,assignments=selection(tmp_path,category,prepared)
    report=validate_selection(impl,current,manifest,assignments,fixture_only=True)
    assert len(report["items"])==len(manifest["jobs"])
    assert not report["contract_authorized"] and not report["artifact_approved"]
    for job,item in zip(manifest["jobs"],report["items"]):
        assert require_current(item,definition=current.definition(job["poster_id"]),job=job)["current"]
    with pytest.raises(BulkError):validate_selection(impl,current,manifest,assignments)


def test_profile_inheritance_and_post_planning_resealed_jobs_cannot_bypass_rules(tmp_path,prepared):
    impl,_=prepared
    current,manifest,assignments=selection(tmp_path,"Franchise",prepared,inherit=True)
    with pytest.raises(BulkError):validate_selection(impl,current,manifest,assignments,fixture_only=True)
    current,manifest,assignments=selection(tmp_path,"Franchise",prepared)
    for field in ("white_wash","logo_offset","font_size","base_color"):
        changed=deepcopy(manifest);job=changed["jobs"][0]
        job["raw_parameters"][field]=job["parameters"][field]=False if field=="white_wash" else "#112233" if field=="base_color" else 123
        job["render_fingerprint"]=fingerprint({k:job[k] for k in ("kind","parameters","inputs","dependencies","language_behavior")} | {"renderer":changed["renderer"]})
        changed["sha256"]=fingerprint({k:v for k,v in changed.items() if k!="sha256"})
        with pytest.raises(BulkError):validate_selection(impl,current,changed,assignments,fixture_only=True)


def test_overlay_planner_replay_remains_separate_from_poster_styles(prepared):
    from create_defaults.bulk import overlays
    impl,data=prepared;first=next(c for c in CASES if c["category"]=="Overlays")
    p,parts,a,member=context(first,data)
    selected=[first,next(c for c in CASES if c["identity"]==member["companions"][0])]
    groups=(first["definition"]["group"],);sources=(member["source"]["path"],)
    manifest=overlays.plan(groups=groups,sources=sources)
    assignments={c["job"]["id"]:context(c,data)[2] for c in selected}
    report=validate_overlays(impl,manifest,assignments,groups=groups,sources=sources,fixture_only=True)
    assert len(report["items"])==2 and not report["publication_authorized"]
    changed=deepcopy(manifest);changed["jobs"]=changed["jobs"][:1]
    changed["sha256"]=fingerprint({k:v for k,v in changed.items() if k!="sha256"})
    with pytest.raises(BulkError):validate_overlays(impl,changed,assignments,groups=groups,sources=sources,fixture_only=True)
