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
    write(OUTPUT/'phase3-historical-chain.json',{**identity(),**observation,'passed':True,'consumption_sha256':fingerprint(result)})
    assert result['chain_compatible'] and result['simulation_eligible']
    assert not result['ready'] and not result['active'] and not result['publication_authorized']
