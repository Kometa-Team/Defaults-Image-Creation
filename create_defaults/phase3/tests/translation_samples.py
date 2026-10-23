"""Synthetic M2 contexts over real Package E loader/expander interfaces."""

from dataclasses import replace
from functools import lru_cache
import hashlib
import json
from pathlib import Path

import yaml

from create_defaults.bulk.common import canonical, fingerprint
from create_defaults.bulk.contracts.models import Contract
from create_defaults.bulk.contracts.categories.models import Rules
from create_defaults.bulk.contracts.categories.release import Package
from create_defaults.bulk.contracts.expanded.resolution import resolve
from create_defaults.bulk.contracts.language_policy import LanguagePolicy, SourceVerificationContext
from create_defaults.bulk.contracts.translation_preflight import PosterRequest, SnapshotInput
from create_defaults.bulk.contracts.translation_preflight.adapters import package_ref
from create_defaults.bulk.contracts.translation_preflight.engine import prepare
from create_defaults.bulk.contracts.translation_preflight.sources import blob_sha, selection_value
from create_defaults.bulk.languages import LanguageSnapshot

ROOT=Path(__file__).resolve().parents[3]
CONTRACTS=ROOT/'create_defaults/bulk/contracts'
CATALOG=ROOT/'create_defaults/bulk/catalog'
KEY='key_names.TIMELINE_ORDER'
LANGUAGES=['en','fr','pt-br','nb_NO']


@lru_cache(maxsize=4)
def real_package(category='Playlist'):
    release=json.loads((CONTRACTS/'categories/data/release-v1.json').read_text())
    entry=next(e for e in release['entries'] if e['category']==category)
    contract=Contract.from_bytes((CONTRACTS/entry['contract_path']).read_bytes())
    rules=Rules.from_bytes((CONTRACTS/entry['rules_path']).read_bytes())
    assert (contract.sha256,rules.sha256)==(entry['contract_sha256'],entry['rules_sha256'])
    return Package(contract,rules)


@lru_cache(maxsize=1)
def real_resolution():
    return resolve([CATALOG/'playlist.yml'])


def request_for(resolution, package, language='en', identity=None, variant=None):
    identity=identity or next(iter(resolution.data()['expanded']))
    variant=variant or package.contract.to_dict()['variants'][0]['id']
    definition=resolution.definition(identity,language)
    outputs=[dict(id=identity,identity_sha256=fingerprint({'identity':identity}),
        local_path='/'.join(filter(None,('defaults-'+language,definition['output']['directory'],definition['output']['filename']))),
        public_path=definition['output']['remote_paths'].get(language))]
    return PosterRequest(resolution,identity,package,package.contract.sha256,package.rules.sha256,
                         variant,canonical(outputs),fingerprint('explicit-synthetic-review-context'))


def synthetic_request(tmp_path, *, language='en', caption=None, mode=None, override=None, contract_languages=None):
    base=real_resolution().definition(next(iter(real_resolution().data()['expanded'])))
    base['id']='fixture.playlist'
    base['source']=dict(kind='authored',path='fixture.yml',line=None,row_sha256=None)
    base['languages']=LANGUAGES[:]
    base['applicability']={code:dict(status='applicable',reason='Synthetic fixture, no real approval') for code in LANGUAGES}
    base['output']['remote_paths']={code:None for code in LANGUAGES}
    if caption:base['caption'].update(caption)
    if mode=='none':base['caption'].update(mode='none',key=None,template_key=None,text='',fallback=None)
    if override:base['overrides']=[dict(language=language,changes=override)]
    tmp_path.mkdir(parents=True,exist_ok=True)
    (tmp_path/'profiles.yml').write_text('schema_version: 1\nprofiles: {}\n',encoding='utf8')
    (tmp_path/'fixture.yml').write_text(yaml.safe_dump(dict(schema_version=1,category='Playlist',definitions=[base]),sort_keys=True,allow_unicode=True),encoding='utf8')
    resolution=resolve([tmp_path/'fixture.yml'],profiles_path=tmp_path/'profiles.yml')
    effective=resolution.definition(base['id'],language)
    original=real_package()
    c=original.contract.to_dict()
    c.update(version='2.0.0',owner='synthetic-maintainer')
    c['provenance'].update(actor='synthetic-maintainer',source='Synthetic M2 tests only; no real package or approval')
    design=c['variants'][0]['design']
    design['caption']['languages']=contract_languages or LANGUAGES[:]
    design['caption']['requirement']='prohibited' if mode=='none' else 'required'
    design['caption']['case']=effective['caption']['case']
    design['caption']['content_types']=[dict(id='synthetic',mode=effective['caption']['mode'],
        template='{value}',value=effective['caption']['key'] or '')]
    contract=Contract.from_dict(c)
    r=original.rules.to_dict();r.update(version='2.0.0',contract_sha256=contract.sha256)
    rules=json.loads(r['rules_json'])
    rule=rules['timeline-order']
    rule['design_sha256']=fingerprint(design)
    types=json.loads(rule['caption_types_json'])
    sample=next(iter(types.values()))
    sample['definition_json']=canonical(effective['caption']).decode()
    rule['caption_types_json']=canonical({'synthetic':sample}).decode()
    r['rules_json']=canonical(rules).decode()
    package=Package(contract,Rules.from_dict(r))
    return request_for(resolution,package,language)


def policy_for(request):
    return LanguagePolicy.from_dict(dict(schema_version=1,kind='language-policy',stage='policy',id='fixture.language-policy',
        version='1.0.0',owner='synthetic-maintainer',languages=[dict(code=code,aliases={'pt-br':['pt_BR'],'nb_NO':['nb-NO']}.get(code,[])) for code in LANGUAGES],
        coverage=[dict(package=package_ref(request.package.contract),variant=request.variant,languages=LANGUAGES[:])],
        freshness='verified-commit-and-content-with-explicit-reverification',external_authority_required=True,
        non_english_requires_versioned_contract=True))


def snapshot_for(resources=None):
    resources=resources if resources is not None else {'en':b'key_names:\n  TIMELINE_ORDER: Timeline Order\n','fr':'key_names:\n  TIMELINE_ORDER: Ordre chronologique\n'.encode()}
    repo=dict(host='github.com',repository_id=101,owner_id=1101,name='Fixture/Translations')
    records=[];raw=[]
    for code,data in sorted(resources.items()):
        records.append(dict(native_code=code,code=code,display_name=None,resource='defaults/'+code+'.yml',
            sha256=hashlib.sha256(data).hexdigest(),git_blob=blob_sha(data),size=len(data),availability='available',
            components=['defaults'],font_support='requires_variant_preflight'))
        raw.append(('defaults/'+code+'.yml',data))
    snapshot=LanguageSnapshot.create(records,provenance=dict(kind='verified-git-blobs',repository=repo['name'],commit='a'*40,tree='b'*40))
    return SnapshotInput(snapshot,canonical(repo),tuple(raw))


def selected(request, snapshot=None, requested='en', *, status='verified', context_label='explicit-verification'):
    snapshot=snapshot or snapshot_for()
    policy=policy_for(request)
    vs,*_,keys=prepare(request,policy,requested)
    selection=selection_value(policy,vs,requested,snapshot,keys,verification=dict(status=status,issuer='synthetic-source',
        issuer_version='1.0.0',context_sha256=fingerprint(context_label),checked_at='2030-01-01T00:00:00Z',synthetic=True))
    context=None
    if selection:
        ts=selection.to_dict();claim=ts['verification']
        context=SourceVerificationContext(selection_sha256=selection.sha256,source_sha256=fingerprint(ts['source']),
            verification_context_sha256=claim['context_sha256'],commit=ts['source']['commit'],tree=ts['source']['tree'],
            issuer=claim['issuer'],issuer_version=claim['issuer_version'],as_of=claim['checked_at'])
    return policy,snapshot,selection,context


class SyntheticCurrent:
    def verify(self,selection,context):return 'synthetic-current'


def synthetic_overlay():
    """Reuse existing M2 strict synthetic records, not another full audit capture."""
    from create_defaults.bulk.tests.test_contract_adoption import synthetic
    from create_defaults.bulk.contracts.translation_preflight import OverlayRequest
    a,_=synthetic('overlay.synthetic-one','Example','standard')
    b,_=synthetic('overlay.synthetic-two','Example','bigger')
    original=real_package('Overlays')
    c=original.contract.to_dict();r=original.rules.to_dict()
    c.update(version='2.0.0',owner='synthetic-maintainer')
    c['provenance'].update(actor='synthetic-maintainer',source='M2 synthetic overlay fixture; no real approval')
    variant=c['variants'][0];variant['id']='synthetic';variant['design']['source_branch']='synthetic'
    c['variants']=[variant]
    contract=Contract.from_dict(c)
    rule=next(iter(json.loads(r['rules_json']).values()))
    rule.update(design_sha256=fingerprint(variant['design']),companion_variants=['synthetic'],source_roots=['logos'])
    members={}
    for record,other in [(a,b),(b,a)]:
        v=record.to_dict()
        members[v['identity']['id']]=dict(record_sha256=record.sha256,variant='synthetic',presentation=v['observed_variant'],
            companions=[other.to_dict()['identity']['id']],source=v['identity']['source'],exceptions=[],
            context_sha256=fingerprint({'definition':json.loads(v['effective_definition_json']),'job':json.loads(v['job_json'])}))
    r.update(version='2.0.0',contract_sha256=contract.sha256,rules_json=canonical({'synthetic':rule}).decode(),members_json=canonical(members).decode())
    package=Package(contract,Rules.from_dict(r))
    return OverlayRequest(a,a.sha256,package,contract.sha256,package.rules.sha256,'synthetic')
