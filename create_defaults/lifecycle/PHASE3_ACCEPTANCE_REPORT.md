# Phase 3 final acceptance report

2026-10-23. **Phase 3 implementation complete; final CI and maintainer acceptance
are recorded separately in the draft PR. Production operational readiness remains
BLOCKED.** M1–M4 are merged; M5 adds full acceptance and a narrow correction in
the isolated M4 validator. Live external authorities, all 22 missing contract
approvals and production integration remain unavailable. Phases 4–6 are NOT STARTED.

## Defect discovered and corrected by acceptance

The fresh read-only M2/M5/M6/M7 audit passes its original artwork, source,
exception, name, dependency, receipt and nonactivation assertions. The added M5
projection also reconciles all 14,079 records and all 278 current English contract
variants. Before correction, the actual standard/bigger overlay pair passed M2
technical checks and complete synthetic M3 destination checks, but M4 raised
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
second. The pre-correction M4 `_graph_scope` required direct hash equality. These hashes
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
hash is replaced. The required existing historical test retains the positive compatibility
assertion that originally failed; it is not skipped, xfailed or made optional.
It now also requires six actual-record negative controls to reject substitutions.

## Explicitly authorized narrow M4 correction

On 2026-10-23 the maintainer explicitly authorized the prepared M4 correction
within draft PR #30, starting at `3741e2d66f6c19a817bb887f4d1cc24a6ec2b5d6`.
The reviewed proposal patch SHA-256 is
`0ae3a6b05a207d11957e51ae3fbca7d6094268f70cde94d53fc4e81dc1ff61dd`.
The only runtime source change is confined to the opt-in M4 evidence
validator, which has no production caller. It changes no renderer, generator,
business policy, contract, frozen schema/receipt, M7 gate or operational flag.

For historical overlays in the exact pinned current M6 release, M4 now always
checks the original record and both context namespaces independently. The M6/M2
context must match the same pinned record's definition/job; the M5 context and
output-node hash must match that record's identity/definition/job/exceptions/
renderer. Every original job input must have its exact asset hash in the selected
closure, and the overlay transform must retain its exact renderer hash. Existing
variant/member/exception/complete-output/authority/request-head gates also remain.
Current released packages cannot bypass this by relabeling the graph with the
member context. Non-current synthetic fixtures preserve their explicit simulation
semantics and never grant real eligibility.

Both hashes were already bound by the unchanged attestation: the M2 subject holds
its review hash, and the M5 material closure holds the graph hash and dependencies.
The fix validates their exact relationship without replacing either or extending
the frozen schema. Poster callers continue to select their explicit M5 review
context; the overlay fix does not invent an implicit poster review mapping.
The actual historical Playlist and captionless Aspect regressions independently
reconstruct both original namespaces, verify their exact record/member/source/
renderer pins, then explicitly select the M5 context for the existing poster API.

Seven new focused controls cover valid distinct namespaces and altered graph,
output-node, source, renderer, definition and record pins. The real historical
pair adds six controls: graph substitution, member-context alias, changed source,
renderer or exception, and withheld companion. Each real poster adds seven
rejections: member-context alias, substituted graph context, definition, source,
renderer, variant and output identity membership. Source and renderer mutations
must invalidate the previous attestation even with a freshly pinned graph.
These cases reuse the original historical fixture and remain mandatory under its
original test ID. All false operational flags and
22 missing exact approvals remain. Full Windows/Linux CI at the final commit is
required; the PR records it separately from the retained pre-fix reproduction.

## Historical reconciliation

Historical invariants required by both final-head platform jobs:

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

All 628 earlier focused IDs remain; 34 new cases give **662 mandatory focused
tests**. The [complete synthetic canonical fixture](../phase3/tests/phase3-final-acceptance-v1.json)
contains actual stage evidence for five complete chains, archival and replay.
The [17-family negative matrix](../phase3/tests/phase3-acceptance-matrix-v1.json)
binds every requested security family to exact mandatory test IDs. Local new
integration tests passed 27/27 and context regression tests passed 7/7. Full focused
and historical final-head results are recorded separately in the draft PR.

The draft PR records final commit, all Windows/Linux check links, per-job counts
and runtimes, original/new full-ID reconciliation and exact unresolved failures.
The complete unchanged bounded workflow is required. Mandatory acceptance must
reject failed historical jobs, as demonstrated by both pre-fix platform runs. Original
15-minute caps, 512 MiB worker-parent test, all original assertions and production
pins remain unchanged; no repository settings are modified.

Machine-readable outputs are retained by existing artifact globs:

| Artifact family | File and purpose |
| --- | --- |
| `phase3-foundations-*` | `phase3-report.json`: fresh complete focused collection/execution and original canonical vectors |
| `phase3-foundations-*` | `phase3-final-acceptance.json`: full five-chain evidence, canonical hash and exact head/platform |
| `validation-*-historical` | `phase3-historical-acceptance.json`: all-category/name/source/exception/dependency projection and production integrity |
| `validation-*-historical` | `phase3-historical-chain.json`: exact actual pair, both context namespaces, preceding-stage results, consumption and six negative controls; pre-fix errors remain in the original run |
| `validation-*-historical` | `phase3-historical-posters.json`: actual captioned Playlist and captionless Aspect records, both independently checked namespaces, exact scoped graphs and seven negative controls per poster |
| Collection / validation artifacts | Exact original IDs and per-phase reports, including the original worker safeguard and retained pre-fix failure evidence |

A successful aggregate `coverage-equivalence.json` is valid only after every
required final-head job passes. The final review checks full raw node identities,
original unittest completion, canonical fixtures, both historical projections,
actual worker-memory test and mandatory acceptance. The pre-fix failure remains
historical evidence; it is never substituted for final green results.

The [draft PR #30 evidence table](https://github.com/Kometa-Team/Defaults-Image-Creation/pull/30)
records the exact final commit and Actions run, all 21 required checks, per-job
execution counts/runtimes and artifact identities. Every report must name that
same commit. The immutable pre-correction reproduction is
[run 39948139950](https://github.com/Kometa-Team/Defaults-Image-Creation/actions/runs/39948139950)
at `3741e2d66f6c19a817bb887f4d1cc24a6ec2b5d6`; its two historical failures and
failed mandatory acceptance are diagnostic evidence, never final acceptance.

## Remaining operational authorities and handoff

Independently of the technical correction, live authoritative source freshness,
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
