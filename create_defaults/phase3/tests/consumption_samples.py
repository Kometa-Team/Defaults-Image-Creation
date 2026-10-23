"""Synthetic M4 evidence over real expansion and existing M1/M5 graph types."""

from dataclasses import replace
from functools import lru_cache

from create_defaults.bulk.common import canonical, fingerprint
from create_defaults.bulk.contracts.language_policy import ValidationSubject
from create_defaults.bulk.contracts.translation_preflight import evaluate as translation
from create_defaults.bulk.contracts.destination_preflight import evaluate as destination, BoundTranslation
from create_defaults.bulk.contracts.evidence_consumption import RequestContext, TranslationInput
from create_defaults.bulk.contracts.expanded.graph import Snapshot
from create_defaults.phase3.tests.translation_samples import synthetic_request, selected, SyntheticCurrent
from create_defaults.phase3.tests.destination_samples import scenario


@lru_cache(maxsize=1)
def implemented_inventory():
    from create_defaults.bulk.contracts.categories.release import Implementation, RELEASE_SHA256
    return Implementation.load(expected_sha256=RELEASE_SHA256)


def input_for(request, snapshot=None, language='en', *, verifier=None, context_label='explicit-verification'):
    lp, snapshot, selection, context = selected(request,snapshot,language,context_label=context_label)
    verifier = verifier if verifier is not None else SyntheticCurrent()
    report = translation(request,lp,language,snapshot,selection,context=context,verifier=verifier)
    return TranslationInput(request,language,snapshot,selection,report,report.sha256,context,verifier),lp


def graph_for(inputs):
    nodes,outputs = {},{}
    for item in inputs:
        subject = item.request.expand(item.requested)[0].to_dict()
        identity = subject['id']
        definition='definition:'+identity
        nodes[definition]=dict(kind='definition',identity=identity,sha256=subject['expanded_definition_sha256'],dependencies=[])
        asset='asset:logos/fixture-'+identity+'.png'
        nodes[asset]=dict(kind='asset',identity='logos/fixture-'+identity+'.png',sha256=fingerprint('synthetic-pixels-not-rendered'),dependencies=[])
        _,members=item.request.package.data()
        member=members.get(identity)
        exceptions=[]
        if member:
            for e in member['exceptions']:
                key='exception:'+identity+'/'+e['code']
                nodes[key]=dict(kind='exception',identity=identity+'/'+e['code'],sha256=e['evidence_sha256'],dependencies=[])
                exceptions.append(key)
        for output in subject['outputs']:
            key='output:'+output['id']
            nodes[key]=dict(kind='output',identity=output['id'],sha256=subject['review_context_sha256'],dependencies=sorted([asset,definition]+exceptions))
            outputs[output['id']]=dict(node=key,category=subject['contract']['category'],kind=subject['contract']['kind'],variant=subject['variant'],
                local_path=output['local_path'],public_path=output['public_path'],companions=member['companions'] if member else [],
                context_sha256=subject['review_context_sha256'],evidence=dict(previews=[],confirmations=[],decisions=[],receipts=[]))
    return Snapshot.create(dict(schema_version=1,kind='m5-dependency-snapshot',basis=fingerprint('synthetic-adoption-basis'),nodes=nodes,outputs=outputs,unresolved=[]))


def assemble(inputs, lp, *, graph=None, revision=1, previous=None, refs=()):
    inputs=tuple(inputs)
    bounds=[]
    for i in inputs:
        subject=ValidationSubject.from_dict(i.report.to_dict()['subject'])
        bounds.append(BoundTranslation(subject,subject.sha256,i.report,i.report.sha256,i.request.package,i.request.contract_sha256,i.request.rules_sha256))
    ds=scenario(bounds,lp)
    report=destination(**ds)
    context=RequestContext.from_dict(dict(schema_version=1,kind='evidence-request-context',version='1.0.0',id='fixture.lifecycle-request',
        revision=revision,previous_sha256=previous,request_payload_sha256=fingerprint(dict(intent='synthetic-M4-only',revision=revision)),
        subjects=sorted(b.subject.sha256 for b in bounds),references=list(refs)))
    graph=graph or graph_for(inputs)
    return dict(inputs=inputs,language_policy=lp,destination=report,destination_inputs={k:v for k,v in ds.items() if k not in {'items','language_policy'}},
        request_context=context,graph=graph,expected_language_policy_sha256=lp.sha256,expected_destination_sha256=report.sha256,
        expected_request_context_sha256=context.sha256,expected_graph_sha256=graph.sha256,
        implementation=implemented_inventory(),expected_release_sha256=implemented_inventory().release.sha256)


def example(path, *, language='fr', mode=None, public=True):
    request=synthetic_request(path,language=language,mode=mode)
    if public:
        import yaml
        from create_defaults.bulk.contracts.expanded.resolution import resolve
        from create_defaults.phase3.tests.translation_samples import request_for
        value=yaml.safe_load((path/'fixture.yml').read_text(encoding='utf8'))
        value['definitions'][0]['output']['remote_paths'][language]='playlist/Reviewed.png'
        (path/'fixture.yml').write_text(yaml.safe_dump(value,allow_unicode=True,sort_keys=True),encoding='utf8')
        request=request_for(resolve([path/'fixture.yml'],profiles_path=path/'profiles.yml'),request.package,language)
    item,lp=input_for(request,language=language)
    return assemble((item,),lp)


def graph_change(value, mutate):
    data=value['graph'].data()
    mutate(data)
    graph=Snapshot.create(data)
    return value|dict(graph=graph,expected_graph_sha256=graph.sha256)
