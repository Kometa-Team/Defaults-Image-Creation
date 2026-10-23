"""Test-only end-to-end wiring: every stage consumes the previous stage's value."""

from create_defaults.bulk.common import fingerprint
from create_defaults.bulk.contracts.language_policy import ValidationSubject
from create_defaults.bulk.contracts.destination_preflight import BoundTranslation,evaluate
from create_defaults.bulk.contracts.evidence_consumption import consume,revalidate
from create_defaults.bulk.contracts.evidence_consumption.storage import Archive
from create_defaults.phase3.tests.destination_samples import scenario


def bounds(chain):
    result=[]
    for item in chain['inputs']:
        subject=ValidationSubject.from_dict(item.report.to_dict()['subject'])
        result.append(BoundTranslation(subject,subject.sha256,item.report,item.report.sha256,
            item.request.package,item.request.contract_sha256,item.request.rules_sha256))
    return tuple(result)


def routed(chain,**options):
    selected=scenario(bounds(chain),chain['language_policy'],**options)
    report=evaluate(**selected)
    return chain|dict(destination=report,expected_destination_sha256=report.sha256,
        destination_inputs={k:v for k,v in selected.items() if k not in {'items','language_policy'}})


def changed_destination(chain,**changes):
    inputs=chain['destination_inputs']|changes
    report=evaluate(items=bounds(chain),language_policy=chain['language_policy'],**inputs)
    return chain|dict(destination=report,expected_destination_sha256=report.sha256,destination_inputs=inputs)


def assert_blocked(report):
    value=report.to_dict()
    assert value['blockers']
    for flag in ('technical_eligible','publication_authorized','production_enforcement','ready','active'):
        assert value[flag] is False
    return value


def complete_chain(chain,root):
    report=consume(**chain)
    assert report.to_dict()['chain_compatible']
    assert_blocked(report)
    archive=Archive(root)
    archive.append(report,chain['request_context'],expected_head_sha256=None,
        expected_context_sha256=chain['request_context'].sha256)
    restored=archive.history(chain['request_context'].to_dict()['id'])
    assert len(restored)==1 and restored[0].encoded==report.encoded
    assert revalidate(restored[0],expected_sha256=report.sha256,**chain).encoded==report.encoded
    # Original complete stage values accompany hashes. These are controlled
    # simulations, not a report assembled from success booleans or fake providers.
    evidence=dict(language_policy=chain['language_policy'].to_dict(),
        translations=[dict(selection=i.selection.to_dict() if i.selection else None,preflight=i.report.to_dict()) for i in chain['inputs']],
        destination=chain['destination'].to_dict(),request_context=chain['request_context'].to_dict(),
        consumption=report.to_dict(),archived_sha256=restored[0].sha256)
    return dict(evidence=evidence,sha256=fingerprint(evidence))


def integration_cases(root):
    from dataclasses import replace
    from create_defaults.phase3.tests.consumption_samples import example,assemble,input_for
    from create_defaults.phase3.tests.translation_samples import synthetic_overlay
    from create_defaults.bulk.tests.test_contract_adoption import synthetic
    cases={}
    english=example(root/'english',language='en')
    cases['official_english']=complete_chain(routed(english,official=True),root/'archive-official')
    cases['user_english']=complete_chain(routed(english),root/'archive-user')
    cases['user_french']=complete_chain(example(root/'french',language='fr'),root/'archive-french')
    cases['private_captionless']=complete_chain(example(root/'private',language='en',mode='none',public=False),root/'archive-private')
    request=synthetic_overlay();other,_=synthetic('overlay.synthetic-two','Example','bigger')
    one,lp=input_for(request);two,_=input_for(replace(request,record=other,record_sha256=other.sha256))
    cases['overlay_pair']=complete_chain(assemble((one,two),lp),root/'archive-overlays')
    return dict(schema_version=1,kind='phase3-final-integration-acceptance',simulation=True,cases=cases,
        operational_readiness=False,publication_authorized=False,production_enforcement=False,ready=False,active=False)
