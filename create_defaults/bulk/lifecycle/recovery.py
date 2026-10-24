"""Read-only M5 recovery from the original M1 journal and Package E events.

Integrity-only inspection never restores live authority or makes archived reviews
current. Unindexed blobs remain orphans; there is no replay queue or auto-apply.
"""
from hashlib import sha256
from io import BytesIO
import inspect
import json

from PIL import Image

from ..common import canonical, fingerprint
from .composition_models import CompositionEvidence
from .evidence import ReviewBundle
from .models import key
from .operations import DefinitionSnapshot, REFERENCE, FLAGS, fail, payload
from .previews import CompositionArchive
from .review import ReviewArchive
from .storage import OperationStore, _replay, MAX_ARCHIVE_BYTES


def _checkpoint(name):
    """Internal fault-injection seam. No caller-controlled validation hook."""


def _successor(snapshot, intent, event):
    """Deterministic marker record; the reviewed intent itself is never edited."""
    from .models import Operation
    s = snapshot.to_dict()
    value = intent.to_dict()
    changes = {key(c['key']):c['after'] for c in event.to_dict()['changes']}
    reads = [dict(r, **{f:changes.get(key(r),r)[f] for f in ('revision','sha256')}) for r in value['reads']]
    refs = value['references']+[dict(kind='evidence',id=REFERENCE,subject=r['id'],sha256=snapshot.sha256) for r in value['subjects']]
    refs.sort(key=lambda r:(r['kind'],r['id'],r['subject']))
    return Operation.from_dict(dict(value,revision=value['revision']+1,content_revision=value['content_revision']+1,
        previous_sha256=intent.sha256,previous_event_sha256=event.sha256,state='draft',reason=None,
        reads=reads,references=refs))


def verify_before(snapshot, snapshots, outputs):
    """Every supplied prior member must be authoritative, including controls."""
    s = snapshot.to_dict()
    if s['before_graph_json'] is None:
        return
    from .evidence import _scope
    from ..contracts.expanded.graph import Snapshot
    before = Snapshot.create(payload(s['before_graph_json'])).index()
    for identity in before.outputs:
        pin = outputs.get(identity,{}).get('snapshot_sha256')
        if pin is None:
            fail('before_not_committed')
        prior = Snapshot.create(payload(snapshots[pin].to_dict()['proposed_graph_json'])).index()
        if before.outputs[identity]!=prior.outputs[identity] or _scope(before,[identity])!=_scope(prior,[identity]):
            fail('before_dependency_substitution')


def inspect_db(root, store, db):
    records, events, latest, heads = _replay(store,db)
    found = db.execute("SELECT name FROM sqlite_master WHERE name LIKE 'p4m4_%'").fetchall()
    if found:
        reviews = ReviewArchive(root)
        histories, bundles, decisions = reviews._replay(db)
    else:
        histories, bundles, decisions = {}, {}, {}
    packages = [tuple(r) for r in db.execute("SELECT subject,payload FROM events WHERE kind='phase4_isolated_commit' ORDER BY sequence")]
    expected_events, snapshots, committed, outputs = [], {}, {}, {}
    budget = 0
    archive = CompositionArchive(root,readonly=True)
    checked = set()

    def check_bytes(ref, expected=None):
        nonlocal budget
        if (ref,canonical(expected)) in checked:
            return
        raw = archive.read_bytes(ref)
        budget += len(raw)
        if budget>MAX_ARCHIVE_BYTES:
            fail('archive_limit')
        if expected is not None:
            if (sha256(raw).hexdigest(),len(raw)) != (expected['sha256'],expected['bytes']):
                fail('archived_artwork_hash')
            with Image.open(BytesIO(raw)) as image:
                image.load()
                if (image.format,image.mode,list(image.size)) != (expected['format'],expected['mode'],expected['dimensions']):
                    fail('archived_artwork_geometry')
        checked.add((ref,canonical(expected)))

    for event in events:
        ev = event.to_dict()
        record = records[ev['operation_id'],ev['operation_revision']]
        v = record.to_dict()
        markers = [r for r in v['references'] if r['id']==REFERENCE]
        if not markers:
            continue
        if v['previous_sha256'] is None:
            fail('unprepared_commit')
        prior = records[v['id'],v['revision']-1]
        old_markers = [r for r in prior.to_dict()['references'] if r['id']==REFERENCE]
        if old_markers:
            # M1 cancellation/history after the commit cannot apply it again.
            if markers != old_markers:
                fail('commit_marker_rewrite')
            continue
        pins = {r['sha256'] for r in markers}
        if len(pins)!=1 or sorted(r['subject'] for r in markers)!=sorted(s['id'] for s in v['subjects']):
            fail('partial_commit_marker')
        pin = pins.pop()
        raw = store.read_object(pin)
        budget += len(raw)
        if budget>MAX_ARCHIVE_BYTES:
            fail('archive_limit')
        snapshot = DefinitionSnapshot.from_bytes(raw)
        if snapshot.sha256 != pin:
            fail('snapshot_pin')
        s = snapshot.to_dict()
        intent_event = next(e for e in events if e.sha256==s['operation']['event_sha256'])
        if (prior.encoded.decode()!=s['intent_json'] or prior.sha256!=s['operation']['sha256']
                or _successor(snapshot,prior,intent_event)!=record or v['id'] in committed):
            fail('commit_intent_binding')
        history = histories.get(s['review_id'],[])
        state = next((r for r in history if r.sha256==s['review_sha256']),None)
        if state is None or state.to_dict()['state']!='MAINTAINER_APPROVED':
            fail('archived_review_required')
        bundle = bundles[state.to_dict()['bundle_sha256']]
        b = bundle.to_dict()
        if (bundle.sha256 != s['review_bundle_sha256'] or b['composition_sha256'] != s['composition_sha256']
                or b['members'] != s['members'] or b['selected_appearance'] != s['selected_appearance']):
            fail('archived_review_binding')
        material = payload(b['material_json'])
        from .identity_models import ImpactEvidence, RegistrySnapshot
        impact = ImpactEvidence.from_dict(payload(s['impact_json']))
        from ..contracts.evidence_consumption import ConsumptionAttestation
        phase3 = ConsumptionAttestation.from_dict(payload(s['phase3_json']))
        if (material['operation']!=s['operation'] or material['impact_sha256']!=impact.sha256
                or material['registry_sha256']!=payload(s['proposed_json'])['registry_sha256']
                or material['phase3_binding_sha256']!=phase3.to_dict()['binding_sha256']):
            fail('archived_material_binding')
        registry = RegistrySnapshot.from_bytes(store.read_object(material['registry_sha256']))
        entries = {e['id']:e for e in registry.to_dict()['entries']}
        if any(entries.get(i)!=s['entries'][i] for i in s['members']):
            fail('archived_identity_binding')
        if store.read_object(s['composition_sha256']).decode()!=s['composition_json']:
            fail('archived_composition_binding')
        for appearance in CompositionEvidence.from_dict(payload(s['composition_json'])).to_dict()['views']:
            from ..workers import tasks_from_manifest, compose as native_compose
            tasks = {t.id:t for t in tasks_from_manifest(payload(appearance['manifest_json']))}
            renderer_id = fingerprint(inspect.getsource(native_compose))
            for member in appearance['members']:
                check_bytes(member['object_sha256'],member)
                receipt = payload(store.read_object(member['receipt_object_sha256']).decode())
                job = db.execute('SELECT status,receipt,spec,fingerprint FROM jobs WHERE id=?',(receipt.get('job_id'),)).fetchone()
                spec = dict(task=tasks[member['job_id']].spec(),renderer_identity=renderer_id)
                if (job is None or job['status']!='verified' or job['receipt']!=canonical(receipt).decode()
                        or job['spec']!=canonical(spec).decode() or job['fingerprint']!=fingerprint(spec)
                        or receipt.get('sha256')!=member['sha256'] or receipt.get('receipt_sha256')!=member['receipt_sha256']
                        or fingerprint({k:x for k,x in receipt.items() if k!='receipt_sha256'})!=member['receipt_sha256']):
                    fail('archived_receipt_binding')
            for source in appearance['sources']:
                raw_source = archive.read_bytes(source['object_sha256'])
                if sha256(raw_source).hexdigest()!=source['sha256']:
                    fail('archived_source_hash')
                check_bytes(source['object_sha256'])
        verify_before(snapshot,snapshots,outputs)
        for i,previous in s['expected_snapshots'].items():
            if outputs.get(i,{}).get('snapshot_sha256')!=previous:
                fail('snapshot_history_conflict')
            if s['operation_type']=='UPDATE':
                old = snapshots[previous].to_dict()
                old_proposal = payload(old['proposed_json'])
                before = payload(s['before_json'])
                # Prove the exact old effective definition and dependency scope,
                # not just the mutable name or a historical receipt.
                if old_proposal['effective_definitions'][i]!=before['effective_definitions'][i]:
                    fail('before_definition_substitution')
                from .evidence import _scope
                from ..contracts.expanded.graph import Snapshot
                old_graph = Snapshot.create(payload(old['proposed_graph_json'])).index()
                before_graph = Snapshot.create(payload(s['before_graph_json'])).index()
                if (old_graph.outputs[i]!=before_graph.outputs[i] or _scope(old_graph,[i])!=_scope(before_graph,[i])):
                    fail('before_dependency_substitution')
                before_ctx = before['manifest']['jobs']
                if not any(j['poster_id']==i for j in before_ctx):
                    fail('before_member_missing')
                if old['entries'][i]['names']['local_path']!=s['entries'][i]['names']['local_path'] or old['entries'][i]['names']['public_path']!=s['entries'][i]['names']['public_path']:
                    fail('rename_requires_m6')
            outputs[i]=dict(snapshot_sha256=pin,operation_id=v['id'],operation_revision=v['revision'],artwork=s['artwork'][i])
        snapshots[pin]=snapshot
        committed[v['id']]=dict(snapshot_sha256=pin,record_sha256=record.sha256,event_sha256=event.sha256,revision=v['revision'])
        expected_events.append((v['id'],canonical(dict(snapshot_sha256=pin,record_sha256=record.sha256,
            review_sha256=s['review_sha256'],members=s['members'],isolated_committed=True,**FLAGS)).decode()))
    if packages != expected_events:
        fail('commit_event_index')
    return dict(outputs=outputs,commits=committed,snapshots=snapshots,
        journal_sha256=events[-1].sha256 if events else None,heads=heads,records=records,events=events)


def recover(root):
    """Report committed snapshots and pending records; never retry automatically."""
    operations = OperationStore(root)
    with operations.contracts.read_connection() as db:
        state = inspect_db(operations.root, operations.contracts, db)
    pending = sorted({r.to_dict()['id'] for r in state['records'].values()}-state['commits'].keys())
    return dict(schema_version=1,kind='isolated-transaction-recovery',**FLAGS,
        currentness='integrity-only-currentness-unknown',commits=state['commits'],outputs=state['outputs'],
        pending_operations=pending,journal_sha256=state['journal_sha256'],
        orphan_policy='unindexed objects retained; never applied or deleted')
