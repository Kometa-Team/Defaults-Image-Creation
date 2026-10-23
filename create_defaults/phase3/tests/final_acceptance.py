"""M5 test-only whole-library projection over the existing fresh M2/M5/M6 audit.

No capture, renderer, provider or production entry point. Called inside the
mandatory historical test after every original M6/M7 assertion, using the same
verified immutable context and dependency index rather than another large audit.
"""

from collections import Counter
import hashlib

from create_defaults.bulk.common import canonical, fingerprint
from create_defaults.bulk.contracts.language_policy import LanguagePolicy
from create_defaults.bulk.contracts.translation_preflight.adapters import package_ref
from create_defaults.bulk.contracts.adoption.models import read_canonical


def reconcile_historical(implementation, registry, records, index, compatibility):
    prepared = {}
    coverage = []
    variant_members = Counter()
    for package in implementation.packages:
        contract = package.contract.to_dict()
        rules,members = package.data()
        prepared[contract['category']] = (package,contract,rules,members,package.contract.sha256,package.rules.sha256)
        for variant in contract['variants']:
            assert contract['kind']=='overlay' or 'en' in variant['design']['caption']['languages']
            coverage.append(dict(package=package_ref(package.contract),variant=variant['id'],languages=['en']))
    policy = LanguagePolicy.from_dict(dict(schema_version=1,kind='language-policy',stage='policy',id='acceptance.historical-english',
        version='1.0.0',owner='acceptance-test-only',languages=[dict(code='en',aliases=[])],coverage=coverage,
        freshness='verified-commit-and-content-with-explicit-reverification',external_authority_required=True,non_english_requires_versioned_contract=True))
    assert len(coverage)==278 and policy.resolve('en')=='en'
    assert len(prepared)==22 and len(records)==len(index.outputs)==14079 and not index.unresolved
    assert not compatibility['incompatibilities'] and not compatibility['unresolved_design_interpretations']
    digest = hashlib.sha256();digest.update(b'[')
    names = hashlib.sha256();names.update(b'[')
    seen = set();counts = Counter();exceptions = Counter();categories = Counter();private = [];context_namespaces=Counter()
    # Sort only references to immutable objects. Do not retain 14,079 detached
    # jobs/definitions or build another complete dependency graph in the parent.
    for number,record in enumerate(sorted(records,key=lambda r:r.to_dict()['identity']['id'])):
        value = record.to_dict();identity = value['identity'];key = identity['id']
        assert key not in seen;seen.add(key)
        package,contract,rules,members,contract_pin,rules_pin = prepared[identity['category']]
        member = members[key];output = index.outputs[key]
        assert member['record_sha256']==record.sha256
        assert member['variant'] in rules
        assert member['source']==identity['source']
        assert member['exceptions']==value['historical_exceptions']
        definition=read_canonical(value['effective_definition_json']);job=read_canonical(value['job_json'])
        assert member['context_sha256']==fingerprint(dict(definition=definition,job=job))
        assert output['context_sha256']==fingerprint(dict(identity=identity,definition=definition,job=job,
            exceptions=value['historical_exceptions'],renderer=value['baseline_renderer_sha256']))
        if member['context_sha256']!=output['context_sha256']:context_namespaces[contract['kind']]+=1
        assert (output['category'],output['kind'],output['local_path'],output['public_path']) == (identity['category'],contract['kind'],identity['local_path'],identity['public_path'])
        assert sorted(output['companions'])==sorted(member['companions'])
        counts[contract['kind']]+=1;categories[identity['category']]+=1
        variant_members[(identity['category'],member['variant'])]+=1
        exceptions.update(e['code'] for e in member['exceptions'])
        if identity['public_path'] is None:private.append(key)
        row=dict(id=key,identity_sha256=fingerprint(identity),record_sha256=record.sha256,
            contract_sha256=contract_pin,rules_sha256=rules_pin,variant=member['variant'],
            exception_sha256=fingerprint(member['exceptions']),source=member['source'],
            material_sha256=index.material_context(key),evidence=output['evidence'],companions=output['companions'])
        if number:digest.update(b',');names.update(b',')
        digest.update(canonical(row))
        names.update(canonical(dict(id=key,local_path=identity['local_path'],public_path=identity['public_path'])))
    digest.update(b']');names.update(b']')
    assert seen==set(index.outputs)
    assert counts==dict(poster=9957,overlay=4122) and len(private)==2
    assert all(index.outputs[key]['category']=='Awards' for key in private)
    assert set(variant_members)=={(c,v['id']) for c,(_,contract,*_) in prepared.items() for v in contract['variants']}
    assert exceptions['D09_ACCEPTED_SOURCE_PRESERVING']==56 and exceptions['D09_NORMAL_ACCEPTED_ALPHA_ASSET']==41
    from create_defaults.bulk.contracts.activation.protection import verify
    protected=verify();assert protected['production_files_verified']==190
    return dict(schema_version=1,kind='phase3-historical-acceptance',basis_sha256=registry.sha256,
        release_sha256=implementation.release.sha256,language_policy_sha256=policy.sha256,
        projection_sha256=digest.hexdigest(),exact_names_sha256=names.hexdigest(),
        outputs=len(seen),posters=counts['poster'],overlays=counts['overlay'],public_outputs=len(seen)-len(private),
        private_outputs=sorted(private),packages=len(prepared),variants=len(variant_members),
        category_outputs=dict(sorted(categories.items())),historical_exceptions=dict(sorted(exceptions.items())),
        distinct_m6_member_and_m5_graph_contexts=dict(sorted(context_namespaces.items())),
        protected=protected,unexplained_differences=0,artwork_regenerated=0,remote_writes=0,
        exact_approvals_missing=22,ready=False,active=False,production_enforcement=False,publication_authorized=False,
        operational_blockers=['live_source_verification_unavailable','authenticated_ownership_unavailable',
            'exact_contract_approvals_missing','production_integration_not_authorized'])


def export_historical(report):
    from ci.validation import identity,write,OUTPUT
    envelope = {**identity(),'evidence':report,'evidence_sha256':fingerprint(report)}
    # Already included by unchanged validation-historical artifact glob. This
    # filename cannot match the original collection/group report selectors.
    write(OUTPUT/'phase3-historical-acceptance.json',envelope)
    return envelope


def assert_actual_overlay_chain(implementation, records, graph, index=None):
    """Require one unchanged real standard/bigger pair through M2→M3→M4.

    Its authority/inventory are explicitly synthetic; original records, package,
    paths, both review-context namespaces and M5 graph are actual historical facts.
    This catches interfaces that only agree in small synthetic graph fixtures.
    """
    from create_defaults.bulk.contracts.translation_preflight import OverlayRequest
    from create_defaults.bulk.contracts.evidence_consumption import consume
    from create_defaults.phase3.tests.consumption_samples import input_for,assemble
    package=implementation.select('Overlays');_,members=package.data()
    index=index if index is not None else graph.index()
    selected=next(k for k in sorted(members) if members[k]['variant']==members[members[k]['companions'][0]]['variant'])
    identities={selected,*members[selected]['companions']}
    inputs=[];policy=None
    for record in records:
        key=record.to_dict()['identity']['id']
        if key in identities:
            request=OverlayRequest(record,record.sha256,package,package.contract.sha256,package.rules.sha256,members[key]['variant'])
            item,policy=input_for(request)
            assert item.report.to_dict()['technical_eligible']
            inputs.append(item)
    assert len(inputs)==2
    # Preserve the exact verified nodes/rows, scoped to this pair. Avoid reparsing
    # an additional whole-library graph inside each M4 replay in the large shared
    # historical process. The parent graph/projection pins are both exported.
    from create_defaults.bulk.contracts.expanded.graph import Snapshot
    closure={};pending=[index.outputs[key]['node'] for key in identities]
    while pending:
        key=pending.pop()
        if key not in closure:
            closure[key]=index.nodes[key];pending.extend(index.nodes[key]['dependencies'])
    scoped=Snapshot.create(dict(schema_version=1,kind='m5-dependency-snapshot',basis=implementation.release.to_dict()['basis_sha256'],
        nodes=closure,outputs={key:index.outputs[key] for key in identities},unresolved=[]))
    chain=assemble(inputs,policy,graph=scoped)
    assert chain['destination'].to_dict()['complete'] and chain['destination'].to_dict()['simulation_eligible']
    from ci.validation import identity,write,OUTPUT
    from create_defaults.bulk.common import BulkError
    observation=dict(pair=sorted(identities),graph_sha256=graph.sha256,scoped_graph_sha256=scoped.sha256,
        m2_technical_checks=[i.report.to_dict()['technical_eligible'] for i in inputs],
        m3_complete=chain['destination'].to_dict()['complete'],m3_simulation_eligible=chain['destination'].to_dict()['simulation_eligible'],
        contexts=[dict(id=i.request.record.to_dict()['identity']['id'],m6_member_sha256=i.request.expand('en')[0].to_dict()['review_context_sha256'],
            m5_graph_sha256=index.outputs[i.request.record.to_dict()['identity']['id']]['context_sha256']) for i in inputs])
    try:
        result=consume(**chain).to_dict()
    except BulkError as error:
        write(OUTPUT/'phase3-historical-chain.json',{**identity(),**observation,'passed':False,'error_code':error.code})
        raise
    assert result['chain_compatible'] and result['simulation_eligible']
    assert not result['ready'] and not result['active'] and not result['publication_authorized']
    # With actual current-release overlays, even replacing the graph's review
    # context with the member hash must fail. Each namespace has an exact meaning.
    import pytest
    negatives=[]
    for mutation in ('graph_context','member_context_alias','source','renderer','exception','missing_companion'):
        value=scoped.data();key=sorted(identities)[0];row=value['outputs'][key]
        if mutation=='graph_context':row['context_sha256']='f'*64
        elif mutation=='member_context_alias':
            row['context_sha256']=members[key]['context_sha256']
            value['nodes'][row['node']]['sha256']=members[key]['context_sha256']
        elif mutation=='source':
            source=members[key]['source']['path'];value['nodes']['asset:'+source]['sha256']='f'*64
        elif mutation=='renderer':value['nodes']['transform:overlay']['sha256']='f'*64
        elif mutation=='exception':
            exception=members[key]['exceptions'][0]
            value['nodes']['exception:'+key+'/'+exception['code']]['sha256']='f'*64
        else:
            # Keep the complete graph but withhold one required input/report.
            partial=assemble(inputs[:1],policy,graph=scoped)
            denied=consume(**partial).to_dict()
            assert not denied['chain_compatible'] and not denied['simulation_eligible']
            negatives.append(mutation);continue
        substituted=Snapshot.create(value)
        with pytest.raises(BulkError):consume(**(chain|dict(graph=substituted,expected_graph_sha256=substituted.sha256)))
        negatives.append(mutation)
    write(OUTPUT/'phase3-historical-chain.json',{**identity(),**observation,'passed':True,
        'consumption_sha256':fingerprint(result),'negative_controls':negatives})


def assert_actual_poster_chains(implementation, records, graph, index):
    """Replay real captioned/captionless posters without recapturing the library.

    PosterRequest explicitly selects the M5 review context. Unlike OverlayRequest
    it does not expose a historical record as an input. Independently verify the
    M6 member context here, then use the unchanged, exact M5 context in M2/M4.
    The complete historical audit above owns record membership and source checks.
    Authority and translation-currentness providers remain synthetic test data.
    """
    from dataclasses import replace
    import pytest
    from create_defaults.bulk.common import BulkError
    from create_defaults.bulk.contracts.expanded.graph import Snapshot
    from create_defaults.bulk.contracts.expanded.resolution import resolve
    from create_defaults.bulk.contracts.evidence_consumption import consume,revalidate
    from create_defaults.phase3.tests.consumption_samples import input_for,assemble
    from create_defaults.phase3.tests.translation_samples import ROOT,CATALOG,request_for,snapshot_for
    from ci.validation import identity,write,OUTPUT

    selected={}
    for record in records:
        value=record.to_dict();category=value['identity']['category']
        if category not in {'Playlist','Aspect'} or category in selected:continue
        definition=read_canonical(value['effective_definition_json'])
        if (category=='Playlist' and definition['caption']['mode']=='translation'
                or category=='Aspect' and definition['caption']['mode']=='none'):
            selected[category]=record
    assert set(selected)=={'Playlist','Aspect'}
    snapshot=snapshot_for({'en':(ROOT/'create_defaults/fixtures/english/en.yml').read_bytes()})
    observations=[]
    for category,record in sorted(selected.items()):
        value=record.to_dict();item=value['identity'];key=item['id']
        definition=read_canonical(value['effective_definition_json']);job=read_canonical(value['job_json'])
        package=implementation.select(category);_,members=package.data();member=members[key]
        member_context=fingerprint(dict(definition=definition,job=job))
        graph_context=fingerprint(dict(identity=item,definition=definition,job=job,
            exceptions=value['historical_exceptions'],renderer=value['baseline_renderer_sha256']))
        assert member['record_sha256']==record.sha256 and member['context_sha256']==member_context
        assert member['source']==item['source'] and member['exceptions']==value['historical_exceptions']
        assert graph_context==index.outputs[key]['context_sha256'] and member_context!=graph_context
        assert not member['companions'] and not index.outputs[key]['companions']
        resolution=resolve([CATALOG/(category.lower()+'.yml')])
        request=request_for(resolution,package,identity=key,variant=member['variant'])
        request=replace(request,outputs_json=canonical([dict(id=key,identity_sha256=fingerprint(item),
            local_path=item['local_path'],public_path=item['public_path'])]),review_context_sha256=graph_context)
        closure={};pending=[index.outputs[key]['node']]
        while pending:
            node=pending.pop()
            if node not in closure:
                closure[node]=index.nodes[node];pending.extend(index.nodes[node]['dependencies'])
        assert closure['output:'+key]['sha256']==graph_context
        assert closure['definition:'+key]['sha256']==fingerprint(definition)
        assert closure['transform:poster']['sha256']==value['baseline_renderer_sha256']
        for source in job['inputs']:
            assert closure['asset:'+source['path']]['sha256']==source['sha256']
        scoped=Snapshot.create(dict(schema_version=1,kind='m5-dependency-snapshot',basis=implementation.release.to_dict()['basis_sha256'],
            nodes=closure,outputs={key:index.outputs[key]},unresolved=[]))
        translation,policy=input_for(request,snapshot)
        assert translation.report.to_dict()['technical_eligible']
        assert translation.report.to_dict()['subject']['expanded_definition_sha256']==fingerprint(definition)
        chain=assemble((translation,),policy,graph=scoped);result=consume(**chain)
        report=result.to_dict()
        assert report['chain_compatible'] and report['simulation_eligible']
        assert not report['ready'] and not report['active'] and not report['publication_authorized']
        negatives=[]
        for mutation in ('member_context_alias','graph_context','definition','source','renderer','variant','membership'):
            data=scoped.data();current=chain.copy()
            if mutation=='member_context_alias':
                substituted=replace(request,review_context_sha256=member_context)
                fresh,lp=input_for(substituted,snapshot)
                current=assemble((fresh,),lp,graph=scoped)
            elif mutation=='graph_context':
                data['outputs'][key]['context_sha256']='f'*64
                data['nodes']['output:'+key]['sha256']='f'*64
            elif mutation=='definition':data['nodes']['definition:'+key]['sha256']='f'*64
            elif mutation=='source':data['nodes']['asset:'+job['inputs'][0]['path']]['sha256']='f'*64
            elif mutation=='renderer':data['nodes']['transform:poster']['sha256']='f'*64
            elif mutation=='variant':
                current['inputs']=(replace(translation,request=replace(request,variant='unapproved-variant')),)
            else:
                output=read_canonical(request.outputs_json.decode())
                output[0]['identity_sha256']='f'*64
                current['inputs']=(replace(translation,request=replace(request,outputs_json=canonical(output))),)
            if mutation in {'graph_context','definition','source','renderer'}:
                changed=Snapshot.create(data)
                current.update(graph=changed,expected_graph_sha256=changed.sha256)
            # Relevant graph source/renderer changes are bound in the original
            # consumption; replay must invalidate it even with a fresh graph pin.
            with pytest.raises(BulkError):
                revalidate(result,expected_sha256=result.sha256,**current)
            negatives.append(mutation)
        observations.append(dict(id=key,category=category,record_sha256=record.sha256,variant=member['variant'],
            caption_mode=definition['caption']['mode'],m6_member_sha256=member_context,m5_graph_sha256=graph_context,
            scoped_graph_sha256=scoped.sha256,consumption_sha256=result.sha256,
            m2_technical_eligible=True,chain_compatible=True,simulation_eligible=True,negative_controls=negatives))
    write(OUTPUT/'phase3-historical-posters.json',{**identity(),'graph_sha256':graph.sha256,
        'passed':True,'posters':observations,'ready':False,'active':False,'publication_authorized':False})
