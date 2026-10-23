# Phase 4 / M1: isolated operation records

This is a synthetic, record-only foundation. It stores proposed ADD, UPDATE,
RENAME and DELETE requests, not executable changes. There is no production hook,
CLI, identity allocator, image processor, approval provider or publication path.
See the [M1 dossier](../../lifecycle/PHASE4_M1_IMPLEMENTATION.md).

## Closed protocol

[`operations-v1.schema.json`](schemas/operations-v1.schema.json) is JSON Schema
2020-12, `schema_version: 1`, `protocol_version: "1.0.0"`. All objects have closed
fields and bounded values. The existing M1 and Phase 3 schemas are unchanged.
[`models.py`](models.py) uses the original strict JSON decoder, strict validator,
canonical serialization, fingerprinting and immutable `Document` primitive.
Duplicate JSON keys, booleans masquerading as integers, malformed hashes, unknown
fields, unsupported versions, unsafe paths and inconsistent references fail.
Serialization preserves exact strings; it never normalizes a filename in place.
Proposed namespace paths must already be NFC and portable relative POSIX paths.
Collision keys use existing NFC/casefold rules independently of the stored path.

Public immutable values are `HeadKey`, `HeadRef`, `Operation` and `Event`.
`from_dict`, `from_bytes`, `encoded`, `sha256` and `to_dict` follow existing
`Document` conventions. `Operation.read_set` and `write_set` return typed tuples.
All IDs are explicitly `synthetic.*`; operation IDs are `synthetic.operation.*`.
Actual historical IDs cannot enter this prototype. This restriction is not a
replacement identity scheme for M2.

| Operation field | Meaning |
| --- | --- |
| `id`, `operation`, `subjects[].id` | Immutable request identity, type and sorted subject set across revisions |
| `subjects[].before_sha256`, `proposed_sha256` | Unverified state pointers; ADD has no before, DELETE has no proposed pointer |
| `revision`, `previous_sha256`, `previous_event_sha256` | Exact per-request record and event chain |
| `content_revision`, `request_sha256` | Content revision and exact external request reference |
| `reads` | Sorted typed subject, namespace, evidence and dependency keys with expected revision/hash and subject scope |
| `writes` | Sorted subset of read keys; must include every subject and referenced namespace |
| `namespaces` | Exact namespace/path/subject scopes; each derives a corresponding written coordination key |
| `references` | Sorted typed evidence, dependency, tombstone or journal references, each scoped to a selected subject |
| `state`, `reason` | Informational status; negative statuses require a diagnostic reason |

Every DELETE subject requires exactly one tombstone reference; other operations
cannot carry tombstones. These are retained references, not applied retirement.
References are recorded data, never evidence authentication or a claim that an
external blob, proposed snapshot or dependency was verified. M2 must supply
authoritative snapshot/mapping/dependency closure later.

All records, events and inspections keep `operation_accepted`, `applied`,
`artwork_approved`, `contract_approved`, `ready`, `active`,
`production_enforcement` and `publication_authorized` false. They require
`scope: "isolated-synthetic-records"`, `simulation: true`, `record_only: true`.
No actor/trusted flag is accepted.

## Informational states and revisions

| Current | Permitted successor |
| --- | --- |
| Initial | `draft`, revision 1, content revision 1 |
| `draft` | Changed-content `draft`, `structurally_validated`, `conflicted`, `stale`, `cancelled` |
| `structurally_validated` | Changed-content `draft`, `conflicted`, `stale`, `cancelled` |
| `conflicted`, `stale` | `draft`, `cancelled` |
| `cancelled` | None; history remains immutable |

Each append increments the operation revision. Material changes to before/proposed
references, request, namespaces, references or read/write scope also increment
the content revision and return to `draft`. Updating expected read-head values
alone is not new content; changing the scope is. A same-state/no-content append
is rejected. `structurally_validated` describes a local record transition only;
it does not claim business, artwork, ownership or freshness validation.

## Explicit storage API

```python
from create_defaults.bulk.lifecycle.models import Operation
from create_defaults.bulk.lifecycle.storage import OperationStore

# Caller supplies a dedicated nonproduction root and exact synthetic record.
store = OperationStore.create(isolated_root)
record = Operation.from_bytes(canonical_record_bytes)
event = store.append(
    record,
    expected_revision=record.to_dict()["revision"] - 1,
    expected_sha256=record.to_dict()["previous_sha256"],
    expected_event_sha256=record.to_dict()["previous_event_sha256"],
)
report = OperationStore(isolated_root).inspect(
    expected_journal_sha256=event.sha256,
)
```

`create` is explicit local initialization. Opening, `inspect`, `history` and
`journal` do not initialize/migrate state, create missing archives, repair data
or permit SQL writes. SQLite may manage WAL/SHM bookkeeping in an already owned
archive; these APIs do not change logical database rows, objects or schemas.
The physical operation marker is checked before opening SQLite, including for a
foreign base-only contract archive. Missing/partial/foreign namespaces fail.
Roots and objects reject traversal, symlinks and Windows reparse points and use
the existing production-root exclusion checks. There is no default state root.

## One transaction and journal

[`storage.py`](storage.py) reuses the **same** isolated `ContractStore` database,
immutable canonical objects and Package E event table. Four additive tables
(`p4m1_schema`, `p4m1_records`, `p4m1_journal`, `p4m1_heads`) have UPDATE/DELETE
rejection triggers. No second database or approval store is introduced.

The additive [`SidecarStore`](package_e.py) subclass provides `open_readonly`,
`read_connection`, `put_object`, `transaction` and `event`. Event insertion
requires the same explicitly writable instance's active transaction. New M1
production code never calls `_store`, `_write_blob` or `_blob_path`. Original
ContractStore bytes, contract pin/record APIs and frozen schemas remain unchanged.
The bridge uses public `Store` transaction/event methods on that same database;
its additional Python handle is not a separate persistence framework. Read-only
instances also reject inherited pin/append entry points before any blob writes.

1. Validate the typed canonical request and existing archive without migration.
2. Write its content-addressed object; this may leave an unreferenced orphan.
3. Inside Package E's immediate transaction, replay the archive and compare the
   independent expected operation revision, previous record and previous event.
4. Compare **every** selected read-head revision/hash, including read-only
   evidence/dependency heads. Any stale head rejects the entire transaction even
   if proposed state hashes are unchanged.
5. Append one record index, all selected head versions, the canonical global
   event and its linked Package E event; commit them together. Budgets are checked
   before commit. Heads advance to the **operation record hash**, not the proposed
   state hash. They coordinate requests; no proposed state is applied.

The global event sequence is serialized, but is not a caller-required global CAS
head: disjoint requests prepared together can both succeed. Overlapping subjects,
output groups or casefolded namespace keys conflict. Namespace keys coordinate
competing requests; they do not allocate real names or release reservations.
An exact ID/revision/content retry returns its original event without new head
movement, even after later requests. That event is historical evidence, not a
claim that its original read set remains current. Different bytes for an existing
ID/revision fail. A failed CAS records nothing; a new `stale`/`conflicted` record
requires explicit refreshed heads and a reason. Cancellation retains history and
does not delete data or implicitly release any name.

## Integrity, recovery and limits

Every inspection/restart replays canonical objects, per-operation chains, global
sequence, read sets, complete head history and Package E index links. Missing,
substituted or corrupt indexed evidence fails closed. An interrupted transaction
rolls back all indexes/heads/events; unindexed objects stay non-authoritative.
Restart does not promote, delete or collect orphans. Interrupted initialization
before the final operation marker is deliberately not automatically repaired;
use a separate inspected/new empty root rather than overwriting evidence.

Without an independently trusted checkpoint, inspection reports
`integrity-only-currentness-unknown`: a coherent whole-archive rollback cannot
authenticate its own currentness. An optional exact journal checkpoint detects
rollback; it grants no operational authority. No live checkpoint provider is
invented. Full replay is intentionally bounded: at most 4,096 records/events,
65,536 head versions, 64 MiB cumulative canonical objects and a separate 64 MiB
index budget, plus the existing 8 MiB JSON-object bound. These are prototype
metadata resource limits, not visual thresholds or workload expansion authority.

## Tests and handoff

`python ci/phase4.py run` collects and executes every explicitly maintained ID in
`ci/phase4-test-ids.json`, checks exact-source maintenance provenance and exports
the fixed full archive vector in `create_defaults/phase4/tests/canonical-v1.json`.
The mandatory aggregate requires both OS reports, identical schema/vector hashes,
all setup/call/teardown reports and no skips/xfails. Earlier ID baselines and
resource limits remain separate and mandatory.

M2 needs separate authorization to add persisted actual identities layered over
frozen historical IDs, semantic member/overlay lookup, retained name ownership,
supported prospective adapters, full dependency/read-write closure and planner
integration. Before/proposed pointers in M1 do not implement any of these. M3
composition, M4 approval, M5 ADD/UPDATE, M6 rename/retirement/recovery and M7 final
acceptance remain unimplemented. All 22 real contract approvals are still absent.
