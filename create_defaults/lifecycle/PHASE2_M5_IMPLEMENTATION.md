# Phase 2 / M5 implementation and review evidence

M5 is **IN PROGRESS**, prepared for maintainer review only after its draft PR and
final-head checks pass. Base: M4 merge
`f10e95107501a029b206e87e19723ddf47a7f7ad`. M1–M4 are COMPLETE; M6–M7 and
Phases 3–6 remain NOT STARTED. No production enforcement, historical generation,
publication, lifecycle ADD/UPDATE/RENAME/DELETE or merge is authorized.

## Implementation and precise production boundaries

The new [opt-in API and CLI](../bulk/contracts/expanded/README.md) reuses Package E
instead of parsing or expanding a competing definition model.

| Production path | M5 coverage | Future integration point, currently inactive |
| --- | --- | --- |
| `catalog.load_catalog` → `definitions.load_definitions` | Existing strict loader, explicit shared profiles, nested merge, unknown-field/duplicate/alias rejection; complete catalog membership | Invoke the read-only resolver after actual intake, before accepting any effective definition |
| `Definition.for_language` | Validate final selected language and preserve entire override context; no English fallback/new language added | Bind the language-resolved definition to its contract attestation |
| `Planner.expand`, registered four generator implementations | Actual named/versioned generator callbacks, complete child definitions/origins/families, missing-parent/cycle/orphan checks | Validate every realized child, not just the family declaration |
| `Planner.plan` / `effective_parameters` | Actual renderer defaults, raw and normalized parameters, authoritative captions, approved font bytes, parent artifact identities, output mappings | Contract gate after final planning; raw intent must also comply |
| `validate_manifest` / serialized jobs | Existing strict schemas, seals, topology and namespaces; M5 independently replays the planner and checks every job in the validation selection | Recheck sidecar and actual final job at each trusted boundary |
| Native overlay catalog / `overlays.plan` | M2 verifies all original group/source/branch/size definitions and owned jobs; no poster wash enters overlay context | New operational overlay validation awaits exact M6 contracts and an opt-in gate before direct overlay workers |
| Custom/imported manifests | Unkeyed seals alone provide no authority; final jobs must match actual resolution and implemented contract scope | Reject manifests bypassing the future validator; no production hook installed |
| `workers.tasks_from_manifest`, `RenderTask.spec`, persistent workers | Historical M2 actual owned specifications/receipts preserved; M5 job hashes cover all serialized fields, including review material not in old render fingerprints | Enforce validation at dispatch and after any mutation without rewriting old render fingerprints |
| M4 `LogoArchive.load` | Existing two-stage/owned-evidence verifier and external attribution, complete required members, end-pointer check, dependency-local material binding | Controlled authenticated operator adapter; no inferred attribution or new approval transition |
| Package E artifact review / staging / publication | Kept separate; all M5 reports explicitly deny publication and merge authority | Later separately authorized integration; no publication code imports M5 |

Resolution reads definitions around the existing expansion and detects edits
during the operation. It validates the expanded parent graph before asset
planning. Missing verified parent bytes block prospective plans; M5 neither
fabricates parent receipts nor generates their images. Historical parent proofs
come from accepted M2 owned receipts and original metadata.

## Contract and bypass checks

M1's loader is invoked on every operational contract selection with exact
registry/package/version/variant pins and external maintainer attribution.
Matching JSON actor names, dataclass fields, local presence, approval-shaped
records and recomputed seals never create trust. The exact M3 Playlist contract
still has no actual package approval: all bundled checks are explicitly
non-operational audits unless a genuine operator-supplied decision exists.

M3 supplies the initial real design: all nine unchanged Playlist definitions,
154-point Bebas Neue Regular and its exact font hash, established captured-fit
evidence, white-wash, geometry, background assignments, `TIMELINE ORDER`, exact
filenames/destinations and accepted historical exceptions. Prospective content
uses the closed version-1 allowlist, independent assigned identity and existing
M3 proposed-definition validator. No six outstanding pilot requests are added.

Validation examines both the full effective definition and actual serialized
jobs. It rejects nested/profile/language protected overrides, aliases, duplicate
keys, raw values that normalize/clamp to approved values, generator attacks,
unknown children, category switching, renamed identity approval inheritance,
stale inputs, substituted/missing dependencies, namespace collisions, forged
contracts, replayed or unrelated review records, partial companions and poster
wash leaking into overlays. An old individually accepted departure remains
bound to its exact old item/context; contributor metadata cannot apply it to a
new or changed design.

## Dependencies and impact

The closed v1 graph contains immutable canonical node hashes, explicit direct
edges, literal output namespaces/variants, required companions and per-member
evidence references. `Index.impact` traverses an in-memory reverse index without
filesystem scans or network calls. `compare` checks previous/proposed content,
topology and member mappings. The candidate graph adapter consumes actual
contract-validated Playlist jobs and can patch a complete supplied baseline
without changing the original. A scoped graph explicitly withholds a claim of
complete-library coverage.

Per-row and inherited-leaf projections isolate unrelated YAML rows and unused
profile leaves. Shared sources, fonts, backgrounds, translations, transforms and
generated parents fan out only along captured edges. Every job field contributes
to material context. Source casing and Unicode spelling remain literal, with
global NFC+casefold collision checks. Historical production receipts remain
unchanged. Existing paired logo designs and standard/bigger overlay companions
are retained; an unchanged companion is reported separately from changed pixels.

Generator family specifications/membership conservatively bind all children
under existing Package E provenance. A proposed narrower family impact requires
per-child resolution/comparison; the tool does not invent a minimal set when
that proof is unavailable. Whole English resource provenance remains material;
no new key-only translation compatibility policy is introduced. Unknown graph
changes and unsupported paths report uncertainty and block claims of complete
impact. Reports never trigger regeneration or actual approval invalidation.

M4 evidence is consumed by its existing verifier. A binding includes exact
review/session, source, full effective job, preview members and each member's
transitive material dependency context. A changed definition/background/font or
dependency invalidates affected bindings even with unchanged original PNG
bytes. Shared historical migration decision hashes are reported for the
affected output member rather than globally invalidating every image from
that review population. M4's logo-only previews cannot acquire full poster
approval through a new M5 binding.

## Historical validation, tests and measurements

The fresh audit reuses the accepted M2 registry
`0b0c2af06124379206d43c36a4c12fb456e3861dd335343f4382865a7aab6a05`:
14,079 output records, 14,077 public mappings, 9,957 posters and 4,122 overlays,
4,372 declared definitions and 102 real generator families. All prior source,
font/layout, filename, approved exception and actual owned/production receipt
identities remain preserved. The 17 normal accepted historical alpha assets
receive no new warnings, cleanup or regeneration. All nine Playlist designs
remain compatible.

Automated tests prohibit historical image decoding/rendering, workers,
production state and network calls. They cover both real catalog/generator
metadata and synthetic attacks, final manifest replay, exact authority,
case/Unicode collisions, cycles/missing nodes, raw/effective values, required
companions, M4 staleness, interrupted reads, namespace isolation and immutable
report writes. The complete historical test constructs its expected-output
oracle by independently scanning original verified jobs and parent references;
it does not use graph edges or a second copy of the graph algorithm.

M2 and M5 share one session-scoped, guarded discovery fixture containing only
immutable M1 documents. Before graph reuse, M5 rechecks all 299 source pins,
every declared actual asset/font hash and the freshly expanded definitions.
Both complete historical assertions/oracles still run. This avoids repeating
the same full discovery within the existing Windows CI limit; no assertion,
workflow timeout or production behavior is changed.

Local Windows validation: **72 focused M5 tests passed**. The separate complete
historical audit and oracle passed; the earlier combined M1/M3/M4/M5 regression
run passed **346 tests with four OS-permission skips**. The final PR must also
pass the existing complete Windows/Linux workflow, including M2, frozen jobs,
font tests and Package D/E acceptance smokes. Exact final-head CI results are
recorded in the draft PR.

Fresh historical dependency snapshot SHA-256:
`6e23ff33bd3cba5b1bd69914b974ed9e2118b364e8f04b3a841376c1461f4197`.
It contains **73,041 nodes**, **14,079 outputs**, **32,886,880 canonical bytes**
and zero unresolved dependencies. The local fresh capture took 373.48 seconds;
that operation includes the entire M2 audit and receipt verification, not just
an indexed query. Review artifacts are in the ignored local folder
`config/lifecycle-m5-20261021-v2/` (`graph.json`, `evidence.json`).

| Changed exact dependency | Direct outputs | Total affected | Indexed query |
| --- | --- | --- | --- |
| `logos_playlist/Arrowverse.png` | 3 | 3 | 7.12 ms |
| `fades/@none.png` | 9,957 | 9,957 | 41.63 ms |
| `logos_franchise/Shaft.png` | 3 | 3 | 7.31 ms |

The three Arrowverse consumers are its existing poster and standard/bigger
overlays, not unrelated Playlist artwork. Each result matched the independent
original-job oracle. Query timings include constructing the returned unaffected
output list from the already built in-memory index. Wall-clock timings are
observations, never correctness thresholds or visual-tolerance policies.

## Remaining production gaps and acceptance blockers

1. The exact M3 Playlist package needs real maintainer approval before any
   operational selection. M5 authorization does not supply that decision.
2. M4 Playlist previews remain logo-only. Complete poster composition/fit
   evidence and explicit design approval are still required for a new item.
   M5 does not retroactively extend logo decisions to a caption or background.
3. Remaining category contracts and their operational adapters belong to M6;
   historical facts do not authorize new designs in those categories.
4. Loader/planner, direct overlay, custom manifest, worker dispatch and
   post-validation/publication enforcement hooks remain inactive. The isolated
   API can detect substitution; existing production callers have not been
   modified to invoke it. This is deliberate, not a claim of live enforcement.
5. Controlled authentication/attribution adapters and future sidecar consumers
   require separately authorized integration. A report is integrity evidence,
   never publication permission. Changes after a read require dispatch-time
   source/task verification and exact current sidecar checks.
6. M7 activation/regression gates, Phase 3 translation/destination safeguards,
   Phases 4–6 operations/review/pilot and the six Timeline Order additions remain
   NOT STARTED. No uncalibrated numeric logo tolerance is introduced.

M5 remains IN PROGRESS until the maintainer accepts the final PR. No merge or
M6 work follows automatically.

## Complete changed-file list

- `create_defaults/bulk/contracts/expanded/__init__.py`
- `create_defaults/bulk/contracts/expanded/__main__.py`
- `create_defaults/bulk/contracts/expanded/resolution.py`
- `create_defaults/bulk/contracts/expanded/graph.py`
- `create_defaults/bulk/contracts/expanded/historical.py`
- `create_defaults/bulk/contracts/expanded/validation.py`
- `create_defaults/bulk/contracts/expanded/candidate.py`
- `create_defaults/bulk/contracts/expanded/review.py`
- `create_defaults/bulk/contracts/expanded/README.md`
- `create_defaults/bulk/tests/test_expanded_validation.py`
- `create_defaults/bulk/tests/test_expanded_historical.py`
- `create_defaults/bulk/tests/conftest.py`
- `create_defaults/bulk/tests/test_contract_adoption.py`
- `create_defaults/lifecycle/PHASE2_M5_IMPLEMENTATION.md`
- `create_defaults/lifecycle/ROADMAP.md`

Only ROADMAP.md and the M2 test's fixture handoff modify existing tracked files.
The latter retains all original assertions and shares a guarded immutable
discovery with M5. No production Python,
catalog definition, font/logo/artwork, translation, renderer, workflow,
publication destination, Default-Images repository, old schema or receipt is
changed. No historical images are generated, uploaded or removed.
