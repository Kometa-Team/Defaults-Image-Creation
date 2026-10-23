# Phase 3 final acceptance report

2026-10-23. **BLOCKED: M4 rejects valid historical overlay review contexts.**
M1–M4 are implemented and merged, and M5 acceptance/handoff tests are prepared.
Phase 3 cannot be marked COMPLETE while the required historical integration check
fails. Production operational readiness is separately blocked by absent external
authorities, all 22 missing contract approvals and unimplemented production
integration. Phases 4–6 remain NOT STARTED.

## Findings and exact blocker

The fresh read-only M2/M5/M6/M7 audit passes its original artwork, source,
exception, name, dependency, receipt and nonactivation assertions. The added M5
projection also reconciles all 14,079 records and all 278 current English contract
variants. The actual standard/bigger overlay pair then passes M2 technical checks
and complete synthetic M3 destination checks, but M4 raises
`p3m4_graph_review_context` in
[`evidence_consumption/engine.py`](../bulk/contracts/evidence_consumption/engine.py).

Two established contexts have different canonical structures:

| Context | Existing canonical material |
| --- | --- |
| M6 member / M2 OverlayRequest review context | `definition`, `job` |
| M5 historical output review context | `identity`, `definition`, `job`, `exceptions`, `renderer` |

M6's [compiler](../bulk/contracts/categories/compiler.py) captures the first.
The [OverlayRequest adapter](../bulk/contracts/translation_preflight/adapters.py)
preserves it in its immutable subject. The original
[M5 historical graph](../bulk/contracts/expanded/historical.py) captures the
second. M4 `_graph_scope` currently requires direct hash equality. These hashes
are not interchangeable even when every original record and dependency is valid.
The existing small synthetic graph fixtures use the subject context for their
output row, which is why their positive chains do not expose this real boundary.

Measured on the complete unchanged history: **4,122 overlay** and **9,957 poster**
member/graph context pairs have distinct hashes. This is an expected namespace
distinction, not 14,079 unexplained artwork differences. The demonstrated consumer
failure is the actual overlay pair below; its adapter fixes the subject context
to the M6 member namespace. Poster callers also need explicit context selection;
the count alone does not prove every possible poster request fails.

| Actual overlay identity | M6/M2 review SHA-256 | M5 graph review SHA-256 |
| --- | --- | --- |
| `overlay.0012ff20503789d637c329c8` | `eb6e53c5b35c70644d38099fd4834946cd7f2eee58a73348c703d228ad603108` | `32881fa7f5b25ebd2824e3bde1eb235674dee3346ec15a0c7bc9ed530abb03d9` |
| `overlay.f7761907c01388dfa89a9a25` | `84b2488cd93b94c1d833b441fa6b7716f845b77bc0d50c29271df08e7d597c77` | `ba13576c067f8b3258fcceeb0de3c74e76a13fc5c751ed6fa4c905d0e01d5186` |

The pair uses exact actual historical records and nodes from full M6 material
graph `93b01e2261249185bd06982a9cb0823a61628104d327958cedefd97788a39d7d`.
Its small, closed, exact node projection is
`448cfc2d9aebf9eda5eada812c3a3d9683e2ca858ce3a7c47c2d5499507a60fa`.
Only remote inventory/authority observations are synthetic. Neither graph review
hash is replaced. The required existing historical test now retains this failure;
it is not skipped, xfailed or made optional.

## Correction requiring separate runtime authorization

M5 permits acceptance, validation and documentation only. No M1–M4 runtime source
is modified by this PR. A narrow M4 correction should:

1. Verify the exact original overlay record, member/contract/rules/variant pins,
   complete companions and M2 subject against the M6 member context.
2. Independently reconstruct/check the M5 historical context from that same pinned
   record's identity, definition, job, exceptions and renderer, against the current
   graph output and selected dependency closure.
3. Bind both exact context hashes and their relationship in consumption. Preserve
   every original source/exception/member/output/authority/request-head safeguard
   and all false operational flags. Keep original records and graph kinds frozen.
4. Require this real historical pair to pass technically with synthetic authority,
   and add negative controls for either substituted context/record, wrong member,
   changed exceptions, renderer/source/dependency or missing companion.

After authorization and correction, rerun all focused and complete exact-head
Windows/Linux checks. Only a green mandatory acceptance plus maintainer review can
close M5. Green synthetic-only tests cannot substitute for this historical proof.

## Historical reconciliation

Fresh local development audit results (not a prior CI run):

| Invariant | Verified |
| --- | ---: |
| Historical outputs | 14,079 |
| Posters / overlays | 9,957 / 4,122 |
| Public references / private Awards intermediates | 14,077 / 2 |
| Packages / covered variants | 22 / 278 |
| Protected production files / historical source pins | 190 / 299 |
| Actual source inputs | 2,106 |
| Unexplained artwork/source/name/receipt differences | 0 |
| Exact real contract approvals missing | 22 |
| Real READY / ACTIVE / production hooks | 0 / 0 / 0 |
| Artwork regenerated / remote writes | 0 / 0 |

Original accepted exception counts remain unchanged, including 56 historical
source-preserving acceptances, 41 accepted alpha-asset references and 488 Studio
source-preserving references. These count output references, not unique source
assets. All other E01–E15 classifications are retained in the machine report.

Complete ordered projection SHA-256:
`d5ddf0d646de1968a0054acfda7fa199330848d3d57254f6611fca7ed636e476`.
Exact identity/local/public spelling, Unicode and casing projection SHA-256:
`32d3a7492b56f007ece4ff7fb83fd2a1b7758c117d34bb92ceae5c6281301fdc`.
Historical English policy coverage SHA-256:
`c06bd27d0c7a26825678cda3ce14c1b92b8f4140cc1e717ce47d4b77e442abee`.
This is test evidence over current packages, not an approved production policy.

## Integration, security and CI evidence contract

All 628 earlier focused IDs remain; 27 new cases give **655 mandatory focused
tests**. The [complete synthetic canonical fixture](../phase3/tests/phase3-final-acceptance-v1.json)
contains actual stage evidence for five complete chains, archival and replay.
The [17-family negative matrix](../phase3/tests/phase3-acceptance-matrix-v1.json)
binds every requested security family to exact mandatory test IDs. Local new
integration tests pass 27/27; a full focused run is recorded separately. Those
results do not waive the real historical chain failure.

The draft PR records final commit, all Windows/Linux check links, per-job counts
and runtimes, original/new full-ID reconciliation and exact unresolved failures.
The complete unchanged bounded workflow is required even when a known acceptance
failure exists. Mandatory acceptance must reject failed historical jobs. Original
15-minute caps, 512 MiB worker-parent test, all original assertions and production
pins remain unchanged; no repository settings are modified.

Machine-readable outputs are retained by existing artifact globs:

| Artifact family | File and purpose |
| --- | --- |
| `phase3-foundations-*` | `phase3-report.json`: fresh complete focused collection/execution and original canonical vectors |
| `phase3-foundations-*` | `phase3-final-acceptance.json`: full five-chain evidence, canonical hash and exact head/platform |
| `validation-*-historical` | `phase3-historical-acceptance.json`: all-category/name/source/exception/dependency projection and production integrity |
| `validation-*-historical` | `phase3-historical-chain.json`: exact actual pair, both context namespaces, preceding-stage results and M4 error |
| Collection / validation artifacts | Exact original IDs and per-phase reports, including every failed test and original worker safeguard |

Because mandatory acceptance fails on the historical group, a successful aggregate
`coverage-equivalence.json` must not be claimed. Final review must compare the raw
per-platform collections/executions directly, retaining the real failed call and
every documented platform skip. Both platforms must match canonical fixture and
historical projection hashes; matching failures are not operational acceptance.

## Remaining operational authorities and handoff

Even after the technical defect is corrected, live authoritative source freshness,
authenticated repository ownership/grants/permissions/revocation, trusted current
heads and verification-to-consumption atomicity remain unimplemented. Local
archival, content hashes and simulations cannot supply those authorities.
Real non-English coverage requires separately reviewed contracts. All 22 package
approvals, complete new-poster preview/visual decisions, independent operator
activation and production/publication integration remain separate requirements.

See the [M5 dossier](PHASE3_M5_IMPLEMENTATION.md) for changed-file scope and the
[Phase 4 checklist](PHASE4_HANDOFF.md) for future ADD/UPDATE/RENAME/DELETE,
composition, dependency impact and immutable preservation decisions. Phase 4 is
not started or authorized; the six Timeline Order requests remain deferred to
Phase 6. No publication, contract approval/activation or merge occurs.
