"""Actual M3 candidates plus existing P3 expansion, source and target replay."""
from dataclasses import replace

from create_defaults.bulk.common import canonical, fingerprint
from create_defaults.bulk.contracts.evidence_consumption import consume, RequestContext
from create_defaults.bulk.contracts.translation_preflight import PosterRequest
from create_defaults.bulk.lifecycle.basis import historical_basis
from create_defaults.bulk.lifecycle.candidates import resolve_stable
from create_defaults.bulk.lifecycle.evidence import ReviewInputs, operation_payload
from create_defaults.bulk.lifecycle.review_authority import SyntheticReviewAuthority
from create_defaults.phase3.tests.consumption_samples import input_for, assemble
from create_defaults.phase3.tests.translation_samples import snapshot_for
from create_defaults.bulk.config import ROOT

SUBMITTER = 'synthetic.actor.submitter'
MAINTAINER = 'synthetic.actor.maintainer'


def english_snapshot():
    return snapshot_for({'en':(ROOT/'fixtures/english/en.yml').read_bytes().replace(b'\r\n',b'\n')})


def authority(row, *, same_actor=False):
    return SyntheticReviewAuthority(row[0], submitters=(SUBMITTER,),
        maintainers=(SUBMITTER if same_actor else MAINTAINER,))


def inputs(row, *, snapshot=None, context_label='explicit-complete-artwork-reverification'):
    trial, ctx, composition, _ = row
    candidate = ctx.candidate
    view = ctx.registry.view()
    resolution = resolve_stable(candidate.paths, candidate.profiles_path, view)
    items = []
    lp = None
    for identity in composition.to_dict()['required_members']:
        entry = view.entry(identity)
        package = historical_basis().package(entry['category'])
        outputs = [dict(id=identity,identity_sha256=fingerprint(entry),
            local_path=entry['names']['local_path'], public_path=entry['names']['public_path'])]
        request = PosterRequest(resolution,identity,package,package.contract.sha256,
            package.rules.sha256,entry['variant'],canonical(outputs),candidate.graph.index().outputs[identity]['context_sha256'])
        item, policy = input_for(request,snapshot=snapshot or english_snapshot(),language='en',context_label=context_label)
        if lp is not None:
            assert lp == policy
        lp = policy
        items.append(item)
    values = assemble(tuple(items), lp, graph=candidate.graph)
    op = composition.to_dict()['operation']
    request = values['request_context'].to_dict()
    request.update(id=op['id'],revision=op['revision'],request_payload_sha256=operation_payload(composition))
    assert op['revision'] == 1
    request = RequestContext.from_dict(request)
    values.update(request_context=request,expected_request_context_sha256=request.sha256)
    attestation = consume(**values)
    return ReviewInputs(ctx,composition.sha256,attestation,attestation.sha256,values)
