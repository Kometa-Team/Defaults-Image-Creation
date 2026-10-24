"""Immutable complete-artwork two-stage review in the existing Package E DB.

M4 writes only synthetic review sidecars. No operation transition, real approval,
application, activation, production catalog or publication integration exists.
"""
from ..common import BulkError, Conflict, canonical
from ..contracts.registry import require_hash
from .evidence import HEADER, FLAGS, ReviewBundle, ReviewDecision, ReviewState, ReviewValue, ReviewInputs, fail
from .package_e import SidecarStore
from .storage import OperationStore
from .review_authority import verify_authority


MAX_EVENTS = 4096
MAX_BYTES = 64*1024*1024
TABLES = (
    'CREATE TABLE p4m4_schema (version INTEGER NOT NULL)',
    'CREATE TABLE p4m4_reviews (id TEXT NOT NULL, revision INTEGER NOT NULL, sha256 TEXT NOT NULL UNIQUE, package_event INTEGER NOT NULL UNIQUE, PRIMARY KEY(id,revision))',
)
TRIGGERS = tuple('CREATE TRIGGER '+table+'_no_'+action.lower()+' BEFORE '+action+' ON '+table+" BEGIN SELECT RAISE(ABORT,'immutable complete review'); END"
    for table in ('p4m4_schema','p4m4_reviews') for action in ('UPDATE','DELETE'))
DDL = TABLES+TRIGGERS
NAMESPACE = {sql.split()[2]:sql for sql in DDL}
TRANSITIONS = {
    'confirm': ('submitter', {'PREVIEWS_COMPLETE'}, 'SUBMITTER_CONFIRMED'),
    'reject': ('submitter', {'PREVIEWS_COMPLETE'}, 'SUBMITTER_REJECTED'),
    'withdraw': ('submitter', {'PREVIEWS_COMPLETE','SUBMITTER_CONFIRMED','MAINTAINER_APPROVED','MAINTAINER_REJECTED'}, 'WITHDRAWN'),
    'approve': ('maintainer', {'SUBMITTER_CONFIRMED'}, 'MAINTAINER_APPROVED'),
    'reject-maintainer': ('maintainer', {'SUBMITTER_CONFIRMED'}, 'MAINTAINER_REJECTED'),
}


class ReviewInvalidation(ReviewValue):
    KIND = 'composition-review-invalidation'


def decision(bundle, state, *, actor, action):
    """Create structural data only. Independent attribution is still required."""
    if type(bundle) is not ReviewBundle or type(state) is not ReviewState or action not in TRANSITIONS:
        fail('typed_decision_inputs')
    b, s = bundle.to_dict(), state.to_dict()
    role = TRANSITIONS[action][0]
    return ReviewDecision.from_dict(dict(**HEADER, kind=ReviewDecision.KIND,
        review_id=b['id'], bundle_sha256=bundle.sha256, context_sha256=b['context_sha256'],
        previous_sha256=state.sha256, actor=actor, role=role, action=action,
        confirmation_sha256=s['confirmation_sha256'] if role=='maintainer' else None))


def _namespace(db):
    actual = {r['name']:r['sql'] for r in db.execute("SELECT name,sql FROM sqlite_master WHERE name LIKE 'p4m4_%'")}
    if actual != NAMESPACE or [tuple(r) for r in db.execute('SELECT version FROM p4m4_schema')] != [(1,)]:
        fail('archive_namespace')


class ReviewArchive:
    def __init__(self, root):
        # Read-only opening validates original operation isolation, no migrations.
        self.operations = OperationStore(root)
        self.store = SidecarStore.open_readonly(self.operations.root)
        self.history()

    @classmethod
    def create(cls, root):
        OperationStore(root)
        store = SidecarStore(root)
        with store.transaction() as db:
            found = db.execute("SELECT name FROM sqlite_master WHERE name LIKE 'p4m4_%'").fetchall()
            if not found:
                for sql in DDL:
                    db.execute(sql)
                db.execute('INSERT INTO p4m4_schema VALUES (1)')
            else:
                _namespace(db)
        return cls(root)

    def _replay(self, db):
        _namespace(db)
        if db.execute('SELECT count(*) FROM p4m4_reviews').fetchone()[0] > MAX_EVENTS:
            fail('archive_limit')
        if db.execute('SELECT coalesce(sum(length(CAST(id AS BLOB))+length(CAST(sha256 AS BLOB))),0) FROM p4m4_reviews').fetchone()[0] > MAX_BYTES:
            fail('archive_limit')
        rows = db.execute('SELECT * FROM p4m4_reviews ORDER BY id,revision').fetchall()
        packages = [tuple(r) for r in db.execute("SELECT sequence,subject,payload FROM events WHERE kind='phase4_complete_review' ORDER BY sequence")]
        expected_events, histories, bundles, records = [], {}, {}, {}
        budget, cache = 0, {}
        def read(pin, cls):
            nonlocal budget
            if (pin,cls) in cache:
                return cache[pin,cls]
            raw = self.store.read_object(require_hash(pin))
            budget += len(raw)
            if budget > MAX_BYTES:
                fail('archive_limit')
            value = cls.from_bytes(raw)
            if value.sha256 != pin:
                fail('archive_object')
            cache[pin,cls] = value
            return value
        for row in rows:
            state = read(row['sha256'], ReviewState)
            s = state.to_dict()
            history = histories.setdefault(row['id'], [])
            if (s['id'], s['revision'], s['previous_sha256']) != (row['id'], len(history)+1, history[-1].sha256 if history else None):
                fail('archive_chain')
            bundle = read(s['bundle_sha256'], ReviewBundle)
            b = bundle.to_dict()
            if b['id'] != s['id'] or history and history[0].to_dict()['bundle_sha256'] != bundle.sha256:
                fail('archive_bundle_substitution')
            bundles[bundle.sha256] = bundle
            if not history:
                if s['confirmation_sha256'] or s['decision_sha256'] or s['reason']:
                    fail('initial_review_state')
            else:
                prior = history[-1].to_dict()
                invalidation = s['state'] in {'STALE','CONFLICTED'}
                record = read(s['record_sha256'], ReviewInvalidation if invalidation else ReviewDecision)
                r = record.to_dict()
                records[record.sha256] = (record,s['grant_sha256'])
                if (r['review_id'], r['bundle_sha256'], r['context_sha256'], r['previous_sha256']) != (s['id'],bundle.sha256,b['context_sha256'],history[-1].sha256):
                    fail('record_context_substitution')
                confirmation, final = prior['confirmation_sha256'], prior['decision_sha256']
                if invalidation:
                    if r['reason'] != s['reason'] or prior['state'] in {'STALE','CONFLICTED','WITHDRAWN','SUBMITTER_REJECTED'}:
                        fail('invalidation_state')
                else:
                    role, allowed, target = TRANSITIONS[r['action']]
                    if prior['state'] not in allowed or target != s['state'] or r['role'] != role:
                        fail('review_transition')
                    if role == 'submitter':
                        if r['actor'] != b['submitter']:
                            fail('submitter_substitution')
                        if r['action'] in {'confirm','reject'}:
                            confirmation = record.sha256
                    else:
                        if r['actor'] == b['submitter'] or r['confirmation_sha256'] != confirmation:
                            fail('separation_of_duties')
                        prior_confirmation = records.get(confirmation)
                        if prior_confirmation is None or prior_confirmation[0].to_dict()['action'] != 'confirm':
                            fail('missing_confirmation')
                        final = record.sha256
                if (s['confirmation_sha256'],s['decision_sha256']) != (confirmation,final):
                    fail('decision_linkage')
            history.append(state)
            expected_events.append((row['package_event'],s['id'],canonical(dict(revision=s['revision'],sha256=state.sha256,state=s['state'],publication_authorized=False)).decode()))
        if packages != sorted(expected_events):
            fail('archive_event_index')
        return histories, bundles, records

    def history(self, identity=None):
        with self.store.read_connection() as db:
            histories, _, _ = self._replay(db)
        return tuple(histories.get(identity, ())) if identity is not None else {k:tuple(v) for k,v in histories.items()}

    def read(self, identity, *, expected_sha256):
        with self.store.read_connection() as db:
            histories, bundles, records = self._replay(db)
        history = histories.get(identity)
        if not history or history[-1].sha256 != require_hash(expected_sha256):
            raise Conflict('Review head differs from the independently selected checkpoint')
        state = history[-1]
        return state, bundles[state.to_dict()['bundle_sha256']], records

    def current(self, identity, *, expected_sha256, inputs, authority=None):
        if type(inputs) is not ReviewInputs or inputs.composition.registry.operations.root != self.store.root:
            fail('foreign_current_inputs')
        state, bundle, records = self.read(identity, expected_sha256=expected_sha256)
        self._attribution(state,records,authority)
        inputs.verify_bundle(bundle)
        return state, bundle

    def _attribution(self, state, records, authority):
        value = state.to_dict()
        if value['state'] in {'STALE','CONFLICTED','WITHDRAWN','SUBMITTER_REJECTED','MAINTAINER_REJECTED'}:
            fail('inactive_review')
        for field in ('confirmation_sha256','decision_sha256'):
            if value[field] is not None:
                record, grant_sha256 = records[value[field]]
                if verify_authority(authority, record, root=self.store.root)['grant_sha256'] != grant_sha256:
                    fail('authority_context_substitution')

    def _commit(self, state, objects, *, expected_sha256, inputs, authority=None):
        writer = SidecarStore(self.store.root)
        for value in (*objects, state):
            writer.put_object(value.encoded, expected_sha256=value.sha256)
        v = state.to_dict()
        with writer.transaction() as db:
            histories, bundles, records = self._replay(db)
            prior = histories.get(v['id'], [])
            if prior and prior[-1].sha256 == state.sha256:
                inputs.verify_bundle(bundles[v['bundle_sha256']])
                return prior[-1]
            if (prior[-1].sha256 if prior else None) != expected_sha256 or len(prior)+1 != v['revision']:
                raise Conflict('Concurrent complete-review change')
            if len(histories) > MAX_EVENTS:
                fail('archive_limit')
            bundle = next((o for o in objects if type(o) is ReviewBundle),None) or bundles[v['bundle_sha256']]
            if v['state'] in {'STALE','CONFLICTED'}:
                outcome = self.assess(v['id'],expected_sha256=expected_sha256,inputs=inputs,authority=authority)
                if outcome['state'] != v['state'] or outcome['reason'] != v['reason']:
                    fail('invalidation_context_changed')
            else:
                # The same Package E write transaction excludes concurrent local
                # operation/registry-head writes during this final current replay.
                if prior:
                    self._attribution(prior[-1],records,authority)
                for record in objects:
                    if type(record) is ReviewDecision:
                        if verify_authority(authority,record,root=self.store.root)['grant_sha256'] != v['grant_sha256']:
                            fail('authority_context_substitution')
                inputs.verify_bundle(bundle)
            event = writer.event(db,'phase4_complete_review',v['id'],dict(revision=v['revision'],sha256=state.sha256,state=v['state'],publication_authorized=False))
            db.execute('INSERT INTO p4m4_reviews VALUES (?,?,?,?)',(v['id'],v['revision'],state.sha256,event))
            self._replay(db)
        return state

    def start(self, identity, *, submitter, inputs, selected_appearance='requested'):
        if type(inputs) is not ReviewInputs or inputs.composition.registry.operations.root != self.store.root:
            fail('foreign_current_inputs')
        bundle = inputs.bundle(identity,submitter,selected_appearance=selected_appearance)
        state = ReviewState.from_dict(dict(**HEADER,kind=ReviewState.KIND,id=identity,revision=1,
            previous_sha256=None,bundle_sha256=bundle.sha256,state='PREVIEWS_COMPLETE',
            record_sha256=None,grant_sha256=None,confirmation_sha256=None,decision_sha256=None,reason=None))
        return self._commit(state, (bundle,), expected_sha256=None,inputs=inputs)

    def decide(self, record, *, expected_sha256, inputs, authority=None):
        if type(record) is not ReviewDecision:
            fail('decision_type')
        record = ReviewDecision.from_bytes(record.encoded)
        r = record.to_dict()
        if type(inputs) is not ReviewInputs or inputs.composition.registry.operations.root != self.store.root:
            fail('foreign_current_inputs')
        state,bundle,records = self.read(r['review_id'],expected_sha256=expected_sha256)
        self._attribution(state,records,authority)
        b, s = bundle.to_dict(), state.to_dict()
        expected = decision(bundle,state,actor=r['actor'],action=r['action'])
        if expected != record or r['previous_sha256'] != expected_sha256:
            fail('substituted_or_replayed_record')
        role, allowed, target = TRANSITIONS[r['action']]
        if s['state'] not in allowed:
            fail('review_transition')
        if (role == 'submitter' and r['actor'] != b['submitter']) or (role == 'maintainer' and r['actor'] == b['submitter']):
            fail('separation_of_duties')
        attribution = verify_authority(authority,record,root=self.store.root)
        v = dict(s,revision=s['revision']+1,previous_sha256=state.sha256,state=target,
            record_sha256=record.sha256,grant_sha256=attribution['grant_sha256'])
        if r['action'] in {'confirm','reject'}:
            v['confirmation_sha256'] = record.sha256
        if role == 'maintainer':
            v['decision_sha256'] = record.sha256
        next_state = ReviewState.from_dict(v)
        # Recheck actual bytes, operation heads and P3 evidence immediately before
        # index exposure. This is not a live verification/consumption protocol.
        return self._commit(next_state,(record,),expected_sha256=state.sha256,inputs=inputs,authority=authority)

    def assess(self, identity, *, expected_sha256, inputs, authority=None):
        try:
            stored, _, _ = self.read(identity,expected_sha256=expected_sha256)
            if stored.to_dict()['state'] in {'STALE','CONFLICTED','WITHDRAWN','SUBMITTER_REJECTED','MAINTAINER_REJECTED'}:
                return dict(**FLAGS,state=stored.to_dict()['state'],reason=stored.to_dict()['reason'],synthetic_maintainer_approved=False)
            state, _ = self.current(identity,expected_sha256=expected_sha256,inputs=inputs,authority=authority)
        except (BulkError, Conflict) as error:
            return dict(**FLAGS,state='CONFLICTED' if isinstance(error,Conflict) else 'STALE',
                reason=getattr(error,'code','review_checkpoint_conflict'),synthetic_maintainer_approved=False)
        return dict(**FLAGS,state=state.to_dict()['state'],reason=None,
            synthetic_maintainer_approved=state.to_dict()['state']=='MAINTAINER_APPROVED')

    def mark_stale(self, identity, *, expected_sha256, inputs, authority=None):
        state,bundle,_ = self.read(identity,expected_sha256=expected_sha256)
        if state.to_dict()['state'] in {'STALE','CONFLICTED','WITHDRAWN','SUBMITTER_REJECTED','MAINTAINER_REJECTED'}:
            fail('inactive_review')
        if type(inputs) is not ReviewInputs or inputs.composition.registry.operations.root != self.store.root:
            fail('foreign_current_inputs')
        outcome = self.assess(identity,expected_sha256=expected_sha256,inputs=inputs,authority=authority)
        if outcome['state'] not in {'STALE','CONFLICTED'}:
            fail('no_demonstrated_invalidation')
        reason = outcome['reason']
        record = ReviewInvalidation.from_dict(dict(**HEADER,kind=ReviewInvalidation.KIND,
            review_id=identity,bundle_sha256=bundle.sha256,context_sha256=bundle.to_dict()['context_sha256'],previous_sha256=state.sha256,reason=reason))
        v = state.to_dict()|dict(revision=state.to_dict()['revision']+1,previous_sha256=state.sha256,
            state=outcome['state'],record_sha256=record.sha256,grant_sha256=None,reason=reason)
        return self._commit(ReviewState.from_dict(v),(record,),expected_sha256=state.sha256,inputs=inputs,authority=authority)
