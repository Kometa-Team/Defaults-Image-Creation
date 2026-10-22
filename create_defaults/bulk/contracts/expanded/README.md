# M5: isolated effective-definition and dependency validation

This package is opt-in. Production catalog, renderer, workers, translations,
review store and publication entry points do not import it. It creates no
database, executes no lifecycle operation, activates no contract and grants no
publication or merge authority. Historical audits neither decode nor regenerate
artwork. The six requested Timeline Order additions remain reserved for the
final acceptance pilot.

## Interfaces

| Interface | Behavior |
| --- | --- |
| `resolution.resolve()` | Existing strict YAML loader, explicit profile merge, existing registered generators, language-aware `Definition` values, source provenance; stable-read check |
| `resolution.plan()` | Actual Package E `Planner.plan` and `validate_manifest`; no worker; unresolved parent bytes block |
| `validation.Authority` | Re-enters M1's exact registry loader and externally attributed contract decision on every check |
| `validation.validate_existing()` | M3's complete nine-item identity/design/job proof, actual source/font hashes, authoritative English and renderer checks |
| `validation.validate_candidate()` | Replays final Package E jobs and checks every job in the selection against the exact implemented Playlist contract |
| `validation.require_current()` | Detects post-validation definition/job/membership changes; integrity guard, not approval |
| `historical.capture()` | Reuses M2's full fresh discovery and actual owned receipt verification, then builds the complete historical graph |
| `candidate.graph_for_candidate()` | Builds proposed Playlist dependency facts from actual validated jobs; may patch a supplied complete previous graph without mutating it |
| `Snapshot.create/load/index()` | Closed v1 dependency model, canonical bytes, externally pinned bounded reads, global namespaces, missing-node/cycle/orphan/pair checks |
| `Index.impact()` | Indexed reverse traversal; direct/transitive outputs, companion membership, scoped evidence and unaffected outputs; no I/O |
| `graph.compare()` | Compares both topology and material node values, including added/removed nodes and exact output mappings |
| `review.consume/require_current/attach()` | Calls existing M4 verification/attribution, binds all reviewed members to current job/dependency context, attaches reporting references; no approval transition |

## Authority and supported scope

There is still no actual exact-package approval for the bundled M3 Playlist
contract. Its empty review registry cannot select it. An `Authority` must be
supplied by a controlled operator with genuine M1 external attribution. A JSON
reviewer name, `approved` flag, public `Selection` dataclass or freshly calculated
checksum cannot provide it. `fixture_only=True` is a controlled Python test/audit
scope and is always reported as non-operational. The CLI has no JSON-to-trust-map
or automatic fixture-to-operational promotion.

Actual category enforcement is implemented only for the exact M3 Playlist v1
package. Other category contracts remain M6. Existing definitions for all 21
poster categories and Overlays are nevertheless resolved and reconciled as M2
historical facts, preserving all accepted exceptions. Historical compatibility,
authorized category rules, logo review, full poster approval, publication and
merge remain separate assertions.

The contributor allowlist has explicit version 1: `display_name`, `source`,
`content_type`, `background_proposal`, further constrained by M1/M3. These are
content inputs, never a merge into the design. Unknown/protected nested keys,
arbitrary profiles and contributor-authored exception decisions fail closed.
Language overrides, raw values that normalize to the same result, fonts,
caption, fitting evidence, effects, background, source treatment, geometry,
output paths, IDs and membership are checked in the final resolved definition
and actual serialized job. Missing translation and parent-byte evidence block.

## Dependency semantics and limits

Nodes contain exact kind/identity, material hash and direct dependency IDs.
Output rows carry literal mappings/variant, required companions, scoped evidence
and material context. Asset paths retain exact case and Unicode; collision keys
use existing Package E NFC+casefold rules. Historical names are never rewritten.

Inputs include actual PNG/font/shared-background assets, effective definitions,
per-row intent, inherited profile contributions, real generator code and family
membership, caption key/resource traces, background assignments, transformation
runtime identity, Playlist rules and accepted exact historical exceptions.
Generated input edges point to the verified parent output, not a similarly
named asset. Every serialized job field participates in the output context.

A YAML file is a container: its unrelated rows do not share a material hash.
Only the leaves inherited from a profile are dependencies of that row. A shared
source change traverses its actual consumers. Required companions are reported
separately from changed pixels. A shared historical approval record remains
scoped to its affected member; it does not invalidate an entire transport/review
population. Caption resource hashes are currently whole-source material
provenance, as in M2/M3; no unproved key-only compatibility bridge is invented.

Generator family parameters and complete membership are conservatively bound
to every child of that family because Package E provenance binds the complete
family specification. A change there requires resolved per-child comparison
before claiming a smaller impact set. The tool does not authorize any automatic
regeneration from that conservative set. Changes to unknown nodes or unsupported
dependency paths return explicit uncertainty; they never become approval.

Snapshots are integrity-only facts. An external pin selects the exact captured
state; it does not authenticate a person or approve a category. An isolated
scoped candidate graph carries an explicit incomplete-library diagnostic until
a complete baseline is supplied. A manually declared `--changed` node requests
conditional impact, not proof of actual proposed bytes or authorization. For
actual comparisons use complete captured states or `graph_for_candidate` with
the actual resolved manifest and supplied complete baseline.

M4's existing `LogoArchive.load` verifies owned artifacts, exact context and
external submitter/maintainer attribution. M5 makes no decisions for it. An end
pointer check rejects a concurrent session change. Bindings include the entire
material dependency closure of each required member. Changing a caption/font,
background, identity, source, output member or review snapshot stales affected
evidence without staling unrelated outputs. A logo-only M4 preview remains
logo-only; a new M5 binding cannot retroactively approve a poster composition.

## CLI

Run with the pinned Package E environment. Default commands only read files:

```text
python -m create_defaults.bulk.contracts.expanded resolve
python -m create_defaults.bulk.contracts.expanded validate-playlist --fixture-only
python -m create_defaults.bulk.contracts.expanded audit
python -m create_defaults.bulk.contracts.expanded audit --snapshot-out config/m5/graph.json --report config/m5/audit.json
python -m create_defaults.bulk.contracts.expanded inspect config/m5/graph.json --sha256 EXACT_SNAPSHOT_SHA
python -m create_defaults.bulk.contracts.expanded impact config/m5/graph.json --sha256 EXACT_SNAPSHOT_SHA --changed asset:logos_playlist/Arrowverse.png
python -m create_defaults.bulk.contracts.expanded compare config/m5/graph.json config/m5/proposed.json --sha256 OLD_SHA --proposed-sha256 NEW_SHA
```

Only explicit report options write new immutable local JSON files. Existing
different bytes and production source/cache/workspace/output paths are rejected.
Snapshot parsing is bounded to 128 MiB, canonical, duplicate-key rejecting and
hash-pinned. No remote lookups or filesystem enumeration occur during indexed
impact analysis. Individual validation reads its declared assets and the pinned
English resource; full catalog discovery is an explicit capture operation.

See [implementation report](../../../lifecycle/PHASE2_M5_IMPLEMENTATION.md) for
integration gaps, measured results, changed files and review status.
