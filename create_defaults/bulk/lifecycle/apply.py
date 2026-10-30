"""Atomic *isolated synthetic* ADD/UPDATE coordinator; no operational provider.

This additive bridge uses the original M1 replay, successor, _changes CAS and
event schema in the same Package E immediate transaction. Frozen M1 code/schema
and production pins are unchanged. There is no second index, graph or database.
"""
from threading import Event as Cancellation
import json
import sqlite3

from ..common import Conflict, canonical
from .models import Event, key, successor
from .operations import Transaction, DefinitionSnapshot, FLAGS, observation_pins, fail
from .package_e import SidecarStore
from .recovery import inspect_db, verify_before, validate_state_impact, _successor, _checkpoint
from .review import ReviewArchive
from .review_authority import SyntheticReviewAuthority, require_operational_approval
from .storage import _replay, _changes, _index_budget, MAX_EVENTS, MAX_HEAD_VERSIONS, MAX_ARCHIVE_BYTES


def _cancelled(cancel):
    if cancel is not None and type(cancel) is not Cancellation:
        fail('cancellation_object_required')
    if cancel is not None and cancel.is_set():
        fail('cancelled')


def _final_inputs(transaction, snapshot):
    """Cheap mutable-input pins after image replay, while pointers are hidden.

    SQLite excludes cooperating state writers; external files and synthetic
    verification observations still need their own exact final checks. No live
    filesystem/authority atomicity guarantee is invented for real operations.
    """
    from ..common import sha256
    from ..asset_cases import exact
    from ..contracts.evidence_consumption import revalidate
    from .operations import payload
    ctx=transaction.inputs.composition;s=snapshot.to_dict();candidate=ctx.candidate
    pins=candidate.data()['source_pins']
    paths=(*candidate.paths,candidate.profiles_path)
    if set(p.name for p in paths)!=set(pins) or any(sha256(p)!=pins[p.name] for p in paths):
        fail('definition_changed_during_commit')
    for view in payload(s['composition_json'])['views']:
        for source in view['sources']:
            if sha256(exact(candidate.config.asset_dir,source['path']))!=source['sha256']:
                fail('source_changed_during_commit')
    if canonical(observation_pins(transaction.inputs)).decode()!=s['observation_pins_json']:
        fail('phase3_observations_changed_during_commit')
    observed=revalidate(transaction.inputs.phase3,expected_sha256=transaction.inputs.expected_phase3_sha256,
        **transaction.inputs.phase3_inputs)
    if observed.to_dict()['binding_sha256']!=payload(s['phase3_json'])['binding_sha256']:
        fail('phase3_changed_during_commit')


def _append_m1(writer, db, record, records, events, latest, heads):
    """M1 atomic append assembly with its exact frozen CAS/replay validators.

    Kept local to M5 so M1's public writer, schema and original golden vectors do
    not change. Every inserted row is replayed by M1 before this transaction can
    commit. Tests independently compare the resulting archive to M1.append.
    """
    v = record.to_dict()
    prior = latest.get(v['id'])
    if prior is None or (prior[0].sha256,prior[1].sha256)!=(v['previous_sha256'],v['previous_event_sha256']):
        raise Conflict('Operation changed immediately before isolated commit')
    successor(prior[0].to_dict(),v)
    changes = _changes(record, heads)
    if len(events)+1>MAX_EVENTS or sum(len(e.to_dict()['changes']) for e in events)+len(changes)>MAX_HEAD_VERSIONS:
        fail('archive_limit')
    header = {k:v[k] for k in ('schema_version','protocol_version','scope','simulation','record_only',
        'operation_accepted','applied','artwork_approved','contract_approved','ready','active','production_enforcement','publication_authorized')}
    event = Event.from_dict(dict(**header,kind='operation-event',sequence=len(events)+1,
        previous_sha256=events[-1].sha256 if events else None,operation_id=v['id'],operation_revision=v['revision'],
        record_sha256=record.sha256,previous_record_sha256=v['previous_sha256'],
        previous_operation_event_sha256=v['previous_event_sha256'],state=v['state'],changes=changes))
    if sum(len(r.encoded) for r in records.values())+sum(len(e.encoded) for e in events)+len(record.encoded)+len(event.encoded)>MAX_ARCHIVE_BYTES:
        fail('archive_limit')
    writer.put_object(record.encoded,expected_sha256=record.sha256)
    _checkpoint('record_blob')
    writer.put_object(event.encoded,expected_sha256=event.sha256)
    _checkpoint('event_blob')
    db.execute('INSERT INTO p4m1_records VALUES (?,?,?)',(v['id'],v['revision'],record.sha256))
    _checkpoint('record_index')
    for c in changes:
        db.execute('INSERT INTO p4m1_heads VALUES (?,?,?,?,?,?)',(*key(c['key']),c['after']['revision'],record.sha256,canonical(c['subjects']).decode(),event.sha256))
        _checkpoint('member_head')
        if c['key']['kind']=='subject':_checkpoint('subject_head')
    pe = writer.event(db,'phase4_operation_recorded',v['id'],dict(sequence=event.to_dict()['sequence'],
        sha256=event.sha256,record_sha256=record.sha256,revision=v['revision']))
    db.execute('INSERT INTO p4m1_journal VALUES (?,?,?)',(event.to_dict()['sequence'],event.sha256,pe))
    _checkpoint('journal_index')
    _index_budget(db)
    _replay(writer,db)
    return event


def commit_operational(*args, **kwargs):
    """Explicit real-operation entry point always fails closed, without writes."""
    require_operational_approval(*args, **kwargs)


def _commit_synthetic(transaction, *, expected_snapshot_sha256, authority=None, cancel=None):
    """Commit complete reviewed proposed state within a disposable trial only.

    expected_snapshot_sha256 pins the prepared value independently. Snapshot
    heads and all M1 subject/dependency/namespace heads are checked under the
    original SQLite write lock. Archived decisions are not live authority.
    """
    from .current_mapping import CurrentTransaction
    if type(transaction) not in {Transaction, CurrentTransaction}:
        fail('typed_transaction')
    from .evidence import ReviewInputs
    from .composition import CompositionContext
    from .candidates import PosterCandidate
    from .identities import IdentityRegistry
    if type(transaction.inputs) is not ReviewInputs or type(transaction.inputs.composition) is not CompositionContext:
        fail('typed_inputs')
    if type(authority) is not SyntheticReviewAuthority:
        require_operational_approval()
    _cancelled(cancel)
    ctx = transaction.inputs.composition
    if (type(ctx.registry) is not IdentityRegistry or type(ctx.candidate) is not PosterCandidate
            or type(ctx.candidate.registry) is not IdentityRegistry):
        fail('typed_inputs')
    authority.trial.require(ctx.candidate)
    root = ctx.registry.operations.root
    if authority.trial.config.cache_dir!=root:
        fail('foreign_authority')
    # A committed retry is an integrity query, not a second application or a
    # revival of expired authority. Exact request/snapshot identities must match.
    writer = SidecarStore(root)
    with writer.transaction() as db:
        state = inspect_db(root,writer,db)
        from .mappings import require_m5_compatible
        if type(transaction) is CurrentTransaction:
            transaction.require_current(writer, db, state)
        else:
            require_m5_compatible(root,writer,db,ctx.candidate)
        op_id = ctx.impact.to_dict()['operation']['id']
        existing = state['commits'].get(op_id)
        if existing is not None:
            snapshot = state['snapshots'][existing['snapshot_sha256']]
            s = snapshot.to_dict()
            if (snapshot.sha256!=expected_snapshot_sha256
                    or s['operation']!=ctx.impact.to_dict()['operation']
                    or s['proposed_sha256']!=ctx.candidate.sha256
                    or s['review_id']!=transaction.review_id or s['review_sha256']!=transaction.review_sha256
                    or s['composition_sha256']!=transaction.inputs.composition_sha256
                    or s['before_sha256']!=(ctx.before.sha256 if ctx.before is not None else None)
                    or s['phase3_json']!=transaction.inputs.phase3.encoded.decode()
                    or transaction.inputs.expected_phase3_sha256!=transaction.inputs.phase3.sha256
                    or s['observation_pins_json']!=canonical(observation_pins(transaction.inputs)).decode()
                    or s['expected_snapshots']!=json.loads(transaction.expected_snapshots_json)):
                fail('revision_replay_with_different_content')
            return dict(**FLAGS,isolated_committed=True,retry=True,currentness='integrity-only-prior-commit',**existing)
        snapshot = transaction.prepare()
        if snapshot.sha256 != expected_snapshot_sha256:
            fail('snapshot_pin')
        s = snapshot.to_dict()
        validate_state_impact(ctx.candidate,state)
        if type(transaction) is CurrentTransaction:
            transaction.verify_before(snapshot, writer, db, state)
        else:
            verify_before(snapshot,state['snapshots'],state['outputs'])
        for identity, expected in s['expected_snapshots'].items():
            if state['outputs'].get(identity,{}).get('snapshot_sha256') != expected:
                raise Conflict('Authoritative isolated snapshot changed')
        _checkpoint('before_review')
        reviews = ReviewArchive(root)
        approved,bundle = reviews.current(transaction.review_id,expected_sha256=transaction.review_sha256,
            inputs=transaction.inputs,authority=authority)
        if approved.to_dict()['state']!='MAINTAINER_APPROVED' or bundle.sha256!=s['review_bundle_sha256']:
            fail('complete_review_required')
        _checkpoint('after_review')
        # The expensive replay is current under the same write lock. Verify
        # exact grants again after it, closing a revocation/expiry during replay.
        approved,_,review_records = reviews.read(transaction.review_id,expected_sha256=transaction.review_sha256)
        reviews._attribution(approved,review_records,authority)
        _cancelled(cancel)
        writer.put_object(snapshot.encoded,expected_sha256=snapshot.sha256)
        _checkpoint('snapshot_blob')
        records,events,latest,heads = _replay(writer,db)
        intent = latest[op_id][0]
        event = next(e for e in events if e.sha256==s['operation']['event_sha256'])
        marker = _successor(snapshot,intent,event)
        committed_event = _append_m1(writer,db,marker,records,events,latest,heads)
        writer.event(db,'phase4_isolated_commit',op_id,dict(snapshot_sha256=snapshot.sha256,
            record_sha256=marker.sha256,review_sha256=s['review_sha256'],members=s['members'],
            isolated_committed=True,**FLAGS))
        if type(transaction) is CurrentTransaction:
            transaction.record_lineage(snapshot, writer, db)
        _checkpoint('receipt_index')
        # Original M1 and M5 immutable restart verification must accept all
        # proposed rows before the single existing Package E COMMIT.
        inspect_db(root,writer,db)
        _checkpoint('before_commit')
        _final_inputs(transaction,snapshot)
        reviews._attribution(approved,review_records,authority)
        _cancelled(cancel)
        result = dict(**FLAGS,isolated_committed=True,retry=False,currentness='verified-at-isolated-commit',snapshot_sha256=snapshot.sha256,
            record_sha256=marker.sha256,event_sha256=committed_event.sha256,revision=marker.to_dict()['revision'])
    _checkpoint('after_commit')
    return result


def commit_synthetic(transaction, *, expected_snapshot_sha256, authority=None, cancel=None):
    """Complete isolated commit or an explicit conflict; never automatic rebase.

    The original SQLite busy timeout stays unchanged. A writer that cannot
    acquire its lock may retry with the same exact inputs after recovery.
    """
    try:
        return _commit_synthetic(transaction,expected_snapshot_sha256=expected_snapshot_sha256,
            authority=authority,cancel=cancel)
    except sqlite3.OperationalError as error:
        if getattr(error,'sqlite_errorcode',None) in {sqlite3.SQLITE_BUSY,sqlite3.SQLITE_LOCKED}:
            raise Conflict('Isolated writer busy; recover and retry exact inputs') from error
        raise
