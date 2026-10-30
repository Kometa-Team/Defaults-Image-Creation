"""M3 exact native-decision binding over M2, P3/P4 and Package E.

The live consumer is deliberately unavailable pending P5-D02/D03 policy and
provider acceptance. The concrete fixture adapter alone exercises existing
synthetic consumers. Neither serialized values nor fixture receipts are grants.
No renderer, operation transition, registry activation or publisher is called.
"""
from dataclasses import dataclass
from datetime import datetime
import hashlib
from functools import wraps
from functools import lru_cache
from pathlib import Path
import threading

from ..common import BulkError, Conflict, canonical, confined, fingerprint, reject_links
from ..contracts.categories.release import Implementation, RELEASE_SHA256, ROOT as CONTRACT_ROOT
from ..contracts.models import ContractApproval, RegistryDocument, decode_json
from ..contracts.registry import RegistrySnapshot, TrustedDecision, package_reference
from .evidence import FLAGS, ReviewBundle, ReviewInputs
from .github_observations import FixtureObserver, GitHubObserver
from .package_e import SidecarStore
from .previews import CompositionTrial
from .review import ReviewArchive, decision
from .review_authority import SyntheticReviewAuthority

VERSION = '1.0.0'
LABELS = ('submitter', 'maintainer', 'source', 'translation', 'destination')
SUBMITTER = 'synthetic.actor.submitter'
MAINTAINER = 'synthetic.actor.maintainer'
MAX_EVIDENCE = 2_000_000


def _release_bytes():
    release = decode_json(confined(CONTRACT_ROOT, 'categories/data/release-v1.json', must_exist=True).read_bytes())
    names = {'categories/data/release-v1.json', 'categories/data/review-registry-v1.json'}
    for entry in release['entries']:
        names.update((entry['contract_path'], entry['rules_path']))
    return tuple((name, hashlib.sha256(confined(CONTRACT_ROOT, name, must_exist=True).read_bytes()).hexdigest()) for name in sorted(names))


@lru_cache(maxsize=1)
def _validated_release():
    before = _release_bytes()
    implementation = Implementation.load(expected_sha256=RELEASE_SHA256)
    if _release_bytes() != before:
        _fail('registry_changed_during_selection')
    return implementation, before


def _current_release():
    # Memoize expensive immutable parsing only. All 46 exact current files are
    # read/hash-checked again on every selection, including at consumption.
    implementation, selected = _validated_release()
    if _release_bytes() != selected:
        _fail('current_registry_changed')
    return implementation


class _DecisionBlocked(BulkError):
    pass


def _fail(reason):
    # Closed, locally selected diagnostics only. Never carry a remote exception.
    raise _DecisionBlocked('p5m3_' + reason, 'Exact decision consumption blocked: ' + reason) from None


def _boundary(method):
    @wraps(method)
    def guarded(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except _DecisionBlocked:
            raise
        except Conflict:
            conflict = True
        except Exception:
            conflict = False
        # Raise outside the handler: no remote/native exception chain survives.
        if conflict:
            raise Conflict('Exact M3 checkpoint conflict') from None
        _fail('native_evidence_unavailable')
    return guarded


@dataclass(frozen=True)
class PackageSelection:
    category: str
    kind: str
    version: str
    sha256: str
    variants: tuple[str, ...]

    @classmethod
    def current(cls, category, *, variants=None):
        package = _current_release().select(category)
        value = package.contract.to_dict()
        return cls(value['category'], value['kind'], value['version'], package.contract.sha256,
                   tuple(sorted(v['id'] for v in value['variants'])) if variants is None else variants)

    def select(self, *, whole_package=False):
        if type(self) is not PackageSelection:
            _fail('package_type')
        package = _current_release().select(self.category)
        value = package.contract.to_dict()
        closed = {v['id'] for v in value['variants']}
        if ((self.kind, self.version, self.sha256) != (value['kind'], value['version'], package.contract.sha256)
                or type(self.variants) is not tuple or not self.variants
                or any(type(v) is not str for v in self.variants)
                or tuple(sorted(set(self.variants))) != self.variants or not set(self.variants) <= closed
                or (whole_package and set(self.variants) != closed)):
            _fail('exact_package_scope')
        return package


@dataclass(frozen=True)
class ObservationQuery:
    observer: object
    paths: tuple = ()
    translation_keys: tuple = ()
    pull_request: int | None = None

    def read(self):
        return self.observer.observe(paths=self.paths, translation_keys=self.translation_keys,
                                     pull_request=self.pull_request)


@dataclass(frozen=True)
class DecisionBinding:
    """Opaque lifetime-selected audit data; no loader restores consumption trust."""
    encoded: bytes

    @property
    def sha256(self):
        return hashlib.sha256(self.encoded).hexdigest()

    def to_dict(self):
        from ..contracts.models import decode_json
        return decode_json(self.encoded)


@dataclass(frozen=True)
class ConsumptionReceipt(DecisionBinding):
    @property
    def publication_authorized(self):
        return False

    @property
    def contract_approved(self):
        return False

    @property
    def readiness_authorized(self):
        return False


def fixture_message(binding, *, stage, action, confirmation=None):
    """Explicit offline fixture grammar, NOT proposed/accepted approval wording.

    Only the body hash is compared with the independently observed native body.
    A generic PR comment/approval or this text without native authorship fails.
    """
    if type(binding) is not DecisionBinding or stage not in {'submitter', 'maintainer'}:
        _fail('message_type')
    return canonical(dict(protocol='phase5-m3-fixture-only-v1', binding_sha256=binding.sha256,
        stage=stage, action=action, confirmation=confirmation)).decode('utf8')


class GitHubDecisionConsumer:
    """Read-only M2 capture plus an explicitly unavailable live consumption gate.

    No policy argument can turn this into a real-positive provider. Implementing
    the integration is not acceptance of identity delegation, role mappings,
    expiry, review-edit/reversal semantics, or production decision language.
    """
    def __init__(self, queries):
        self._configure(queries, GitHubObserver)

    def _configure(self, queries, observer_type):
        if type(queries) is not dict or set(queries) != set(LABELS):
            _fail('observation_scope')
        if any(type(q) is not ObservationQuery or type(q.observer) is not observer_type for q in queries.values()):
            _fail('observer_boundary')
        self.queries = dict(queries)

    @_boundary
    def observe(self):
        if type(self) not in {GitHubDecisionConsumer, FixtureDecisionConsumer}:
            _fail('consumer_boundary')
        expected = FixtureObserver if type(self) is FixtureDecisionConsumer else GitHubObserver
        self._configure(self.queries, expected)
        result = {name: self.queries[name].read() for name in LABELS}
        wanted = 'synthetic-current' if expected is FixtureObserver else 'verified-current'
        for name, value in result.items():
            report = value.to_dict()
            if report['status'] != wanted:
                _fail('observation_' + (report['status'] if report['status'] in {'invalid', 'stale', 'revoked'} else 'unavailable') + '_' + name)
        return result

    def consume(self, *args, **kwargs):
        # No argument, archived observation, callback, native PR approval or
        # subclass can bypass this gate. There is no accepted live policy yet.
        _fail('real_policy_and_provider_unavailable')


class FixtureDecisionConsumer(GitHubDecisionConsumer):
    """Concrete disposable positive path; never exported as P3/P4 real authority.

    Numeric participants and logical expiry are fixture controls only. The
    existing SyntheticReviewAuthority retains all false operational flags.
    """
    def __init__(self, trial, queries, *, submitter_id, maintainer_id, source_files=(), as_of=0, expires_at=100):
        if type(self) is not FixtureDecisionConsumer or type(trial) is not CompositionTrial or trial._closed:
            _fail('fixture_trial_required')
        if (any(type(v) is not int or v <= 0 for v in (submitter_id, maintainer_id))
                or submitter_id == maintainer_id):
            _fail('independent_numeric_identities')
        if type(as_of) is not int or type(expires_at) is not int or not 0 <= as_of < expires_at:
            _fail('fixture_expiry')
        self._configure(queries, FixtureObserver)
        self.trial, self.submitter_id, self.maintainer_id = trial, submitter_id, maintainer_id
        self.source_files = tuple(source_files)
        self.as_of, self.expires_at = as_of, expires_at
        self._issued = {}
        self._lock = threading.RLock()
        self._authority = SyntheticReviewAuthority(trial, submitters=(SUBMITTER,), maintainers=(MAINTAINER,), as_of=as_of)

    def _lifetime(self):
        if type(self) is not FixtureDecisionConsumer or self.trial._closed:
            _fail('fixture_trial_required')
        if type(self.as_of) is not int or not 0 <= self.as_of < self.expires_at:
            _fail('fixture_expired')
        self._authority.as_of = self.as_of

    def _facts(self, observations):
        facts = {name: value.to_dict()['facts'] for name, value in observations.items()}
        submitter, maintainer = (facts[name] for name in ('submitter', 'maintainer'))
        if (submitter['identity']['principal']['id'] != self.submitter_id
                or maintainer['identity']['principal']['id'] != self.maintainer_id):
            _fail('principal_identity')
        if (submitter['identity']['repository_id'] != maintainer['identity']['repository_id']
                or submitter['identity']['owner_id'] != maintainer['identity']['owner_id']
                or submitter.get('decisions') != maintainer.get('decisions')):
            _fail('proposal_observation_mismatch')
        pull = submitter.get('decisions')
        if not pull or pull['author_id'] != self.submitter_id or pull['state'] != 'open' or pull['merged']:
            _fail('submitter_work_relationship')
        source = facts['source']
        if (pull['head_repository_id'], pull['head_commit']) != (source['identity']['repository_id'], source['snapshot']['commit']):
            _fail('proposal_source_binding')
        role = maintainer['identity']['principal_role']
        # Explicitly a fixture role policy; never installed for real identities.
        if role['user_id'] != self.maintainer_id or role['role_name'] not in {'maintain', 'admin'} or role['permission'] not in {'write', 'admin'}:
            _fail('fixture_maintainer_permission')
        return facts

    def _native(self, inputs, bundle, facts, selection):
        if type(inputs) is not ReviewInputs or type(bundle) is not ReviewBundle:
            _fail('native_review_inputs')
        if inputs.composition.registry.operations.root != self.trial.config.cache_dir:
            _fail('foreign_native_archive')
        inputs.verify_bundle(bundle)  # P3 revalidate + actual full encoded bytes/owned receipts.
        composition = inputs.composition
        self.trial.require(composition.candidate)
        members = bundle.to_dict()['members']
        entries = [composition.registry.view().entry(i) for i in members]
        if (any(e['category'] != selection.category for e in entries)
                or {e['variant'] for e in entries} != set(selection.variants)):
            _fail('artwork_package_scope')
        from .previews import CompositionArchive
        from .composition_models import CompositionEvidence
        archive = CompositionArchive(self.trial.config.cache_dir, readonly=True)
        # verify_bundle above already performed the full native archive replay.
        # Read its exact immutable metadata without replaying it a second time.
        evidence = CompositionEvidence.from_bytes(archive.store.read_object(inputs.composition_sha256))
        if evidence.sha256 != inputs.composition_sha256:
            _fail('composition_pin')
        required = {}
        for view in evidence.to_dict()['views']:
            for source in view['sources']:
                required[str((composition.candidate.config.asset_dir / source['path']).resolve())] = source['sha256']
        for path in (*composition.candidate.paths, composition.candidate.profiles_path):
            path = reject_links(Path(path)).resolve()
            required[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
        if len(self.source_files) > 100:
            _fail('source_membership')
        mapped = {}
        for remote, local in self.source_files:
            from ..contracts.destination_preflight.paths import safe_path
            safe_path(remote)
            local = str(reject_links(Path(local)).resolve())
            if local in mapped or remote in mapped.values():
                _fail('source_membership')
            mapped[local] = remote
        remote = {s['path']: s['sha256'] for s in facts['source']['snapshot']['selected']}
        if set(mapped) != set(required) or remote != {mapped[p]: pin for p, pin in required.items()}:
            _fail('native_source_bytes')
        translation = facts['translation']
        selected = {v['path']: v for v in translation['snapshot']['selected']}
        for item in inputs.phase3_inputs['inputs']:
            if item.selection is None:
                report = item.report.to_dict()
                if (report['key_status'] != 'not_applicable' or report['required_keys']
                        or report['results'] or report['currentness'] != 'not_applicable'
                        or report['required_row_count'] != 0 or report['evaluated_row_count'] != 0):
                    _fail('translation_selection_unavailable')
                value = dict(source=report['source'], values=[])
            else:
                value = item.selection.to_dict()
            source = value['source']
            identity, snapshot = translation['identity'], translation['snapshot']
            repo = source['repository']
            if ((repo['repository_id'], repo['owner_id'], repo['name'], source['commit'], source['tree']) !=
                    (identity['repository_id'], identity['owner_id'], identity['repository'], snapshot['commit'], snapshot['tree'])):
                _fail('authoritative_translation_binding')
            for resource in source['resources']:
                observed = selected.get(resource['path'], {})
                if (resource['blob_sha1'], resource['sha256']) != (observed.get('blob'), observed.get('sha256')):
                    _fail('translation_resource_bytes')
            for trace in value['values']:
                from ..contracts.translation_preflight.sources import lookup, parse
                raw = dict(item.snapshot.resources).get(trace['resource_path'])
                found, text, actual_key = lookup(parse(raw), trace['key'])
                values = {v['key']: v['value_sha256'] for v in selected.get(trace['resource_path'], {}).get('values', [])}
                if not found or fingerprint(text) != trace['value_sha256'] or values.get(actual_key) != trace['value_sha256']:
                    _fail('required_translation_value')
        destination = inputs.phase3_inputs['destination_inputs']
        target = destination['evidence'].to_dict()['target']
        observed = facts['destination']
        identity, snapshot = observed['identity'], observed['snapshot']
        repo = target['repository']
        if ((repo['repository_id'], repo['owner_id'], repo['name'], target['branch'], target['root'], target['baseline_commit'], target['baseline_tree']) !=
                (identity['repository_id'], identity['owner_id'], identity['repository'], snapshot['branch'], snapshot['root'], snapshot['commit'], snapshot['tree'])):
            _fail('current_destination_binding')

    def _contract_source(self, selection, facts):
        implementation = _current_release()
        package = selection.select(whole_package=True)
        entry = next(e for e in implementation.release.to_dict()['entries']
                     if e['contract_sha256'] == package.contract.sha256)
        names = {entry['contract_path'], entry['rules_path'],
                 'categories/data/release-v1.json', 'categories/data/review-registry-v1.json'}
        expected = {'create_defaults/bulk/contracts/' + name:
                    hashlib.sha256(confined(CONTRACT_ROOT, name, must_exist=True).read_bytes()).hexdigest()
                    for name in names}
        selected = {row['path']: row['sha256'] for row in facts['source']['snapshot']['selected']}
        if selected != expected:
            _fail('contract_source_bytes')

    def _context(self, facts, selection, *, scope, bundle=None):
        selection.select(whole_package=scope == 'contract')
        pull = facts['submitter']['decisions']
        # Decision histories are observed after human decisions; they are not a
        # cyclic prerequisite of the proposal hash. Their full pins enter receipt.
        proposal = {k: pull[k] for k in ('id', 'number', 'author_id', 'state', 'merged', 'draft', 'base_commit', 'head_commit', 'head_repository_id')}
        value = dict(schema_version=1, kind='phase5-m3-fixture-binding', version=VERSION,
            scope=scope, package=dict(selection.__dict__, variants=list(selection.variants)),
            proposal=proposal, submitter_id=self.submitter_id, maintainer_id=self.maintainer_id,
            observations={name: dict(identity=facts[name]['identity'], snapshot=facts[name]['snapshot']) for name in LABELS},
            bundle_sha256=bundle.sha256 if bundle else None,
            context_sha256=bundle.to_dict()['context_sha256'] if bundle else None,
            fixture_expiry=self.expires_at, **FLAGS)
        encoded = canonical(value)
        if len(encoded) > MAX_EVIDENCE:
            _fail('evidence_bound')
        return DecisionBinding(encoded)

    @_boundary
    def prepare(self, selection, *, inputs=None, review_id=None, scope='artwork'):
        with self._lock:
            self._lifetime()
            if type(selection) is not PackageSelection or scope not in {'artwork', 'contract'}:
                _fail('scope_unavailable')
            facts = self._facts(self.observe())
            bundle = None
            if scope == 'artwork':
                if type(inputs) is not ReviewInputs or type(review_id) is not str or len(review_id) > 180:
                    _fail('native_review_inputs')
                bundle = inputs.bundle(review_id, SUBMITTER)
                self._native(inputs, bundle, facts, selection)
            elif inputs is not None or review_id is not None:
                _fail('separate_approval_scopes')
            else:
                self._contract_source(selection, facts)
            binding = self._context(facts, selection, scope=scope, bundle=bundle)
            if len(self._issued) >= 16:
                self._issued.pop(next(iter(self._issued)))
            self._issued[id(binding)] = (binding, selection, inputs, bundle)
            return binding

    def _decisions(self, binding, facts, *, confirmation_id, review_id, action):
        if type(confirmation_id) is not int or type(review_id) is not int or action not in {'approve', 'reject'}:
            _fail('exact_native_selection')
        pull = facts['submitter']['decisions']
        comments, reviews = pull['comments'], pull['reviews']
        confirm = next((v for v in comments if v['id'] == confirmation_id), None)
        review = next((v for v in reviews if v['id'] == review_id), None)
        if not confirm or confirm['author_id'] != self.submitter_id or confirm['created_at'] != confirm['updated_at']:
            _fail('exact_submitter_confirmation')
        if max((v for v in comments if v['author_id'] == self.submitter_id), key=lambda v: (v['created_at'], v['id'])) != confirm:
            _fail('confirmation_superseded')
        if confirm['body_sha256'] != hashlib.sha256(fixture_message(binding, stage='submitter', action='confirm').encode()).hexdigest():
            _fail('confirmation_context')
        reference = {k: confirm[k] for k in ('id', 'revision_sha256')}
        if (not review or review['author_id'] != self.maintainer_id or review['author_id'] == confirm['author_id']
                or review['role'] != facts['maintainer']['identity']['principal_role']
                or review['state'] != ('APPROVED' if action == 'approve' else 'CHANGES_REQUESTED')
                or not review['matches_current_head'] or review['commit'] != pull['head_commit']):
            _fail('exact_independent_maintainer')
        eligible = [v for v in reviews if v['submitted_at'] is not None and v['role']['role_name'] in {'maintain', 'admin'}]
        if not eligible or max(eligible, key=lambda v: (v['submitted_at'], v['id'])) != review:
            _fail('maintainer_decision_superseded')
        if datetime.fromisoformat(confirm['created_at'].replace('Z', '+00:00')) >= datetime.fromisoformat(review['submitted_at'].replace('Z', '+00:00')):
            _fail('two_stage_order')
        expected = fixture_message(binding, stage='maintainer', action=action, confirmation=reference)
        if review['body_sha256'] != hashlib.sha256(expected.encode()).hexdigest():
            _fail('maintainer_context')
        return confirm, review

    def _reobserve(self, observations):
        for name, previous in observations.items():
            fresh = self.queries[name].observer.reobserve(previous).to_dict()
            if fresh['status'] != 'synthetic-current':
                _fail('authority_changed_at_consumption')

    def _artwork(self, inputs, bundle, *, action):
        archive = ReviewArchive.create(self.trial.config.cache_dir)
        history = archive.history(bundle.to_dict()['id'])
        if not history:
            state = archive.start(bundle.to_dict()['id'], submitter=SUBMITTER, inputs=inputs)
        else:
            state = history[-1]
        # Reconstruct attribution ONLY after fresh native decisions were checked.
        # Archived records alone cannot reach this function through consume.
        if state.to_dict()['state'] != 'PREVIEWS_COMPLETE':
            _, existing, records = archive.read(bundle.to_dict()['id'], expected_sha256=state.sha256)
            if existing != bundle:
                _fail('changed_review_bundle')
            for field, actor, role in [('confirmation_sha256', SUBMITTER, 'submitter'), ('decision_sha256', MAINTAINER, 'maintainer')]:
                pin = state.to_dict()[field]
                if pin is not None:
                    record = records[pin][0]
                    self._authority.authorize(record, actor=actor, role=role, expires_at=self.expires_at)
        if state.to_dict()['state'] == 'PREVIEWS_COMPLETE':
            record = decision(bundle, state, actor=SUBMITTER, action='confirm')
            self._authority.authorize(record, actor=SUBMITTER, role='submitter', expires_at=self.expires_at)
            state = archive.decide(record, expected_sha256=state.sha256, inputs=inputs, authority=self._authority)
        if state.to_dict()['state'] == 'SUBMITTER_CONFIRMED':
            record = decision(bundle, state, actor=MAINTAINER, action='approve' if action == 'approve' else 'reject-maintainer')
            self._authority.authorize(record, actor=MAINTAINER, role='maintainer', expires_at=self.expires_at)
            state = archive.decide(record, expected_sha256=state.sha256, inputs=inputs, authority=self._authority)
        if state.to_dict()['state'] != ('MAINTAINER_APPROVED' if action == 'approve' else 'MAINTAINER_REJECTED'):
            _fail('review_decision_conflict')
        if action == 'approve':
            archive.current(bundle.to_dict()['id'], expected_sha256=state.sha256, inputs=inputs, authority=self._authority)
        else:
            inputs.verify_bundle(bundle)
        return dict(review_state_sha256=state.sha256, review_state=state.to_dict()['state'])

    def _contract(self, selection, evidence_sha256, *, action):
        package = selection.select(whole_package=True)
        reference = package_reference(package.contract)
        approval = ContractApproval.from_dict(dict(schema_version=1, kind='contract-approval',
            id='synthetic.contract.' + selection.category.lower(), revision=1,
            provenance=dict(role='maintainer', actor='bullmoose20', source='Controlled M3 fixture ONLY; no real attribution', evidence_sha256=evidence_sha256),
            package=reference, decision='approved' if action == 'approve' else 'rejected', scope='category-contract'))
        store = SidecarStore(self.trial.config.cache_dir)
        for record in (package.contract, approval):
            store.put_object(record.encoded, expected_sha256=record.sha256)
        if action == 'reject':
            return dict(contract_decision_sha256=approval.sha256, synthetic_contract_selected=False)
        registry = RegistryDocument.from_dict(dict(schema_version=1, kind='category-contract-registry',
            id='synthetic.m3.registry', version='1.0.0', owner='bullmoose20',
            provenance=dict(role='maintainer', actor='bullmoose20', source='Disposable fixture registry only', evidence_sha256=evidence_sha256),
            entries=[dict(package=reference, variants=list(selection.variants), approval_sha256=approval.sha256, adoption_sha256=[])]))
        store.put_object(registry.encoded, expected_sha256=registry.sha256)
        checked = RegistrySnapshot.load(registry.encoded, expected_sha256=registry.sha256, read_object=store.read_object,
            trusted_decisions={approval.sha256: TrustedDecision('bullmoose20', evidence_sha256)})
        for variant in selection.variants:
            checked.select(selection.category, selection.kind, selection.version, selection.sha256, variant)
        # No trusted map/RegistrySnapshot is returned as a live capability.
        return dict(contract_decision_sha256=approval.sha256, registry_sha256=registry.sha256, synthetic_contract_selected=True)

    @_boundary
    def consume(self, binding, *, confirmation_id, review_id, scope, action='approve'):
        with self._lock:
            self._lifetime()
            issued = self._issued.get(id(binding))
            if type(binding) is not DecisionBinding or not issued or issued[0] is not binding:
                _fail('restart_or_foreign_binding')
            _, selection, inputs, bundle = issued
            if scope != binding.to_dict()['scope']:
                _fail('separate_approval_scopes')
            observations = self.observe()
            facts = self._facts(observations)
            if bundle is not None:
                self._native(inputs, bundle, facts, selection)
            else:
                self._contract_source(selection, facts)
            if self._context(facts, selection, scope=scope, bundle=bundle) != binding:
                _fail('full_context_changed')
            confirm, review = self._decisions(binding, facts, confirmation_id=confirmation_id, review_id=review_id, action=action)
            self._reobserve(observations)
            if bundle is not None:
                inputs.verify_bundle(bundle)
            evidence = dict(binding_sha256=binding.sha256, confirmation=confirm, decision=review,
                observations={name: value.sha256 for name, value in observations.items()})
            evidence_pin = fingerprint(evidence)
            store = SidecarStore(self.trial.config.cache_dir)
            store.put_object(canonical(evidence), expected_sha256=evidence_pin)
            for name, observation in observations.items():
                self.queries[name].observer.archive(observation, store)
            result = self._artwork(inputs, bundle, action=action) if scope == 'artwork' else self._contract(selection, evidence_pin, action=action)
            receipt = ConsumptionReceipt(canonical(dict(schema_version=1, kind='phase5-m3-fixture-consumption',
                version=VERSION, scope=scope, action=action, binding_sha256=binding.sha256,
                evidence_sha256=evidence_pin, result=result, **FLAGS)))
            store.put_object(receipt.encoded, expected_sha256=receipt.sha256)
            # Existing Package E CAS/event machinery, no table/database/schema.
            # No network call takes place inside this local write transaction.
            with store.transaction() as db:
                rows = db.execute("SELECT payload FROM events WHERE kind='phase5_m3_consumption' AND subject=?", (binding.sha256,)).fetchall()
                payload = dict(receipt_sha256=receipt.sha256, publication_authorized=False)
                if rows:
                    if len(rows) != 1 or rows[0]['payload'] != canonical(payload).decode():
                        raise Conflict('Exact M3 decision already consumed with different evidence')
                else:
                    store.event(db, 'phase5_m3_consumption', binding.sha256, payload)
            return receipt
