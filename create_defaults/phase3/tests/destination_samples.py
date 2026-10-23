"""Test-only trusted observations. No provider is exported by the M3 package."""

from dataclasses import replace
import json

import yaml

from create_defaults.bulk.common import canonical, fingerprint
from create_defaults.bulk.contracts.language_policy import DestinationPolicy, DestinationEvidence, AuthorityContext, reference
from create_defaults.bulk.contracts.language_policy.simulation import SyntheticAuthority
from create_defaults.bulk.contracts.destination_preflight import BoundTranslation, DestinationFacts, DestinationInventory
from create_defaults.bulk.contracts.destination_preflight.bindings import cohort
from create_defaults.bulk.contracts.destination_preflight.inventory import tree_sha, git_object
from create_defaults.bulk.contracts.destination_preflight.authority import REQUIRED_PERMISSIONS
from create_defaults.bulk.contracts.expanded.resolution import resolve
from create_defaults.bulk.contracts.translation_preflight import evaluate as translations
from create_defaults.phase3.tests.translation_samples import (
    synthetic_request,request_for,selected,snapshot_for,SyntheticCurrent,policy_for,synthetic_overlay,
)

OFFICIAL=dict(host='github.com',repository_id=102,owner_id=1102,name='Fixture/Official')
USER=dict(host='github.com',repository_id=103,owner_id=1103,name='Fixture/Artwork')


def bound(request, language='en', snapshot=None):
    policy,snapshot,selection,context=selected(request,snapshot,language)
    report=translations(request,policy,language,snapshot,selection,context=context,verifier=SyntheticCurrent())
    from create_defaults.bulk.contracts.language_policy import ValidationSubject
    subject=ValidationSubject.from_dict(report.to_dict()['subject'])
    return BoundTranslation(subject,subject.sha256,report,report.sha256,request.package,request.contract_sha256,request.rules_sha256),policy


def poster(tmp_path, *, language='en', filename=None, public=True, contract_languages=None, snapshot=None, identity=None):
    request=synthetic_request(tmp_path,language=language,contract_languages=contract_languages)
    path=tmp_path/'fixture.yml'
    value=yaml.safe_load(path.read_text(encoding='utf8'))
    definition=value['definitions'][0]
    if identity:definition['id']=identity
    if filename:definition['output']['filename']=filename
    definition['output']['remote_paths'][language]=('playlist/'+definition['output']['filename']) if public else None
    path.write_text(yaml.safe_dump(value,allow_unicode=True,sort_keys=True),encoding='utf8')
    resolution=resolve([path],profiles_path=tmp_path/'profiles.yml')
    request=request_for(resolution,request.package,language)
    if snapshot is None and language not in {'en','fr'}:
        snapshot=snapshot_for({'en':b'key_names: {TIMELINE_ORDER: Timeline Order}',language:b'key_names: {TIMELINE_ORDER: Synthetic fixture only}'})
    return bound(request,language,snapshot)


def overlay_pair():
    request=synthetic_overlay()
    from create_defaults.bulk.tests.test_contract_adoption import synthetic
    b,_=synthetic('overlay.synthetic-two','Example','bigger')
    other=replace(request,record=b,record_sha256=b.sha256)
    first,policy=bound(request)
    second,_=bound(other)
    return (first,second),policy


def inventory(repo, branch, entries=None):
    """Build cryptographically consistent synthetic Git objects, no Git writes."""
    entries=entries or {}
    root={}
    for path,mode in entries.items():
        parts=path.split('/');node=root
        for part in parts[:-1]:node=node.setdefault(part,{})
        node[parts[-1]]=(mode,'d'*40)
    pages=[]
    def tree(node):
        rows=[]
        for name,data in sorted(node.items()):
            mode,sha=('040000',tree(data)) if isinstance(data,dict) else data
            rows.append(dict(name=name,mode=mode,sha=sha))
        sha=tree_sha(rows);pages.append(dict(sha=sha,entries=rows));return sha
    root_sha=tree(root)
    raw=('tree '+root_sha+'\nauthor Fixture <fixture@example.invalid> 1 +0000\ncommitter Fixture <fixture@example.invalid> 1 +0000\n\nSynthetic fixture only\n').encode()
    return DestinationInventory.from_dict(dict(schema_version=1,kind='destination-inventory',version='1.0.0',
        repository=repo,branch=branch,commit=git_object('commit',raw),tree=root_sha,commit_hex=raw.hex(),pages=sorted(pages,key=lambda p:p['sha'])))


class SyntheticDestinationAuthority(SyntheticAuthority):
    """Only imported from tests; immutable independent facts survive JSON attacks."""
    def __init__(self,facts):self.facts=facts
    def observe(self,evidence,context):return self.facts


def scenario(items, lp, *, official=False, root=None, entries=None, extra_mappings=None, repo=None, branch=None):
    items=tuple(items)
    language=items[0].subject.to_dict()['language']
    repo=repo or (OFFICIAL.copy() if official else USER.copy())
    branch=branch or ('master' if official else 'Main')
    public=sorted(o['public_path'] for i in items for o in i.subject.to_dict()['outputs'] if o['public_path'] is not None)
    mapping=dict(language=language,repository=repo,branch=branch,root=root,paths=public)
    policy=DestinationPolicy.from_dict(dict(schema_version=1,kind='destination-policy',stage='policy',id='fixture.destination-policy',
        version='1.0.0',owner='synthetic-maintainer',language_policy=reference(lp),official_repository=OFFICIAL,
        official_language='en',english_user_owned_allowed=True,external_authority_required=True,
        mappings=([mapping] if public else [])+(extra_mappings or [])))
    if not public:
        return dict(items=items,language_policy=lp,policy=policy,evidence=None,inventory=None,
            expected_policy_sha256=policy.sha256,expected_evidence_sha256=None,expected_inventory_sha256=None)
    inv=inventory(repo,branch,entries)
    target=mapping|dict(baseline_commit=inv.to_dict()['commit'],baseline_tree=inv.to_dict()['tree'],inventory_sha256=inv.sha256)
    auth=dict(status='verified',principal='fixture.submitter',issuer='fixture.verifier',issuer_version='1.0.0',
        assertion_sha256=fingerprint('external-fixture-grant'),verification_context_sha256=fingerprint('external-fixture-context'),
        verified_at='2030-01-01T00:00:00Z',expires_at='2030-01-02T00:00:00Z',
        revocation=dict(status='clear',checked_at='2030-01-01T00:00:00Z',revision_sha256=fingerprint('fixture-revocations')),synthetic=True)
    primary=next(i for i in items if any(o['public_path'] is not None for o in i.subject.to_dict()['outputs']))
    evidence=DestinationEvidence.from_dict(dict(schema_version=1,kind='destination-evidence',stage='observation',id='fixture.destination-evidence',
        version='1.0.0',subject=reference(primary.subject),destination_policy=reference(policy),target=target,authorization=auth))
    context=AuthorityContext(evidence_sha256=evidence.sha256,subject_sha256=primary.subject.sha256,destination_policy_sha256=policy.sha256,
        target_sha256=fingerprint(target),**{k:auth[k] for k in ['assertion_sha256','verification_context_sha256','principal','issuer','issuer_version']},as_of='2030-01-01T12:00:00Z')
    facts=DestinationFacts(context=context,repository_json=canonical(repo),owner_kind='organization' if official else 'user',
        principal_id=1103,official_repository_id=OFFICIAL['repository_id'],official_owner_id=OFFICIAL['owner_id'],target_sha256=fingerprint(target),
        inventory_sha256=inv.sha256,cohort_sha256=cohort(items,lp)[-1],permissions=REQUIRED_PERMISSIONS,
        revocation_revision_sha256=auth['revocation']['revision_sha256'],revocation_checked_at=auth['revocation']['checked_at'])
    return dict(items=items,language_policy=lp,policy=policy,evidence=evidence,inventory=inv,
        expected_policy_sha256=policy.sha256,expected_evidence_sha256=evidence.sha256,expected_inventory_sha256=inv.sha256,
        context=context,verifier=SyntheticDestinationAuthority(facts))
