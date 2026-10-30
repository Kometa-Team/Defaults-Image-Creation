"""M4 current-mapping UPDATE bridge over the existing isolated M1–M6 journal.

No operational authority, catalog exporter, renderer or second state index. The
new immutable lineage object joins an existing native snapshot to its accepted
M5 artwork and intervening M6 mapping plans. Original M5 callers keep their gate.
"""
from copy import deepcopy
from dataclasses import dataclass, replace
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import tempfile

from ..common import BulkError, Conflict, atomic_bytes, canonical, confined, fingerprint, sha256
from ..config import Config
from ..contracts.expanded.graph import Snapshot
from ..contracts.registry import require_hash
from .candidates import PosterCandidate, poster_candidate
from .identities import IdentityRegistry, RegistryHead
from .operations import Transaction, FLAGS, payload, require_adapter
from .package_e import SidecarStore
from .previews import CompositionArchive, CompositionTrial
from .storage import MAX_EVENTS, MAX_ARCHIVE_BYTES

EVENT = 'phase5_current_mapping_committed'
FIELDS = {'schema_version', 'kind', 'registry_id', 'members', 'entries', 'definitions',
          'accepted_snapshots', 'mapping_plans', 'closure_sha256', 'before_sha256',
          'before_graph_sha256', 'registry_head', 'content_json', 'files', 'assets'}


def fail(code):
    raise BulkError('p5m4_'+code, 'Current mapping UPDATE rejected: '+code)


def _cohort(entries, definitions, members):
    from .basis import historical_basis
    if not members or sorted(set(members)) != members or len(members) > 64:
        fail('membership')
    for identity in members:
        e = entries.get(identity)
        if e is None or e['origin'] != 'assigned' or e['tombstone_sha256'] is not None:
            fail('inactive_or_unassigned_identity')
        if e['category'] != 'Genre' or e['semantic']['language'] != 'en':
            fail('unsupported_cohort')
        if e['semantic']['parent'] is not None or e['semantic']['role'] in {'family','group'}:
            fail('generated_or_dependent_identity')
        rule = historical_basis().rule(e['category'], e['variant'])
        if rule['source_kind'] != 'logo' or rule['required_presentations'] != ['single']:
            fail('unsupported_variant')
        d = definitions.get(identity)
        if (d is None or d['id'] != identity or d['category'] != 'Genre'
                or d['generator'] is not None or d['dependencies'] or d['composer'].get('input') is not None
                or set(d['output']['remote_paths']) != {'en'}):
            fail('unsupported_dependency_or_language')


def _projection(store, db, records, events, snapshots, cutoff=None):
    """Read-only selected journal prefix, using the original M6 plan validators.

    This transient projection is not persisted or trusted independently. Its
    inputs have already passed native snapshot/receipt replay, and M6's ledger
    independently verifies the mapping records and their commit cross-index.
    """
    from . import mappings
    from .evidence import _scope
    plans, _, _ = mappings._ledger(store, db)
    by_operation = {p.to_dict()['operation_id']: p for p in plans}
    graph = None
    definitions, keys, retained, entries, selected, seen = {}, {}, {}, {}, [], set()
    for event in events:
        ev = event.to_dict()
        if cutoff is not None and ev['sequence'] >= cutoff:
            break
        record = records[ev['operation_id'], ev['operation_revision']].to_dict()
        refs = [r for r in record['references'] if r['id'] == 'synthetic.lifecycle.snapshot']
        if refs and ev['operation_id'] not in seen:
            seen.add(ev['operation_id'])
            if refs[0]['sha256'] not in snapshots:
                fail('unverified_prefix_snapshot')
            s = snapshots[refs[0]['sha256']].to_dict()
            proposed = Snapshot.create(payload(s['proposed_graph_json']))
            index = proposed.index()
            if graph is None:
                graph = dict(schema_version=1, kind='m5-dependency-snapshot', basis=proposed.data()['basis'],
                             nodes={}, outputs={}, unresolved=[])
            for i in s['members']:
                graph['nodes'].update(deepcopy(_scope(index, [i])))
                graph['outputs'][i] = deepcopy(index.outputs[i])
                definitions[i] = payload(s['proposed_json'])['effective_definitions'][i]
                entries[i] = s['entries'][i]
                retained[i] = dict(snapshot_sha256=refs[0]['sha256'], artwork=s['artwork'][i])
                keys[i] = i
            mappings._prune(graph)
            Snapshot.create(graph)
        if ev['operation_id'] not in by_operation or not any(
                r['id'] == mappings.REFERENCE for r in record['references']):
            continue
        plan = by_operation[ev['operation_id']]
        p = plan.to_dict()
        if graph is None or p['base_sha256'] != fingerprint(dict(graph=graph, definitions=definitions, keys=keys)):
            fail('mapping_epoch')
        for i in p['members']:
            if entries.get(i) != p['before'][i] or retained.get(i) != p['retained'][i]:
                fail('mapping_lineage')
            if p['operation'] == 'RENAME' and mappings._rename(entries[i], definitions[i], p['definitions'][i]) != p['after'][i]['names']:
                fail('mapping_definition')
            entries[i] = p['after'][i]
            keys[i], definitions[i] = p['definition_keys'][i], p['definitions'][i]
            if p['operation'] == 'DELETE':
                graph['outputs'].pop(i)
                definitions.pop(i); keys.pop(i)
                continue
            row = graph['outputs'][i]
            row.update(local_path=entries[i]['names']['local_path'], public_path=entries[i]['names']['public_path'])
            graph['nodes'][row['node']]['sha256'] = fingerprint(dict(prior=graph['nodes'][row['node']]['sha256'], mapping_plan=plan.sha256))
            row['context_sha256'] = fingerprint(dict(prior=row['context_sha256'], mapping_plan=plan.sha256))
            if 'definition:'+i in graph['nodes']:
                graph['nodes']['definition:'+i]['sha256'] = fingerprint(definitions[i])
            a, b = p['before'][i]['names']['source'], p['after'][i]['names']['source']
            if a and a != b:
                old, new = 'asset:'+a['path'], 'asset:'+b['path']
                if old in graph['nodes']:
                    source = graph['nodes'].pop(old)
                    graph['nodes'][new] = dict(source, identity=b['path'])
                    for node in graph['nodes'].values():
                        node['dependencies'] = sorted(new if d == old else d for d in node['dependencies'])
        mappings._prune(graph)
        Snapshot.create(graph)
        selected.append(plan)
    return (Snapshot.create(graph) if graph is not None else None), definitions, keys, retained, entries, selected


def _scoped(graph, definitions, retained, entries, plans, members):
    from .evidence import _scope
    if graph is None or not set(members) <= graph.index().outputs.keys():
        fail('inactive_or_unavailable_identity')
    _cohort(entries, definitions, members)
    index = graph.index()
    if index.unresolved or any(index.outputs[i]['companions'] for i in members):
        fail('required_closure')
    relevant = [p.sha256 for p in plans if set(p.to_dict()['members']) & set(members)]
    if not relevant:
        fail('renamed_mapping_required')
    return dict(entries={i:entries[i] for i in members}, definitions={i:definitions[i] for i in members},
                accepted_snapshots={i:retained[i]['snapshot_sha256'] for i in members}, mapping_plans=relevant,
                closure_sha256=fingerprint(dict(outputs={i:index.outputs[i] for i in members}, nodes=_scope(index, members))))


def _same_mapping(before, after):
    """An UPDATE may revise same-path source bytes, never names/aliases/identity."""
    from .identities import aliases_for
    a, b = deepcopy(before), deepcopy(after)
    aliases={(r['namespace'],r['value']) for r in a.pop('aliases')}
    observed={(r['namespace'],r['value']) for r in b.pop('aliases')}
    if after['revision'] > before['revision']:
        aliases |= set(aliases_for(before['names']))
    if observed != aliases:
        fail('alias_changed')
    a.pop('revision'); b.pop('revision')
    if a['names']['source'] is None or b['names']['source'] is None:
        fail('source_required')
    a['names']['source'].pop('sha256'); b['names']['source'].pop('sha256')
    if a != b or after['revision'] < before['revision']:
        fail('mapping_changed')


def lineage_events(store, db):
    rows = db.execute('SELECT subject,payload FROM events WHERE kind=? ORDER BY sequence LIMIT ?',
                      (EVENT, MAX_EVENTS+1)).fetchall()
    if len(rows) > MAX_EVENTS or sum(len(r[1]) for r in rows) > MAX_ARCHIVE_BYTES:
        fail('lineage_bound')
    result = {}
    for operation, text in rows:
        value = payload(text)
        if (type(value) is not dict or set(value) != {'snapshot_sha256','lineage_sha256'} or operation in result):
            fail('lineage_index')
        for checksum in value.values():
            require_hash(checksum)
        result[operation] = value
    return result


def _read_bundle(store, value):
    if (type(value) is not dict or set(value) != FIELDS or value['schema_version'] != 1
            or value['kind'] != 'isolated-current-mapping-epoch'):
        fail('lineage_shape')
    members = value['members']
    _cohort(value['entries'], value['definitions'], members)
    if any(set(value[f]) != set(members) for f in ('entries','definitions','accepted_snapshots')):
        fail('lineage_membership')
    for f in ('before_sha256','before_graph_sha256','closure_sha256'):
        require_hash(value[f])
    files, assets, total = [], [], 0
    archive = CompositionArchive(store.root, readonly=True)
    for field, target in (('files',files),('assets',assets)):
        rows = value[field]
        if type(rows) is not dict or not 0 < len(rows) <= 100:
            fail('lineage_bound')
        for name, checksum in sorted(rows.items()):
            require_hash(checksum)
            raw = archive.read_bytes(checksum)
            total += len(raw)
            if total > MAX_ARCHIVE_BYTES:
                fail('lineage_bound')
            target.append((name,raw))
    return tuple(files), tuple(assets)


@lru_cache(maxsize=16)
def _native_replay(root, registry_id, registry_head_json, content_json, files, assets):
    """Replay original strict loader, Planner and category validators, no render.

    Only immutable, freshly read bytes are memoized. Every recovery still checks
    the source objects, accepted prefix, registry history and exact lineage pins.
    """
    registry = IdentityRegistry(Path(root), registry_id)
    head = RegistryHead(**json.loads(registry_head_json))
    with tempfile.TemporaryDirectory(prefix='kometa-m4-native-replay-') as directory:
        base = Path(directory)
        for name, raw in assets:
            target = confined(base/'assets', name); target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(raw)
        paths = []
        profiles = None
        for name, raw in files:
            if Path(name).name != name:
                fail('definition_filename')
            target = base/name; target.write_bytes(raw)
            parsed = __import__('yaml').safe_load(raw)
            if type(parsed) is dict and 'profiles' in parsed:
                if profiles is not None: fail('profiles_membership')
                profiles = target
            else:
                paths.append(target)
        if profiles is None: fail('profiles_required')
        content = payload(content_json)
        candidate = poster_candidate(registry, expected=head, paths=paths, profiles_path=profiles,
            posters=sorted(content), content=content, config=Config(asset_dir=base/'assets',
                cache_dir=Path(root), workspace_dir=base/'workspace', output_dir=base/'output', offline=True))
        return candidate.encoded, candidate.graph.encoded


def _verify_bundle(store, value, *, graph, definitions, retained, entries, plans, snapshot):
    s = snapshot.to_dict()
    if s['operation_type'] != 'UPDATE' or s['members'] != value.get('members'):
        fail('lineage_operation')
    members = s['members']
    scoped = _scoped(graph, definitions, retained, entries, plans, members)
    if any(value.get(k) != v for k,v in scoped.items()):
        fail('stale_mapping_lineage')
    if s['expected_snapshots'] != value['accepted_snapshots'] or s['before_sha256'] != value['before_sha256']:
        fail('receipt_lineage')
    files, assets = _read_bundle(store, value)
    encoded, encoded_graph = _native_replay(str(store.root), value['registry_id'],
        canonical(value['registry_head']).decode(), value['content_json'], files, assets)
    before, before_graph = payload(s['before_json']), payload(s['before_graph_json'])
    if (encoded.decode() != s['before_json'] or encoded_graph.decode() != s['before_graph_json']
            or fingerprint(before_graph) != value['before_graph_sha256']
            or before['effective_definitions'] != value['definitions']):
        fail('native_preimage')
    registry = IdentityRegistry(store.root, value['registry_id'])
    view = next((v for v in registry.history() if v.head.__dict__ == value['registry_head']), None)
    if view is None or any(view.entry(i) != value['entries'][i] for i in members):
        fail('registry_lineage')
    for i in members:
        _same_mapping(entries[i], s['entries'][i])
    _cohort(s['entries'], payload(s['proposed_json'])['effective_definitions'], members)
    # The native before job must read the exact bytes reserved by accepted
    # history, including a source renamed by M6 without changing its bytes.
    jobs = before['manifest']['jobs']
    for i in members:
        source = entries[i]['names']['source']
        job = next((j for j in jobs if j['poster_id']==i), None)
        if job is None or source not in [{k:r[k] for k in ('path','sha256')} for r in job['inputs']]:
            fail('accepted_source_lineage')


def verify_archived_lineage(snapshot, event, *, store, db, snapshots, outputs, records, events, commit_sequence):
    if event is None:
        return False
    if event['snapshot_sha256'] != snapshot.sha256:
        fail('lineage_snapshot')
    value = payload(store.read_object(event['lineage_sha256']).decode())
    graph, definitions, _, retained, entries, plans = _projection(store,db,records,events,snapshots,commit_sequence)
    _verify_bundle(store,value,graph=graph,definitions=definitions,retained=retained,entries=entries,plans=plans,snapshot=snapshot)
    return True


@dataclass(frozen=True)
class CurrentEpoch:
    """Verified immutable preimage, never permission to apply or publish."""
    before: PosterCandidate
    lineage_json: str

    @property
    def sha256(self):
        return fingerprint(payload(self.lineage_json))


def select_current(registry, *, expected, paths, profiles_path, posters, content, trial):
    if type(registry) is not IdentityRegistry or type(trial) is not CompositionTrial:
        fail('typed_inputs')
    registry.require_head(expected)
    from . import mappings
    from .recovery import validate_state_impact
    with registry.operations.contracts.read_connection() as db:
        mappings._require_no_pending_moves(registry.operations.contracts, db)
        state, graph, definitions, keys, retained, _, _, entries = mappings._state(registry,registry.operations.contracts,db)
        plans = mappings._ledger(registry.operations.contracts,db)[0]
    members = sorted(posters)
    scoped = _scoped(graph,definitions,retained,entries,plans,members)
    if any(keys[i] != i for i in members):
        fail('unsupported_catalog_key_adapter')
    before = poster_candidate(registry,expected=expected,paths=paths,profiles_path=profiles_path,
                              posters=members,content=content,config=trial.config)
    require_adapter(before); trial.require(before)
    if before.data()['effective_definitions'] != scoped['definitions']:
        fail('current_definition_required')
    # Snapshot current source/support bytes before allowing any caller to stage
    # new bytes. Both the native before candidate and its archive are immutable.
    archive = CompositionArchive(registry.operations.root)
    files = {p.name:archive.put_bytes(p.read_bytes()) for p in (*before.paths,before.profiles_path)}
    assets = {r['path']:archive.put_bytes(confined(before.config.asset_dir,r['path'],must_exist=True).read_bytes())
              for job in before.data()['manifest']['jobs'] for r in job['inputs']}
    value = dict(schema_version=1,kind='isolated-current-mapping-epoch',registry_id=registry.identity,
        members=members,**scoped,before_sha256=before.sha256,before_graph_sha256=before.graph.sha256,
        registry_head=expected.__dict__,content_json=before.content_json,files=files,assets=assets)
    _read_bundle(registry.operations.contracts,value)
    frozen_assets = Path(tempfile.mkdtemp(prefix='current-before-assets-',dir=trial.root))
    for name,checksum in assets.items():
        target=confined(frozen_assets,name);target.parent.mkdir(parents=True,exist_ok=True)
        atomic_bytes(target,archive.read_bytes(checksum))
    frozen = replace(before,config=replace(before.config,asset_dir=frozen_assets))
    frozen.verify()
    # Current full committed graph is checked at commit; selecting an immutable
    # preimage alone does not reserve the right to change a shared dependency.
    return CurrentEpoch(frozen, canonical(value).decode())


def stage_source(epoch, trial, identity, raw, *, expected_source_sha256):
    """Same-name disposable source staging; retains all archived preimages."""
    from ..asset_cases import exact
    from ..contracts.logos.assets import inspect_png
    from .composition_models import MAX_BINARY
    if type(epoch) is not CurrentEpoch or type(trial) is not CompositionTrial:
        fail('typed_inputs')
    before=epoch.before
    trial.require(replace(before,config=trial.config))
    before.verify()
    if identity not in payload(epoch.lineage_json)['members']:
        fail('source_identity')
    source=before.registry.view().entry(identity)['names']['source']
    target=exact(trial.config.asset_dir,source['path'])
    if source['sha256'] != expected_source_sha256 or sha256(target) != expected_source_sha256:
        fail('source_precondition')
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_BINARY:
        fail('source_bound')
    if inspect_png(raw).report()['default_transparency_blockers']:
        fail('new_exception_forbidden')
    atomic_bytes(target,raw,replace=True)
    return dict(path=source['path'],sha256=hashlib.sha256(raw).hexdigest())


def propose_current(epoch, candidate, *, identity):
    """Reject a stale/foreign preimage before creating a new native intent."""
    if type(epoch) is not CurrentEpoch or type(candidate) is not PosterCandidate:
        fail('typed_inputs')
    before=epoch.before
    if candidate.registry is not before.registry:
        fail('foreign_epoch')
    value=payload(epoch.lineage_json)
    store=before.registry.operations.contracts
    from .recovery import inspect_db
    from . import mappings
    with store.read_connection() as db:
        mappings._require_no_pending_moves(store,db)
        state=inspect_db(store.root,store,db)
        graph,definitions,_,retained,entries,plans=_projection(store,db,state['records'],state['events'],state['snapshots'])
        scoped=_scoped(graph,definitions,retained,entries,plans,value.get('members',[]))
        if any(value.get(k)!=v for k,v in scoped.items()):
            fail('stale_mapping_lineage')
    if sorted(candidate.graph.index().outputs)!=value['members']:
        fail('candidate_membership')
    files,assets=_read_bundle(store,value)
    encoded,encoded_graph=_native_replay(str(store.root),value['registry_id'],
        canonical(value['registry_head']).decode(),value['content_json'],files,assets)
    if (encoded!=before.encoded or encoded_graph!=before.graph.encoded
            or before.sha256!=value['before_sha256'] or before.graph.sha256!=value['before_graph_sha256']):
        fail('native_preimage')
    before.verify();require_adapter(candidate)
    for i in value['members']:
        _same_mapping(entries[i],candidate.registry.view().entry(i))
    from .operations import propose
    return propose(candidate.registry,before=before,candidate=candidate,identity=identity,operation='UPDATE')


@dataclass(frozen=True)
class CurrentTransaction:
    """Concrete synthetic adapter consumed by the unchanged atomic coordinator."""
    transaction: Transaction
    epoch: CurrentEpoch

    @property
    def inputs(self): return self.transaction.inputs
    @property
    def review_id(self): return self.transaction.review_id
    @property
    def review_sha256(self): return self.transaction.review_sha256
    @property
    def expected_snapshots_json(self): return self.transaction.expected_snapshots_json

    def prepare(self):
        if type(self.transaction) is not Transaction or type(self.epoch) is not CurrentEpoch:
            fail('typed_transaction')
        ctx=self.inputs.composition
        if (ctx.before is not self.epoch.before or ctx.registry is not self.epoch.before.registry
                or ctx.candidate.registry is not ctx.registry):
            fail('foreign_epoch')
        snapshot=self.transaction.prepare()
        root=ctx.registry.operations.root
        from .recovery import inspect_db
        with ctx.registry.operations.contracts.read_connection() as db:
            state=inspect_db(root,ctx.registry.operations.contracts,db)
            self.verify_before(snapshot,ctx.registry.operations.contracts,db,state)
        return snapshot

    def require_current(self, store, db, state):
        from . import mappings
        if type(self.transaction) is not Transaction or type(self.epoch) is not CurrentEpoch:
            fail('typed_transaction')
        mappings._require_no_pending_moves(store,db)
        op=self.inputs.composition.impact.to_dict()['operation']['id']
        if op in state['commits']:
            receipt=lineage_events(store,db).get(op)
            if receipt is None or receipt['lineage_sha256'] != self.epoch.sha256:
                fail('retry_lineage')
            return
        graph,definitions,_,retained,entries,plans=_projection(store,db,state['records'],state['events'],state['snapshots'])
        value=payload(self.epoch.lineage_json)
        if any(value.get(k)!=v for k,v in _scoped(graph,definitions,retained,entries,plans,value['members']).items()):
            raise Conflict('Current mapping or accepted artwork changed')
        candidate=self.inputs.composition.candidate
        if sorted(candidate.graph.index().outputs) != value['members']:
            fail('candidate_membership')
        from .evidence import _scope
        old,new=graph.index(),candidate.graph.index()
        changed={n for n in old.nodes.keys() & new.nodes.keys() if old.nodes[n]!=new.nodes[n]}
        impact=old.impact(changed)
        if (not impact['impact_complete'] or
                (set(impact['affected_outputs'])|set(impact['required_companions']))-new.outputs.keys()):
            fail('incomplete_current_consumer_scope')

    def verify_before(self, snapshot, store, db, state):
        self.require_current(store,db,state)
        graph,definitions,_,retained,entries,plans=_projection(store,db,state['records'],state['events'],state['snapshots'])
        _verify_bundle(store,payload(self.epoch.lineage_json),graph=graph,definitions=definitions,
                       retained=retained,entries=entries,plans=plans,snapshot=snapshot)

    def record_lineage(self, snapshot, store, db):
        store.put_object(canonical(payload(self.epoch.lineage_json)),expected_sha256=self.epoch.sha256)
        store.event(db,EVENT,snapshot.to_dict()['operation']['id'],
                    dict(snapshot_sha256=snapshot.sha256,lineage_sha256=self.epoch.sha256))


def commit_operational(*args, **kwargs):
    from .review_authority import require_operational_approval
    require_operational_approval(*args,**kwargs)
