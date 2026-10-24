"""Complete-composition review values and current Phase 3 evidence replay.

Integrity is not authentication. These additive values never grant real approval,
contract acceptance, lifecycle execution, READY/ACTIVE or publication authority.
"""
from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from ..common import BulkError, canonical, fingerprint
from ..contracts.models import Document, decode_json
from ..definitions import StrictValidator
from ..contracts.registry import require_hash
from ..contracts.evidence_consumption import ConsumptionAttestation, revalidate
from ..contracts.expanded.graph import Snapshot
from .composition import CompositionContext
from .previews import CompositionArchive
from .composition_models import CompositionEvidence


FLAGS = dict(simulation=True, record_only=True, authenticated=False,
    operation_accepted=False, applied=False, artwork_approved=False,
    contract_approved=False, ready=False, active=False,
    production_enforcement=False, publication_authorized=False)
HEADER = dict(schema_version=1, protocol_version='1.0.0',
    scope='isolated-synthetic-complete-review', **FLAGS)


def fail(code):
    raise BulkError('p4m4_'+code, 'Complete-poster review blocked: '+code)


def json_value(value):
    result = decode_json(value.encode('utf-8'))
    if canonical(result).decode('utf-8') != value:
        fail('noncanonical_payload')
    return result


@lru_cache(maxsize=3)
def validator(kind):
    schema = decode_json((Path(__file__).parent/'schemas/review-v1.schema.json').read_bytes())
    Draft202012Validator.check_schema(schema)
    return StrictValidator({'$defs': schema['$defs'], '$ref': '#/$defs/'+kind})


class ReviewValue(Document):
    def __init__(self, value):
        raw = canonical(value)
        value = decode_json(raw)
        if next(validator(self.KIND).iter_errors(value), None):
            fail('schema')
        self._check(value)
        object.__setattr__(self, 'encoded', raw)

    @classmethod
    def from_bytes(cls, raw):
        if type(raw) is not bytes or len(raw) > 8*1024*1024:
            fail('document_bound')
        value = cls.from_dict(decode_json(raw))
        if value.encoded != raw:
            fail('noncanonical_document')
        return value


class ReviewBundle(ReviewValue):
    KIND = 'composition-review-bundle'

    def _check(self, value):
        material = json_value(value['material_json'])
        if type(material) is not dict or set(material) != {'composition_sha256','operation','registry_sha256','impact_sha256','members','selected_appearance','phase3_binding_sha256'}:
            fail('material_shape')
        phase3 = ConsumptionAttestation.from_dict(json_value(value['phase3_json']))
        if (fingerprint(material) != value['context_sha256']
                or phase3.to_dict()['binding_sha256'] != material.get('phase3_binding_sha256')
                or material.get('composition_sha256') != value['composition_sha256']
                or material.get('selected_appearance') != value['selected_appearance']
                or material.get('members') != value['members']):
            fail('bundle_binding')
        if value['members'] != sorted(set(value['members'])):
            fail('membership')


class ReviewDecision(ReviewValue):
    KIND = 'composition-review-decision'

    def _check(self, value):
        submitter = value['role'] == 'submitter'
        if submitter != (value['action'] in {'confirm', 'reject', 'withdraw'}):
            fail('decision_role')
        if (value['role'] == 'maintainer') != (value['confirmation_sha256'] is not None):
            fail('confirmation_reference')


class ReviewState(ReviewValue):
    KIND = 'composition-review-state'

    def _check(self, value):
        initial = value['revision'] == 1
        if initial != (value['previous_sha256'] is None) or initial != (value['state'] == 'PREVIEWS_COMPLETE'):
            fail('review_revision')
        if initial != (value['record_sha256'] is None):
            fail('review_record')
        if (value['state'] in {'STALE', 'CONFLICTED'}) != (value['reason'] is not None):
            fail('diagnostic_state')
        if (initial or value['reason'] is not None) != (value['grant_sha256'] is None):
            fail('attribution_reference')


def operation_payload(composition):
    """Acyclic Phase 3 request pin: preview exists before its human decisions."""
    return fingerprint(dict(operation=composition.to_dict()['operation'], composition_sha256=composition.sha256))


def _scope(index, identities):
    nodes = {}
    pending = [index.outputs[i]['node'] for i in identities]
    while pending:
        key = pending.pop()
        if key not in nodes:
            nodes[key] = index.nodes[key]
            pending.extend(index.nodes[key]['dependencies'])
    return nodes


@dataclass(frozen=True)
class ReviewInputs:
    """Explicit independently selected current observations, never JSON flags."""
    composition: CompositionContext
    composition_sha256: str
    phase3: ConsumptionAttestation
    expected_phase3_sha256: str
    phase3_inputs: dict

    def _material(self, *, original=None, selected_appearance='requested'):
        if (type(self.composition) is not CompositionContext
                or type(self.phase3) is not ConsumptionAttestation
                or type(self.phase3_inputs) is not dict):
            fail('typed_current_evidence_required')
        ctx = self.composition
        if ctx.registry.operations.root != ctx.candidate.registry.operations.root:
            fail('foreign_registry')
        archive = CompositionArchive(ctx.registry.operations.root, readonly=True)
        # Reject malformed/stale metadata before expensive native-byte replay.
        # Every successful path still calls the full unchanged M3 verifier below.
        pin = require_hash(self.composition_sha256)
        composition = CompositionEvidence.from_bytes(archive.store.read_object(pin))
        if composition.sha256 != pin:
            fail('composition_pin')
        value = composition.to_dict()
        if selected_appearance not in {v['appearance'] for v in value['views']}:
            fail('selected_appearance')
        require_hash(self.expected_phase3_sha256)
        if self.phase3.sha256 != self.expected_phase3_sha256:
            fail('phase3_pin')
        old = self.phase3 if original is None else ConsumptionAttestation.from_dict(original)
        current = revalidate(old, expected_sha256=old.sha256, **self.phase3_inputs)
        # Independently selected observations must themselves be exact replays.
        selected = current if old.sha256 == self.phase3.sha256 else revalidate(
            self.phase3, expected_sha256=self.expected_phase3_sha256, **self.phase3_inputs)
        if current.encoded != selected.encoded:
            fail('substituted_phase3')
        report = current.to_dict()
        request = self.phase3_inputs['request_context'].to_dict()
        operation = value['operation']
        if ((request['id'], request['revision'], request['request_payload_sha256'])
                != (operation['id'], operation['revision'], operation_payload(composition))):
            fail('phase3_operation_binding')
        if not report['evaluation_complete'] or not report['chain_compatible'] or not report['simulation_eligible'] or not report['simulation']:
            fail('current_evidence_unavailable_or_incomplete')
        if any(report[k] for k in ('technical_eligible', 'ready', 'active', 'publication_authorized', 'production_enforcement')):
            fail('synthetic_as_real')
        # Reuse P3's actual M7 inventory inspection, never submitted readiness.
        if report['m7']['exact_approvals_missing'] != 22 or report['m7']['ready'] or report['m7']['active']:
            fail('m7_boundary')
        ids = value['required_members']
        subjects = {s['subject_id']: s for s in report['subjects']}
        if set(subjects) != set(ids):
            fail('phase3_membership')
        graph = self.phase3_inputs['graph']
        if type(graph) is not Snapshot:
            fail('graph_type')
        index = Snapshot.load(graph.encoded, expected_sha256=self.phase3_inputs['expected_graph_sha256']).index()
        candidate_index = ctx.candidate.graph.index()
        if any(i not in index.outputs for i in ids):
            fail('graph_membership')
        # Permit only genuinely unrelated enclosing-graph observations to move.
        if (_scope(index, ids) != _scope(candidate_index, ids)
                or any(index.outputs[i] != candidate_index.outputs[i] for i in ids)):
            fail('selected_dependency_scope')
        registry = ctx.registry.view()
        destination = self.phase3_inputs['destination_inputs']
        namespace = json_value(registry.snapshot.to_dict()['namespace_context_json'])
        if (destination['inventory'].sha256 != namespace['inventory_sha256']
                or destination['evidence'].to_dict()['target']['root'] != namespace['root']):
            fail('destination_namespace_binding')
        from .basis import historical_basis
        default = next(v for v in value['views'] if v['appearance']=='default')
        jobs = {j['poster_id']:j for j in json_value(default['manifest_json'])['jobs']}
        translations = {i.report.to_dict()['subject']['id']:i.report.to_dict() for i in self.phase3_inputs['inputs']}
        for identity, subject in subjects.items():
            entry = registry.entry(identity)
            package = historical_basis().package(entry['category'])
            expected = [dict(id=identity, identity_sha256=fingerprint(entry),
                local_path=entry['names']['local_path'], public_path=entry['names']['public_path'])]
            if subject['outputs'] != expected or subject['language'] != 'en':
                fail('identity_or_destination_membership')
            if subject['scope']['variant'] != entry['variant']:
                fail('design_variant')
            if (subject['scope']['contract_sha256'], subject['scope']['rules_sha256']) != (package.contract.sha256, package.rules.sha256):
                fail('category_policy_substitution')
            if jobs[identity]['kind']=='poster':
                translated = translations[identity]
                if (translated['resolved_caption'] != jobs[identity]['parameters']['text']
                        or json_value(translated['legacy_trace_json']) != jobs[identity]['translation']['trace']):
                    fail('rendered_translation_binding')
        material = dict(composition_sha256=composition.sha256, operation=operation,
            registry_sha256=ctx.candidate.registry_head.snapshot_sha256,
            impact_sha256=ctx.impact_sha256, members=ids,
            selected_appearance=selected_appearance,
            phase3_binding_sha256=report['binding_sha256'])
        return composition, current, material

    def verify(self, *, original=None, selected_appearance='requested'):
        result = self._material(original=original,selected_appearance=selected_appearance)
        CompositionArchive(self.composition.registry.operations.root,readonly=True).load(
            self.composition_sha256,context=self.composition)
        return result

    def bundle(self, identity, submitter, *, selected_appearance='requested'):
        # Preparing immutable structural data does not publish a review head.
        # ReviewArchive's transaction performs full native replay before exposure.
        _, current, material = self._material(selected_appearance=selected_appearance)
        return ReviewBundle.from_dict(dict(**HEADER, kind=ReviewBundle.KIND, id=identity,
            submitter=submitter, composition_sha256=self.composition_sha256,
            members=material['members'], selected_appearance=selected_appearance,
            context_sha256=fingerprint(material), material_json=canonical(material).decode(),
            phase3_json=current.encoded.decode()))

    def verify_bundle(self, bundle):
        if type(bundle) is not ReviewBundle:
            fail('bundle_type')
        value = ReviewBundle.from_bytes(bundle.encoded).to_dict()
        _, _, material = self.verify(original=json_value(value['phase3_json']),
            selected_appearance=value['selected_appearance'])
        if material != json_value(value['material_json']):
            fail('stale_review_context')
        return bundle


def selective_impact(graph, changes, populations):
    """Read-only M5 direct/transitive/companion query; never edits decisions."""
    if type(graph) is not Snapshot or type(populations) is not dict:
        fail('impact_type')
    index = Snapshot.load(graph.encoded, expected_sha256=graph.sha256).index()
    result = index.impact(changes)
    if result['unresolved']:
        fail('unknown_invalidation_scope')
    affected = set(result['affected_outputs']) | set(result['required_companions'])
    invalidated, preserved = [], []
    for identity, members in sorted(populations.items()):
        if not members or not set(members) <= index.outputs.keys():
            fail('invalidation_membership')
        (invalidated if affected & set(members) else preserved).append(identity)
    return dict(invalidated=invalidated, preserved=preserved, impact=result,
        preservation='requires_independent_current_evidence_and_authority_replay')
