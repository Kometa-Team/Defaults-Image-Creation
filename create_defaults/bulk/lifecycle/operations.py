"""Versioned isolated proposals. No production catalog/exporter entry point.

M5 snapshots are values, not approval. Only apply.commit_synthetic exposes a
snapshot through the original M1 journal after independent current review replay.
"""
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import json

from jsonschema import Draft202012Validator

from ..common import BulkError, canonical, fingerprint
from ..contracts.models import Document, decode_json
from ..definitions import StrictValidator
from .candidates import PosterCandidate
from .composition import CompositionContext
from .composition_models import CompositionEvidence
from .evidence import ReviewInputs
from .impact import operation_head, preview_impact
from .models import Operation
from .package_e import SidecarStore
from .review import ReviewArchive


FLAGS = dict(simulation=True, record_only=True, authenticated=False,
    operation_accepted=False, applied=False, artwork_approved=False,
    contract_approved=False, ready=False, active=False,
    production_enforcement=False, publication_authorized=False)
HEADER = dict(schema_version=1, protocol_version='1.0.0',
    kind='isolated-definition-snapshot', scope='isolated-synthetic-transactions', **FLAGS)
REFERENCE = 'synthetic.lifecycle.snapshot'
OBSERVATION_KEYS=('expected_language_policy_sha256','expected_destination_sha256',
    'expected_request_context_sha256','expected_graph_sha256','expected_release_sha256')


def fail(code):
    raise BulkError('p4m5_'+code, 'Isolated transaction rejected: '+code)


def payload(text):
    value = decode_json(text.encode('utf8'))
    if canonical(value).decode() != text:
        fail('noncanonical_payload')
    return value


def require_adapter(candidate):
    if type(candidate) is not PosterCandidate:
        fail('unsupported_prospective_phase3_adapter')
    if any(candidate.registry.view().entry(i)['category']!='Genre' for i in candidate.graph.index().outputs):
        fail('unsupported_transaction_category')
    if candidate.data()['families']:
        fail('prospective_generator_phase3_identity_adapter_required')
    if set(candidate.data()['effective_definitions'])!=set(candidate.graph.index().outputs):
        fail('unselected_definition_requires_scoped_proposal')
    from .basis import historical_basis
    for identity in candidate.graph.index().outputs:
        entry=candidate.registry.view().entry(identity)
        rule=historical_basis().rule(entry['category'],entry['variant'])
        required=['single']
        if rule['source_kind']!='logo' or rule['required_presentations']!=required:
            fail('unsupported_transaction_variant')


def observation_pins(inputs):
    """Retry identity only; stored observations never establish current trust."""
    return {n:inputs.phase3_inputs[n] for n in OBSERVATION_KEYS}


@lru_cache(maxsize=1)
def validator():
    schema = decode_json((Path(__file__).parent/'schemas/transaction-v1.schema.json').read_bytes())
    Draft202012Validator.check_schema(schema)
    return StrictValidator(schema)


class DefinitionSnapshot(Document):
    def __init__(self, value):
        raw = canonical(value)
        value = decode_json(raw)
        if next(validator().iter_errors(value), None):
            fail('schema')
        proposed = payload(value['proposed_json'])
        before = None if value['before_json'] is None else payload(value['before_json'])
        intent = Operation.from_dict(payload(value['intent_json']))
        composition = CompositionEvidence.from_dict(payload(value['composition_json']))
        from .identity_models import ImpactEvidence, entry_check
        from ..contracts.evidence_consumption import ConsumptionAttestation
        from ..contracts.expanded.graph import Snapshot
        impact = ImpactEvidence.from_dict(payload(value['impact_json']))
        phase3 = ConsumptionAttestation.from_dict(payload(value['phase3_json']))
        observations=payload(value['observation_pins_json'])
        from ..contracts.registry import require_hash
        if type(observations) is not dict or set(observations)!=set(OBSERVATION_KEYS):
            fail('observation_pin_shape')
        for pin in observations.values():require_hash(pin)
        members = value['members']
        if (members != sorted(set(members)) or sorted(value['expected_snapshots']) != members
                or sorted(value['entries']) != members or sorted(value['artwork']) != members
                or fingerprint(proposed) != value['proposed_sha256']
                or (fingerprint(before) if before is not None else None) != value['before_sha256']
                or intent.sha256 != value['operation']['sha256']
                or composition.sha256 != value['composition_sha256']
                or composition.to_dict()['operation'] != value['operation']
                or composition.to_dict()['required_members'] != members
                or intent.to_dict()['operation'] != value['operation_type']
                or (intent.to_dict()['id'],intent.to_dict()['revision']) != (value['operation']['id'],value['operation']['revision'])
                or impact.to_dict()['operation'] != value['operation']):
            fail('snapshot_binding')
        graph = Snapshot.create(payload(value['proposed_graph_json'])).data()
        if before is not None and before['graph_sha256'] != Snapshot.create(payload(value['before_graph_json'])).sha256:
            fail('before_graph_binding')
        if proposed['graph_sha256'] != fingerprint(graph) or set(graph['outputs']) != set(members):
            fail('graph_binding')
        selected = next((v for v in composition.to_dict()['views'] if v['appearance']==value['selected_appearance']), None)
        if selected is None or value['artwork'] != {m['identity']:m for m in selected['members']}:
            fail('artwork_binding')
        if value['operation_type']=='UPDATE' and before is None or (before is None)!=(value['before_graph_json'] is None):
            fail('before_required')
        if (value['operation_type']=='ADD' and any(p is not None for p in value['expected_snapshots'].values())
                or value['operation_type']=='UPDATE' and any(p is None for p in value['expected_snapshots'].values())):
            fail('expected_snapshot_kind')
        for i in members:
            entry = value['entries'][i]
            entry_check(entry)
            row = graph['outputs'][i]
            if entry['id'] != i or entry['origin'] != 'assigned' or entry['tombstone_sha256'] is not None:
                fail('unsupported_identity')
            if (entry['names']['local_path'],entry['names']['public_path']) != (row['local_path'],row['public_path']):
                fail('mapping_binding')
        object.__setattr__(self, 'encoded', raw)

    @classmethod
    def from_bytes(cls, raw):
        if type(raw) is not bytes or len(raw)>8*1024*1024:
            fail('snapshot_bound')
        result = cls.from_dict(decode_json(raw))
        if result.encoded != raw:
            fail('noncanonical_snapshot')
        return result


@dataclass(frozen=True)
class Transaction:
    """Independently selected M1-M4/P3 inputs; no caller compatibility flags."""
    inputs: ReviewInputs
    review_id: str
    review_sha256: str
    expected_snapshots_json: str

    def prepare(self):
        if type(self.inputs) is not ReviewInputs or type(self.inputs.composition) is not CompositionContext:
            fail('typed_inputs')
        ctx = self.inputs.composition
        candidate = ctx.candidate
        require_adapter(candidate)
        if ctx.before is not None and type(ctx.before) is not PosterCandidate:
            fail('unsupported_before_adapter')
        op = operation_head(ctx.registry.operations, ctx.impact.to_dict()['operation']['id'])
        if op.__dict__ != ctx.impact.to_dict()['operation']:
            fail('stale_operation')
        intent = ctx.registry.operations.history(op.id)[-1]
        v = intent.to_dict()
        if v['operation'] not in {'ADD','UPDATE'} or v['state'] not in {'draft','structurally_validated'}:
            fail('operation_not_applicable')
        details = json.loads(ctx.impact.to_dict()['details_json'])
        ids = sorted(candidate.graph.index().outputs)
        if set(details['affected_outputs']) != set(ids):
            fail('candidate_must_equal_complete_affected_members')
        if v['operation']=='UPDATE':
            if ctx.before is None:
                fail('before_required')
            a, b = details['before_mappings'], details['after_mappings']
            if set(a) != set(b) or any(a[i] != b[i] for i in a):
                fail('rename_delete_or_type_change_requires_m6')
            # Output members may be a scoped subset, but none may be invented.
            old = ctx.before.graph.index()
            if set(ids)-old.outputs.keys():
                fail('update_membership_requires_m6')
            for i in ids:
                a = next(v for v in ctx.registry.history() if v.head==ctx.before.registry_head).entry(i)
                b = ctx.registry.view().entry(i)
                if any(a['names'][f]!=b['names'][f] for f in ('display_name','rendered_caption','local_path','public_path')):
                    fail('rename_requires_m6')
                old_source,new_source=a['names']['source'],b['names']['source']
                if (old_source is None)!=(new_source is None) or old_source is not None and old_source['path']!=new_source['path']:
                    fail('source_rename_requires_m6')
        elif ctx.before is not None and set(ids)&ctx.before.graph.index().outputs.keys():
            fail('mixed_add_update')
        expected = payload(self.expected_snapshots_json)
        if type(expected) is not dict or set(expected) != set(ids):
            fail('expected_snapshot_membership')
        if (v['operation']=='ADD' and any(p is not None for p in expected.values())) or (v['operation']=='UPDATE' and any(p is None for p in expected.values())):
            fail('expected_snapshot_kind')
        archive = ReviewArchive(ctx.registry.operations.root)
        state, bundle, _ = archive.read(self.review_id, expected_sha256=self.review_sha256)
        if state.to_dict()['state'] != 'MAINTAINER_APPROVED':
            fail('complete_review_required')
        b = bundle.to_dict()
        if b['composition_sha256'] != self.inputs.composition_sha256 or b['members'] != ids:
            fail('review_membership')
        store = SidecarStore.open_readonly(ctx.registry.operations.root)
        composition = CompositionEvidence.from_bytes(store.read_object(self.inputs.composition_sha256))
        selected = next(x for x in composition.to_dict()['views'] if x['appearance']==b['selected_appearance'])
        view = ctx.registry.view()
        return DefinitionSnapshot.from_dict(dict(**HEADER, operation=op.__dict__, operation_type=v['operation'],
            intent_json=intent.encoded.decode(), before_json=ctx.before.encoded.decode() if ctx.before else None,
            before_sha256=ctx.before.sha256 if ctx.before else None,
            before_graph_json=ctx.before.graph.encoded.decode() if ctx.before else None,
            proposed_json=candidate.encoded.decode(), proposed_sha256=candidate.sha256,
            proposed_graph_json=candidate.graph.encoded.decode(), members=ids,
            entries={i:view.entry(i) for i in ids}, expected_snapshots=expected,
            impact_json=ctx.impact.encoded.decode(), composition_sha256=composition.sha256,
            composition_json=composition.encoded.decode(), selected_appearance=b['selected_appearance'],
            artwork={m['identity']:m for m in selected['members']},
            review_id=self.review_id, review_sha256=state.sha256, review_bundle_sha256=bundle.sha256,
            phase3_json=self.inputs.phase3.encoded.decode(),observation_pins_json=canonical(observation_pins(self.inputs)).decode()))


def propose(registry, *, before, candidate, identity, operation):
    """Create measured M1 intent only. Does not generate or commit artwork.

    Allocation remains the supported M2 IdentityRegistry.allocate API; loaders,
    category/contributor validation and native generation remain M2/M3 APIs.
    """
    from .impact import request_record, analyze
    if operation not in {'ADD','UPDATE'} or type(candidate) is not PosterCandidate:
        fail('unsupported_operation_adapter')
    require_adapter(candidate)
    from .recovery import inspect_db, validate_state_impact
    with registry.operations.contracts.read_connection() as db:
        state=inspect_db(registry.operations.root,registry.operations.contracts,db)
    validate_state_impact(candidate,state)
    if operation=='UPDATE':
        details = preview_impact(before,candidate)['details']
        if details['before_mappings'] != details['after_mappings']:
            fail('rename_delete_or_type_change_requires_m6')
    record = request_record(registry,before,candidate,identity=identity,operation=operation)
    registry.operations.append(record,expected_revision=0,expected_sha256=None,expected_event_sha256=None)
    op = operation_head(registry.operations,identity)
    impact = analyze(registry,before,candidate,operation=op,expected_operation_sha256=op.sha256)
    return CompositionContext(registry,before,candidate,impact,impact.sha256)


def preview(context, trial, *, exceptions=(), cancel=None):
    """Compose every required native member; this never accepts a review."""
    if type(context) is not CompositionContext:
        fail('typed_inputs')
    require_adapter(context.candidate)
    from .composition import compose
    return compose(context,trial,exceptions=exceptions,cancel=cancel)


def freeze_before(candidate, trial):
    """Rehydrate a committed proposal's exact input bytes for before replay.

    This is an isolated immutable preimage, not source fallback, rendering or a
    catalog rename. The proposed/current candidate still uses trial.config and
    must independently validate the new bytes and current registry reservation.
    """
    from dataclasses import replace
    from hashlib import sha256
    import tempfile
    from ..common import atomic_bytes, confined
    from .previews import CompositionTrial, CompositionArchive
    from .recovery import inspect_db
    if type(trial) is not CompositionTrial:
        fail('synthetic_trial_required')
    require_adapter(candidate)
    trial.require(candidate)
    store=SidecarStore.open_readonly(candidate.registry.operations.root)
    with store.read_connection() as db:
        state=inspect_db(store.root,store,db)
    selected=[]
    for i in candidate.graph.index().outputs:
        pin=state['outputs'].get(i,{}).get('snapshot_sha256')
        if pin is None or state['snapshots'][pin].to_dict()['proposed_sha256']!=candidate.sha256:
            fail('before_not_exact_committed_candidate')
        selected.append(state['snapshots'][pin])
    if not selected or len({s.sha256 for s in selected})!=1:
        fail('before_cohort_requires_explicit_adapter')
    snapshot=selected[0].to_dict()
    composition=CompositionEvidence.from_dict(payload(snapshot['composition_json']))
    assets=Path(tempfile.mkdtemp(prefix='before-assets-',dir=trial.root))
    archive=CompositionArchive(store.root,readonly=True)
    sources=composition.to_dict()['views'][0]['sources']
    for source in sources:
        raw=archive.read_bytes(source['object_sha256'])
        if sha256(raw).hexdigest()!=source['sha256']:
            fail('before_source_hash')
        path=confined(assets,source['path']);path.parent.mkdir(parents=True,exist_ok=True)
        atomic_bytes(path,raw)
    result=replace(candidate,config=replace(candidate.config,asset_dir=assets))
    # The real M2 adapter must independently reproduce the exact old candidate
    # and graph using these original bytes, never a historical compatibility flag.
    result.verify()
    return result


def stage_source_update(candidate, trial, identity, raw, *, expected_source_sha256):
    """Explicit same-name synthetic input staging, never authoritative apply.

    Keep the original immutable archive/preimage, require the exact current
    source hash, and replace only this trial's existing confined file. A crash
    here cannot expose a proposed-definition snapshot or an approval.
    """
    from hashlib import sha256 as digest
    from ..common import atomic_bytes,sha256
    from ..asset_cases import exact
    from ..contracts.logos.assets import inspect_png
    from .composition_models import MAX_BINARY
    if type(raw) is not bytes or not 0<len(raw)<=MAX_BINARY:
        fail('source_resource_bound')
    require_adapter(candidate)
    trial.require(candidate)
    if identity not in candidate.graph.index().outputs:
        fail('source_identity')
    entry=next(v for v in candidate.registry.history() if v.head==candidate.registry_head).entry(identity)
    source=entry['names']['source']
    if source is None or source['sha256']!=expected_source_sha256:
        fail('source_precondition')
    target=exact(trial.config.asset_dir,source['path'])
    if sha256(target)!=expected_source_sha256:
        fail('source_precondition')
    inspected=inspect_png(raw)
    if inspected.report()['default_transparency_blockers']:
        fail('source_transparency_requires_separate_exception_adapter')
    frozen=freeze_before(candidate,trial)
    atomic_bytes(target,raw,replace=True)
    return frozen,dict(path=source['path'],sha256=digest(raw).hexdigest())
