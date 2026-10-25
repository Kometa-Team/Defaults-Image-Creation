"""M6 immutable mapping plans and isolated identity-preserving transactions.

No catalog writer, network client, live authenticator or new persistence index.
M1 records, M2 registry snapshots and Package E events are the authority for
isolated state. Old M5 composition snapshots and receipts are never rewritten.
"""
from copy import deepcopy
from functools import lru_cache
from hashlib import sha256 as digest
from pathlib import Path, PurePosixPath
import json
import sqlite3
import unicodedata

from ..common import Conflict, canonical, confined, fingerprint, path_key, sha256
from ..contracts.models import Document, decode_json
from ..contracts.expanded.graph import Snapshot
from ..definitions import Definition
from .apply import _append_m1, _cancelled
from .basis import historical_basis
from .evidence import ReviewDecision
from .identities import IdentityRegistry, aliases_for, namespace_inventory, transition
from .identity_models import RegistrySnapshot, portable
from .models import Operation, key, namespace_key
from .operations import FLAGS, payload
from .package_e import SidecarStore
from .previews import CompositionArchive
from .recovery import inspect_db, committed_graph
from .retirement import fail, validate_delete, tombstone
from .review_authority import SyntheticReviewAuthority, verify_authority, require_operational_approval
from .storage import _replay, MAX_EVENTS, MAX_ARCHIVE_BYTES

REFERENCE = 'synthetic.lifecycle.mapping'
COMMIT = 'phase4_mapping_committed'
HEADER = dict(schema_version=1, kind='isolated-mapping-plan', **FLAGS)
FIELDS = set(HEADER) | {'operation_id', 'operation', 'registry_id', 'registry_sha256',
    'base_sha256', 'members', 'before', 'after', 'definitions', 'definition_keys',
    'retained', 'tombstones', 'previous_sha256', 'compensates'}


def _checkpoint(name):
    """Internal crash-test seam, never supplied by a caller."""


def _subject(identity):
    # Same permanent-ID bridge as M2, independent of names and paths.
    return 'synthetic.item.'+fingerprint(identity)


@lru_cache(maxsize=1)
def _validator():
    from jsonschema import Draft202012Validator
    from ..definitions import StrictValidator
    schema=decode_json((Path(__file__).parent/'schemas/mappings-v1.schema.json').read_bytes())
    Draft202012Validator.check_schema(schema)
    return StrictValidator(schema)


class MappingPlan(Document):
    def __init__(self, value):
        raw = canonical(value)
        v = decode_json(raw)
        if len(raw) > 8*1024*1024 or type(v) is not dict or set(v) != FIELDS or next(_validator().iter_errors(v),None):
            fail('plan_shape')
        if any(v[k] != x or type(v[k]) is not type(x) for k, x in HEADER.items()):
            fail('plan_flags')
        if v['operation'] not in {'RENAME', 'DELETE'}:
            fail('operation')
        ids = v['members']
        if type(ids) is not list or not ids or ids != sorted(set(ids)) or len(ids) > 64:
            fail('membership')
        for f in ('before', 'after', 'definitions', 'definition_keys', 'retained'):
            if type(v[f]) is not dict or sorted(v[f]) != ids:
                fail('membership')
        from ..contracts.registry import require_hash
        for f in ('registry_sha256', 'base_sha256'):
            require_hash(v[f])
        if v['previous_sha256'] is not None: require_hash(v['previous_sha256'])
        for i in ids:
            a, b = v['before'][i], v['after'][i]
            if a['id'] != i or b['id'] != i or a['tombstone_sha256'] is not None:
                fail('identity_binding')
            from .identity_models import entry_check
            entry_check(a);entry_check(b)
            for f in ('id', 'category', 'semantic', 'variant', 'origin', 'historical_sha256', 'original_names'):
                if a[f] != b[f]: fail('identity_reassignment')
            if b['revision'] != a['revision']+1:
                fail('entry_revision')
            for f in ('local_path', 'public_path'):
                if b['names'][f] is not None: portable(b['names'][f], new=True)
            if v['operation'] == 'DELETE':
                t = tombstone(v['operation_id'], a, v['retained'][i])
                if v['tombstones'].get(i) != t or b['tombstone_sha256'] != fingerprint(t) or b['names'] != a['names']:
                    fail('tombstone_binding')
            elif b['tombstone_sha256'] is not None or v['tombstones']:
                fail('rename_tombstone')
        object.__setattr__(self, 'encoded', raw)

    @classmethod
    def from_bytes(cls, raw):
        if type(raw) is not bytes or len(raw) > 8*1024*1024: fail('plan_bound')
        result = cls.from_dict(decode_json(raw))
        if result.encoded != raw: fail('noncanonical_plan')
        return result


def _ledger(store, db):
    """Replay immutable M1 references AND their Package E commit cross-index."""
    records, events, latest, heads = _replay(store, db)
    plans, commits, touched, expected = [], {}, set(), []
    budget = 0
    for event in events:
        record = records[(event.to_dict()['operation_id'], event.to_dict()['operation_revision'])]
        r = record.to_dict()
        refs = [x for x in r['references'] if x['id'] == REFERENCE]
        if not refs: continue
        pin = refs[0]['sha256']
        raw = store.read_object(pin); budget += len(raw)
        if budget > MAX_ARCHIVE_BYTES: fail('archive_bound')
        plan = MappingPlan.from_bytes(raw); p = plan.to_dict()
        if (plan.sha256 != pin or p['operation_id'] != r['id'] or p['operation'] != r['operation']
                or r['request_sha256'] != pin or r['revision'] != 2
                or sorted(x['subject'] for x in refs) != sorted(_subject(i) for i in p['members'])
                or any(x['sha256'] != pin for x in refs)
                or p['previous_sha256'] != (plans[-1].sha256 if plans else None)):
            fail('mapping_index')
        intent = records.get((r['id'], 1))
        if intent is None or intent.to_dict()['request_sha256'] != pin:
            fail('mapping_intent')
        decisions = [x for x in r['references'] if x['id'] in {'synthetic.mapping.confirm', 'synthetic.mapping.approve'}]
        pins = {x['id']:x['sha256'] for x in decisions}
        if len(decisions) != 2 or len(pins) != 2: fail('approval_evidence')
        pair = [ReviewDecision.from_bytes(store.read_object(pins[n])) for n in
                ('synthetic.mapping.confirm', 'synthetic.mapping.approve')]
        _decisions(plan, pair, authority=None, root=store.root, historical=True)
        data = dict(plan_sha256=pin, record_sha256=record.sha256, event_sha256=event.sha256,
                    registry_sha256=p['registry_sha256'])
        expected.append((r['id'], canonical(data).decode()))
        if r['id'] in commits: fail('duplicate_mapping_commit')
        commits[r['id']] = data; plans.append(plan); touched.update(p['members'])
    actual = [tuple(r) for r in db.execute('SELECT subject,payload FROM events WHERE kind=? ORDER BY sequence LIMIT ?', (COMMIT, MAX_EVENTS+1))]
    if actual != expected: fail('mapping_commit_index')
    return plans, commits, touched


def _state(registry, store, db):
    # Reconstruct M5 and M6 commits in their shared M1 event order. Starting
    # from today's M5 graph would incorrectly apply an old M6 plan to a later
    # unrelated ADD/UPDATE. No second current-state index is persisted.
    state = inspect_db(store.root, store, db)
    plans, commits, touched = _ledger(store, db)
    by_operation={p.to_dict()['operation_id']:p for p in plans}
    definitions={};retained={};keys={};expected_entries={};value=None;seen_m6=set()
    entries={e['id']:e for e in registry.view().entries()}
    from .operations import REFERENCE as M5_REFERENCE
    from .evidence import _scope
    for event in state['events']:
        e=event.to_dict();record=state['records'][(e['operation_id'],e['operation_revision'])].to_dict()
        refs=[r for r in record['references'] if r['id']==M5_REFERENCE]
        if refs:
            snapshot=state['snapshots'][refs[0]['sha256']].to_dict()
            index=Snapshot.create(payload(snapshot['proposed_graph_json'])).index()
            if value is None:
                value=dict(schema_version=1,kind='m5-dependency-snapshot',basis=payload(snapshot['proposed_graph_json'])['basis'],nodes={},outputs={},unresolved=[])
            for i in snapshot['members']:
                if i in seen_m6:
                    fail('m5_reuses_m6_identity')
                for n,row in _scope(index,[i]).items():
                    # M5's original replay separately validates source updates;
                    # overwrite the selected closure, then validate all outputs.
                    value['nodes'][n]=deepcopy(row)
                value['outputs'][i]=deepcopy(index.outputs[i])
                definitions[i]=payload(snapshot['proposed_json'])['effective_definitions'][i]
                retained[i]=dict(snapshot_sha256=refs[0]['sha256'],artwork=snapshot['artwork'][i])
                keys[i]=i;expected_entries[i]=snapshot['entries'][i]
            _prune(value);Snapshot.create(value)
        if e['operation_id'] in by_operation and any(r['id']==REFERENCE for r in record['references']):
            plan=by_operation[e['operation_id']];p=plan.to_dict();seen_m6.update(p['members'])
            if value is None or p['base_sha256']!=fingerprint(dict(graph=value,definitions=definitions,keys=keys)):
                fail('mapping_epoch')
            for i in p['members']:
                if p['before'][i]!=expected_entries.get(i): fail('mapping_before_entry')
                expected_entries[i]=p['after'][i]
                if i not in value['outputs'] or retained[i] != p['retained'][i]: fail('retention_binding')
                if i not in entries: fail('mapping_entry_missing')
                if p['operation']=='RENAME' and _rename(p['before'][i],definitions[i],p['definitions'][i]) != p['after'][i]['names']:
                    fail('mapping_definition_replay')
                keys[i] = p['definition_keys'][i]
                definitions[i] = p['definitions'][i]
                if p['operation'] == 'DELETE':
                    del value['outputs'][i]
                else:
                    value['outputs'][i].update(local_path=p['after'][i]['names']['local_path'],
                                              public_path=p['after'][i]['names']['public_path'])
                    node=value['outputs'][i]['node']
                    value['nodes'][node]['sha256']=fingerprint(dict(prior=value['nodes'][node]['sha256'],mapping_plan=plan.sha256))
                    value['outputs'][i]['context_sha256']=fingerprint(dict(prior=value['outputs'][i]['context_sha256'],mapping_plan=plan.sha256))
                    # The renamed definition is a new immutable dependency
                    # version; old composition contexts remain archived.
                    dn='definition:'+i
                    if dn in value['nodes']: value['nodes'][dn]['sha256']=fingerprint(p['definitions'][i])
                    old_source=p['before'][i]['names']['source'];new_source=p['after'][i]['names']['source']
                    if old_source and old_source!=new_source:
                        old_node='asset:'+old_source['path'];new_node='asset:'+new_source['path']
                        if old_node in value['nodes']:
                            source=value['nodes'].pop(old_node)
                            value['nodes'][new_node]=dict(source,identity=new_source['path'])
                            for n in value['nodes'].values():
                                n['dependencies']=sorted(new_node if d==old_node else d for d in n['dependencies'])
            # Only retained output closures remain active; historical nodes stay
            # in immutable snapshots, never physically removed from the archive.
            needed = set(); pending = [x['node'] for x in value['outputs'].values()]
            while pending:
                n = pending.pop()
                if n not in needed: needed.add(n); pending.extend(value['nodes'][n]['dependencies'])
            value['nodes'] = {n:x for n,x in value['nodes'].items() if n in needed}
            for i in p['members']:
                if p['operation'] == 'DELETE': definitions.pop(i); keys.pop(i)
    graph=Snapshot.create(value) if value is not None else None
    if any(entries.get(i)!=entry for i,entry in expected_entries.items()):
        fail('uncommitted_registry_revision')
    if plans:
        # M2 independently replays every registry revision, aliases/tombstones.
        histories=registry.history()
        for plan in plans:
            p=plan.to_dict()
            prior=next((h for h in histories if h.snapshot.sha256==p['registry_sha256']),None)
            after=next((h for h in histories if prior and h.head.revision==prior.head.revision+1),None)
            if after is None or any(after.entry(i)!=p['after'][i] for i in p['members']):
                fail('partial_registry_commit')
    return state,graph,definitions,keys,retained,plans,commits,entries


def _prune(value):
    needed=set();pending=[x['node'] for x in value['outputs'].values()]
    while pending:
        n=pending.pop()
        if n not in needed:
            needed.add(n);pending.extend(value['nodes'][n]['dependencies'])
    value['nodes']={n:x for n,x in value['nodes'].items() if n in needed}


def _rename(entry, definition, proposed):
    """Accept only nonvisual changes; never disguise caption/style edits as names."""
    a = Definition.create(definition).data
    b = Definition.create(proposed).data
    if b['id'] != entry['id'] or b['category'] != entry['category'] or b['generator'] is not None:
        fail('identity_or_generator_change')
    check = deepcopy(b)
    for field in ('display_name', 'output'): check[field] = a[field]
    for field in ('out_name', 'logo'): check['composer'][field] = a['composer'][field]
    if check != a: fail('material_change_requires_composition_review')
    # Use the actual compositor's filename algorithm. No reverse slug/titlecase.
    from create_defaults.create_poster import PosterOptions, output_filename
    from ..planner import effective_parameters
    parameters = effective_parameters(b['composer'])
    filename = output_filename(PosterOptions(**parameters), parameters['base_color'])
    if b['output']['filename'] != filename: fail('definition_filename')
    local = '/'.join(filter(None, ('defaults-en', b['output']['directory'], filename)))
    public = b['output']['remote_paths'].get('en')
    if set(b['output']['remote_paths']) != {'en'}: fail('language_scope')
    if public is not None and PurePosixPath(public).name != filename: fail('authoritative_filename')
    old = entry['names']; source = deepcopy(old['source'])
    if source is None and a['composer']['logo'] != b['composer']['logo']: fail('source_ownership')
    if source is not None:
        if a['composer']['logo'] != source['path']: fail('source_ownership')
        source['path'] = b['composer']['logo']; portable(source['path'], new=True)
    if source is not None and Path(source['path']).suffix.lower() != '.png': fail('source_png_required')
    names = dict(display_name=b['display_name'], rendered_caption=old['rendered_caption'],
                 source=source, local_path=local, public_path=public)
    if any(unicodedata.normalize('NFC', x) != x for x in (b['display_name'], filename)):
        fail('non_nfc_name')
    # Route changes need a separately approved category adapter.
    if PurePosixPath(local).parent != PurePosixPath(old['local_path']).parent:
        fail('category_route')
    if (public is None) != (old['public_path'] is None) or public is not None and PurePosixPath(public).parent != PurePosixPath(old['public_path']).parent:
        fail('category_route')
    return names


def prepare(registry, *, operation_id, operation, definitions=None, members=None,
            definition_keys=None, compensates=None):
    """Read-only proposal against exact committed M5/M6 state, not loose YAML.

    Existing M5 adapters bound execution to assigned English Genre logo outputs.
    Historical/generator/overlay execution remains closed pending the existing
    Phase 3 adapters; immutable historical identities are never invented here.
    """
    if type(registry) is not IdentityRegistry: fail('typed_registry')
    if operation not in {'RENAME', 'DELETE'}: fail('operation')
    definitions = {} if definitions is None else definitions
    ids = sorted(definitions) if operation == 'RENAME' else sorted(members or [])
    if not ids or len(ids) != len(set(ids)): fail('membership')
    with registry.operations.contracts.read_connection() as db:
        state, graph, current, keys, retained, plans, commits, entries = _state(registry, registry.operations.contracts, db)
    if graph is None or not set(ids) <= graph.index().outputs.keys(): fail('before_not_committed')
    if operation_id in commits: fail('operation_already_committed')
    before = {i:deepcopy(entries[i]) for i in ids}; after = deepcopy(before)
    index = graph.index()
    if index.unresolved: fail('uncertain_dependency_impact')
    for i in ids:
        if before[i]['tombstone_sha256'] is not None: fail('tombstone_reuse')
        if set(index.outputs[i]['companions']) - set(ids): fail('required_companion')
    if operation == 'DELETE': validate_delete(index, entries, ids)
    result = dict(**HEADER, operation_id=operation_id, operation=operation,
        registry_id=registry.identity, registry_sha256=registry.view().snapshot.sha256,
        base_sha256=fingerprint(dict(graph=graph.data(), definitions=current, keys=keys)),
        members=ids, before=before, after=after,
        definitions={i:deepcopy(definitions[i] if operation == 'RENAME' else current[i]) for i in ids},
        definition_keys={i:(definition_keys or {}).get(i, keys[i]) for i in ids},
        retained={i:retained[i] for i in ids}, tombstones={},
        previous_sha256=plans[-1].sha256 if plans else None, compensates=compensates)
    if definition_keys is not None and set(definition_keys) != set(ids): fail('definition_key_membership')
    occupied = {path_key(i):i for i in retained}
    occupied.update({path_key(k):i for i,k in keys.items()})
    for plan in plans:
        for i,k in plan.to_dict()['definition_keys'].items(): occupied[path_key(k)] = i
    for i in ids:
        k = result['definition_keys'][i]; portable(k, new=True)
        if occupied.get(path_key(k), i) != i: fail('definition_key_collision')
        occupied[path_key(k)] = i
        e = after[i]
        if operation == 'RENAME':
            e['names'] = _rename(before[i], current[i], definitions[i])
            a,b=before[i]['names'],e['names']
            changed=[]
            if a['local_path']!=b['local_path']: changed.append(index.outputs[i]['node'])
            if a['source']!=b['source'] and a['source']: changed.append('asset:'+a['source']['path'])
            impact=index.impact(changed)
            if changed and (not impact['impact_complete'] or set(impact['affected_outputs'])-set(ids)):
                fail('dependent_mapping_requires_complete_adapter')
        else:
            t = tombstone(operation_id, before[i], retained[i]); result['tombstones'][i] = t
            e['tombstone_sha256'] = fingerprint(t)
        aliases = set(aliases_for(before[i]['names'])) | {(a['namespace'],a['value']) for a in before[i]['aliases']}
        e.update(revision=e['revision']+1, aliases=[dict(namespace=n,value=v) for n,v in sorted(aliases)])
    for i in ids:
        a,b=before[i]['names']['source'],after[i]['names']['source']
        if a and b and a['path']!=b['path']:
            for j in historical_basis().ids:
                src=historical_basis().row(j)['identity']['source']
                if src and j!=i and path_key(src['path'])==path_key(b['path']): fail('historical_source_collision')
            for j,e in entries.items():
                sources=[e['names']['source']['path']] if e['names']['source'] else []
                sources += [x['value'] for x in e['aliases'] if x['namespace']=='source']
                if j!=i and any(path_key(x)==path_key(b['path']) for x in sources): fail('source_alias_collision')
    plan = MappingPlan.from_dict(result)
    _registry_successor(registry, plan)  # Full historical/external namespace.
    if operation == 'RENAME' and all(before[i]['names'] == after[i]['names'] and result['definition_keys'][i] == keys[i] for i in ids):
        fail('empty_rename')
    if compensates is not None:
        old = next((p.to_dict() for p in plans if p.sha256 == compensates), None)
        if old is None or old['operation'] != 'RENAME' or old['members'] != ids or operation != 'RENAME' or any(after[i]['names'] != old['before'][i]['names'] for i in ids):
            fail('invalid_compensation')
    return plan


def _registry_successor(registry, plan):
    p = plan.to_dict(); view = registry.view()
    if view.snapshot.sha256 != p['registry_sha256']: raise Conflict('Registry changed')
    v = view.snapshot.to_dict()
    v['entries'] = sorted([e for e in v['entries'] if e['id'] not in p['members']]+list(p['after'].values()), key=lambda e:e['id'])
    v['requests'].append(dict(token='m6-'+fingerprint(p['operation_id']), request_sha256=plan.sha256, result_id=p['members'][0]))
    v['requests'].sort(key=lambda r:r['token'])
    v.update(revision=v['revision']+1, previous_sha256=view.snapshot.sha256)
    context=json.loads(v['namespace_context_json'])
    from ..contracts.destination_preflight.models import DestinationInventory
    inventory=DestinationInventory.from_bytes(registry.operations.contracts.read_object(context['inventory_sha256']))
    external,_=namespace_inventory(inventory,context['inventory_sha256'],context['root'])
    result=RegistrySnapshot.from_dict(v); transition(view.snapshot,result,external)
    return result


def _request(registry, plan):
    from .impact import _coordination
    p = plan.to_dict(); ids = p['members']
    with registry.operations.contracts.read_connection() as db:
        _, graph, _, _, _, _, _, _ = _state(registry, registry.operations.contracts, db)
    from .evidence import _scope
    nodes = sorted(_scope(graph.index(), ids))
    mappings = lambda field:{i:dict(category=p[field][i]['category'],variant=p[field][i]['variant'],
        **{k:p[field][i]['names'][k] for k in ('local_path','public_path')}) for i in ids}
    details = dict(affected_outputs=ids,read_set=nodes,write_set=nodes,
                   before_mappings=mappings('before'),after_mappings=mappings('after'))
    subjects,keys,writes,namespaces=_coordination(registry,details)
    # Serialize all registry changes; UPDATE already consumes registry evidence.
    h=dict(kind='evidence',id=registry.subject); keys[key(h)]=h
    heads={key(h):h for h in registry.operations.inspect()['heads']}
    refs=[dict(kind='evidence',id='synthetic.mapping.plan',subject=s,sha256=plan.sha256) for s in subjects]
    if p['operation']=='DELETE':
        refs += [dict(kind='tombstone',id='synthetic.tombstone.'+fingerprint(i),subject=_subject(i),sha256=fingerprint(p['tombstones'][i])) for i in ids]
    base=registry.operations.history(registry.operation_id)[0].to_dict()
    header={k:base[k] for k in ('schema_version','protocol_version','scope','simulation','record_only',
        'operation_accepted','applied','artwork_approved','contract_approved','ready','active','production_enforcement','publication_authorized')}
    return Operation.from_dict(dict(**header,kind='operation-record',id=p['operation_id'],operation=p['operation'],
        revision=1,content_revision=1,previous_sha256=None,previous_event_sha256=None,state='draft',reason=None,
        request_sha256=plan.sha256,subjects=[dict(id=_subject(i),before_sha256=fingerprint(p['before'][i]),
            proposed_sha256=None if p['operation']=='DELETE' else fingerprint(p['after'][i])) for i in sorted(ids,key=_subject)],
        reads=[dict(**keys[k],subjects=[keys[k]['id']] if keys[k]['kind']=='subject' else subjects,
            revision=heads.get(k,{}).get('revision',0),sha256=heads.get(k,{}).get('sha256')) for k in sorted(keys)],
        writes=[writes[k] for k in sorted(writes)],namespaces=[namespaces[k] for k in sorted(namespaces)],
        references=sorted(refs,key=lambda r:(r['kind'],r['id'],r['subject']))))


def propose(registry, plan):
    if type(plan) is not MappingPlan: fail('typed_plan')
    p=plan.to_dict()
    current=prepare(registry,operation_id=p['operation_id'],operation=p['operation'],definitions=p['definitions'] if p['operation']=='RENAME' else None,
        members=p['members'],definition_keys=p['definition_keys'],compensates=p['compensates'])
    if current.encoded != plan.encoded: raise Conflict('Mapping plan changed before commit')
    prior=registry.operations.history(p['operation_id'])
    if prior:
        if prior[0].to_dict()['request_sha256'] != plan.sha256: raise Conflict('Operation identity occupied')
        return prior[0]
    writer=SidecarStore(registry.operations.root); writer.put_object(plan.encoded,expected_sha256=plan.sha256)
    record=_request(registry,plan)
    registry.operations.append(record,expected_revision=0,expected_sha256=None,expected_event_sha256=None)
    return record


def _decisions(plan, decisions, *, authority, root, historical=False):
    if type(decisions) not in {list,tuple} or len(decisions)!=2 or any(type(d) is not ReviewDecision for d in decisions):
        fail('two_stage_review_required')
    a,b=[d.to_dict() for d in decisions]
    for v in (a,b):
        if v['context_sha256'] != plan.sha256 or v['bundle_sha256'] != plan.sha256 or v['review_id'] != 'synthetic.review.m6-'+fingerprint(plan.to_dict()['operation_id']):
            fail('review_context')
    if ((a['role'],a['action'],a['confirmation_sha256']) != ('submitter','confirm',None)
            or (b['role'],b['action'],b['confirmation_sha256']) != ('maintainer','approve',decisions[0].sha256)
            or a['previous_sha256'] != plan.sha256 or b['previous_sha256'] != decisions[0].sha256):
        fail('review_chain')
    if not historical:
        for decision in decisions: verify_authority(authority,decision,root=root)


def require_m5_compatible(root, store, db, candidate):
    """M5 cannot resurrect retired definitions or use pre-rename receipts/edges."""
    plans,_,touched=_ledger(store,db)
    _require_no_pending_moves(store,db)
    affected=set(candidate.graph.index().outputs)
    dependencies=set(candidate.graph.index().nodes)
    for plan in plans:
        p=plan.to_dict()
        if affected & set(p['members']): fail('m6_mapping_requires_current_adapter')
        for field in ('before','after'):
            for e in p[field].values():
                if e['names']['source'] and 'asset:'+e['names']['source']['path'] in dependencies:
                    fail('m6_dependency_requires_current_adapter')


def commit_operational(*args, **kwargs):
    require_operational_approval(*args, **kwargs)


def _require_no_pending_moves(store,db,operation_id=None):
    from .mapping_moves import _rows
    rows=_rows(store,db)
    committed={r[0] for r in db.execute('SELECT subject FROM events WHERE kind=?',(COMMIT,))}
    latest=_replay(store,db)[2]
    cancelled={i for i,(r,e) in latest.items() if r.to_dict()['state']=='cancelled'}
    if set(rows)-committed-cancelled-({operation_id} if operation_id else set()):
        fail('pending_move_recovery_required')


def _sources(plan,authority):
    if plan.to_dict()['operation']=='RENAME':
        for e in plan.to_dict()['after'].values():
            src=e['names']['source']
            if src is not None and sha256(confined(authority.trial.config.asset_dir,src['path'],must_exist=True)) != src['sha256']:
                fail('source_hash')


def commit_synthetic(registry, plan, *, authority, decisions, cancel=None):
    """Two records, one M1/Package E transaction; no operational success path."""
    if type(registry) is not IdentityRegistry or type(plan) is not MappingPlan: fail('typed_inputs')
    if type(authority) is not SyntheticReviewAuthority: require_operational_approval()
    root=registry.operations.root
    if authority.trial._closed or root != authority.trial.config.cache_dir: fail('foreign_authority')
    _cancelled(cancel); _decisions(plan,decisions,authority=authority,root=root)
    writer=SidecarStore(root); p=plan.to_dict()
    try:
        from . import mapping_moves
        # This journal commits before filesystem changes; old public/archived
        # bytes are never moved. Staged files are copies in the owned state.
        with writer.read_connection() as db:
            _,existing,_=_ledger(writer,db)
        if p['operation_id'] not in existing:
            _sources(plan,authority)
            mapping_moves.stage(writer,plan)
        with writer.transaction() as db:
            _require_no_pending_moves(writer,db,p['operation_id'])
            _,commits,_=_ledger(writer,db)
            if p['operation_id'] in commits:
                if commits[p['operation_id']]['plan_sha256'] != plan.sha256: fail('retry_substitution')
                mapping_moves.inspect(writer,db,commits)
                return dict(**FLAGS,isolated_committed=True,retry=True,**commits[p['operation_id']])
            current=prepare(registry,operation_id=p['operation_id'],operation=p['operation'],definitions=p['definitions'] if p['operation']=='RENAME' else None,
                members=p['members'],definition_keys=p['definition_keys'],compensates=p['compensates'])
            if current.encoded != plan.encoded: raise Conflict('Mapping plan changed before commit')
            # Same source bytes, verified against archived provenance. Moving a
            # source is explicit staging in the owned trial, never production IO.
            _sources(plan,authority)
            records,events,latest,heads=_replay(writer,db)
            prior=latest.get(p['operation_id'])
            if prior is None or prior[0].to_dict()['revision']!=1 or prior[0].to_dict()['request_sha256']!=plan.sha256:
                fail('exact_proposal_required')
            intent,event=prior; v=intent.to_dict()
            changes={key(c['key']):c['after'] for c in event.to_dict()['changes']}
            v['reads']=[dict(r,**{f:changes.get(key(r),r)[f] for f in ('revision','sha256')}) for r in v['reads']]
            refs=[dict(kind='evidence',id=REFERENCE,subject=s['id'],sha256=plan.sha256) for s in v['subjects']]
            refs += [dict(kind='evidence',id=n,subject=v['subjects'][0]['id'],sha256=d.sha256) for n,d in zip(
                ('synthetic.mapping.confirm','synthetic.mapping.approve'),decisions)]
            v.update(revision=2,content_revision=2,previous_sha256=intent.sha256,previous_event_sha256=event.sha256,
                references=sorted(v['references']+refs,key=lambda r:(r['kind'],r['id'],r['subject'])))
            marker=Operation.from_dict(v)
            snapshot=_registry_successor(registry,plan)
            for d in decisions: writer.put_object(d.encoded,expected_sha256=d.sha256)
            writer.put_object(snapshot.encoded,expected_sha256=snapshot.sha256)
            for t in p['tombstones'].values(): writer.put_object(canonical(t),expected_sha256=fingerprint(t))
            _cancelled(cancel); _decisions(plan,decisions,authority=authority,root=root)
            mapping_moves.execute(writer,db,plan)
            committed=_append_m1(writer,db,marker,records,events,latest,heads)
            _checkpoint('mapping_marker')
            records,events,latest,heads=_replay(writer,db)
            previous=latest[registry.operation_id]; rv=previous[0].to_dict()
            rv.update(revision=rv['revision']+1,content_revision=rv['content_revision']+1,
                previous_sha256=previous[0].sha256,previous_event_sha256=previous[1].sha256,request_sha256=snapshot.sha256,
                subjects=[dict(id=registry.subject,before_sha256=p['registry_sha256'],proposed_sha256=snapshot.sha256)],
                references=[dict(kind='evidence',id='synthetic.registry.snapshot',subject=registry.subject,sha256=snapshot.sha256)])
            for r in rv['reads']:
                h=heads[key(r)];r.update(revision=h['revision'],sha256=h['sha256'])
            _append_m1(writer,db,Operation.from_dict(rv),records,events,latest,heads)
            _checkpoint('registry_marker')
            result=dict(plan_sha256=plan.sha256,record_sha256=marker.sha256,event_sha256=committed.sha256,registry_sha256=p['registry_sha256'])
            writer.event(db,COMMIT,p['operation_id'],result)
            _checkpoint('commit_event')
            _,verified,_=_ledger(writer,db);mapping_moves.inspect(writer,db,verified)
            _cancelled(cancel);_decisions(plan,decisions,authority=authority,root=root);_sources(plan,authority)
        return dict(**FLAGS,isolated_committed=True,retry=False,**result)
    except sqlite3.OperationalError as error:
        if 'locked' in str(error).lower() or 'busy' in str(error).lower(): raise Conflict('Mapping writer busy') from None
        raise
    except Exception:
        recover_local(registry,operation_id=p['operation_id'])
        raise


def recover_local(registry, *, operation_id=None):
    """Explicit local-only recovery; no reapproval, retry or history rewriting."""
    from . import mapping_moves
    writer=SidecarStore(registry.operations.root)
    with writer.transaction() as db:
        _,commits,_=_ledger(writer,db)
        result=mapping_moves.recover(writer,db,commits,operation_id=operation_id)
        for operation,state in result.items():
            writer.event(db,'phase4_mapping_move_recovered',operation,dict(state=state))
    return result


def cancel_synthetic(registry, plan, *, expected_record_sha256, authority, withdrawal):
    """Withdraw an uncommitted owned proposal with immutable evidence and CAS."""
    if type(registry) is not IdentityRegistry or type(plan) is not MappingPlan: fail('typed_inputs')
    if type(withdrawal) is not ReviewDecision: fail('withdrawal_record')
    w=withdrawal.to_dict();p=plan.to_dict();root=registry.operations.root
    if (w['role'],w['action'],w['context_sha256'],w['bundle_sha256'],w['review_id']) != (
            'submitter','withdraw',plan.sha256,plan.sha256,'synthetic.review.m6-'+fingerprint(p['operation_id'])):
        fail('withdrawal_context')
    verify_authority(authority,withdrawal,root=root)
    with registry.operations.contracts.read_connection() as db:
        _,commits,_=_ledger(registry.operations.contracts,db)
        prior=_replay(registry.operations.contracts,db)[2].get(p['operation_id'])
        if p['operation_id'] in commits: fail('committed_operation_requires_compensation')
        if prior is None or prior[0].sha256!=expected_record_sha256 or prior[0].to_dict()['request_sha256']!=plan.sha256:
            raise Conflict('Exact pending proposal required')
    recover_local(registry,operation_id=p['operation_id'])
    writer=SidecarStore(root)
    with writer.transaction() as db:
        _,commits,_=_ledger(writer,db)
        if p['operation_id'] in commits: fail('committed_operation_requires_compensation')
        records,events,latest,heads=_replay(writer,db)
        prior=latest.get(p['operation_id'])
        if prior is None or prior[0].sha256!=expected_record_sha256 or prior[0].to_dict()['request_sha256']!=plan.sha256:
            raise Conflict('Exact pending proposal required')
        v=prior[0].to_dict()
        if v['state']=='cancelled': return prior[0]
        changed={key(c['key']):c['after'] for c in prior[1].to_dict()['changes']}
        v['reads']=[dict(r,**{f:changed.get(key(r),r)[f] for f in ('revision','sha256')}) for r in v['reads']]
        v.update(revision=v['revision']+1,content_revision=v['content_revision']+1,
            previous_sha256=prior[0].sha256,previous_event_sha256=prior[1].sha256)
        v['references']=sorted(v['references']+[dict(kind='evidence',id='synthetic.mapping.withdraw',
            subject=v['subjects'][0]['id'],sha256=withdrawal.sha256)],key=lambda r:(r['kind'],r['id'],r['subject']))
        writer.put_object(withdrawal.encoded,expected_sha256=withdrawal.sha256)
        verify_authority(authority,withdrawal,root=root)
        evidence=Operation.from_dict(v);event=_append_m1(writer,db,evidence,records,events,latest,heads)
        records,events,latest,heads=_replay(writer,db)
        changed={key(c['key']):c['after'] for c in event.to_dict()['changes']}
        v.update(revision=v['revision']+1,previous_sha256=evidence.sha256,previous_event_sha256=event.sha256,
            state='cancelled',reason='explicit synthetic submitter withdrawal')
        v['reads']=[dict(r,**{f:changed.get(key(r),r)[f] for f in ('revision','sha256')}) for r in v['reads']]
        result=Operation.from_dict(v);_append_m1(writer,db,result,records,events,latest,heads)
        verify_authority(authority,withdrawal,root=root)
    return result


def recover(registry):
    """Integrity-only state projection, never automatic retries or remote work."""
    with registry.operations.contracts.read_connection() as db:
        state,graph,definitions,keys,retained,plans,commits,entries=_state(registry,registry.operations.contracts,db)
        from .mapping_moves import inspect as inspect_moves
        local_moves=inspect_moves(registry.operations.contracts,db,commits)
    return dict(**FLAGS,kind='isolated-mapping-recovery',commits=commits,
        currentness='integrity-only-currentness-unknown',
        active_members=sorted(graph.index().outputs) if graph else [],definition_keys=keys,
        tombstones={i:e['tombstone_sha256'] for i,e in entries.items() if e['tombstone_sha256'] is not None},
        retained=retained,plans=[p.sha256 for p in plans],local_moves=local_moves)
