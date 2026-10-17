# Package E â€” acceptance verification in progress

Maintainer authorization: all Gates Aâ€“D approved; Package E authorized from
`166a007c00f14b166a97be8887a4532ea42078b8`, existing development branch and draft PR #12.
Production cutover, merge, ready transition, deployment, artwork/translation writes
and automatic visual approval remain unauthorized. Earlier package reports and
fixtures remain immutable. This report will be completed from retained run evidence.

## Reconciliation already completed

The corrected-current capture remains 9,958 English jobs. All 21 category contracts
reconcile, with D02's green Splatter retired: 9,957 active, 9,955 publishable paths,
two private Awards intermediates, zero duplicate destinations, no blocked English
preflight variants. Red Splatter and Death in Paradise (2011) remain unchanged.
Coverage: 3,022 ready, 4,285 with documented warnings, 2,650 shared.
Local evidence: `config/package-e/baseline/`.

Read-only published snapshot: `Kometa-Team/Default-Images@master`, commit
`59e49ede8d41ac5991f971e66e93af596402329a`, tree
`e1664efb92db5872db112cf18253910da77355df`. There are 9,954 exact published-path
matches, two private exclusions and one case conflict. The expected captured path
`genre/Action & adventure.jpg` differs from published `genre/Action & Adventure.jpg`.
Do not silently rename the captured contract. An explicit future mapping/cutover
decision is required. No published artwork was changed.

The refreshed translation snapshot is unchanged: 14 resources at Translations
commit `a7bddf45d0fb2cc37c794af05d5fb807880c9a80`, registry SHA-256
`4f3e741b5d252addfbb4c1a4ed3c7eadf231b5aa3636afa9d2b833816c05ed1b`.
The fresh complete multilingual audit is running separately.

## Measured warm verification and focused fixes

A fresh Year workload completed 301 actual posters, two persistent workers,
326.277 seconds cold, zero failures/retries. Its unchanged warm pass verified
451 cache entries for 301 distinct outputs: 150 parents are checked in both stages.
A paired profiled observation measured 51.189 seconds before and 35.777 after,
with identical canonical manifest `c6e06332c32d89e6c68ba81b6cb7aa4b2d7fc7f1d2978eb0b9f11a077feb7e25`,
identical output bytes and no new renders/workers. This single profiled pair is
not an isolated universal speedup claim; scaling/repeated workloads are separate.

The profile attributed 11.8 seconds to repeated JPEG decoding and 6.8 seconds to
repeated renderer metadata reconstruction. Verified cache reuse still hashes every
output and source, checks header dimensions/mode/format and compares the finalized
SQLite receipt. Full decoding remains mandatory for new/promoted artifacts. No
mtime shortcut, appearance, threshold or receipt rewrite was introduced. Pinned
library metadata is immutable per loaded process; source code hashes are still
rechecked, and dependency upgrades require a fresh process. Cold scheduling avoids
repeatedly hashing a waiting task while all workers are busy, with source checks
before process startup/dispatch, worker entry and promotion. A regression caught
and restored the pre-start check before the full run began.

The existing overlay API now accepts cancellation so finite larger acceptance
runs can stop safely and resume. New focused tests preserve verified outputs on
cancellation and reject corrupt receipts, same-size output corruption, unapproved
fonts, stale reviews and corrupt state. Synthetic review mechanics use temporary
test state and grant no maintainer artwork approval.

## Controlled runs and remaining report sections

The full English production-path generation is running with four workers, a
three-hour limit per cold/warm invocation, 16 GiB output cap, 8 GiB free-disk floor
and 4 GiB sampled process-tree RSS cap. Each worker retains the existing 512 MiB
sampled RSS budget. Limits are sampled safeguards, not OS allocation ceilings.
The full 4,122-overlay run uses two workers and a 30-minute limit. Windows test
suites, source audits and these acceptance runs overlap; their elapsed durations
must not be described as isolated scaling benchmarks.

Pending final evidence: complete output/receipt verification, prior full Phase 1
image-hash comparison and fresh generated-parent references, selective published
images, worker scaling and controlled legacy benchmarks, full language matrix,
Arabic/fitting proposals, final Windows/Linux suites and CI, repository/security
audit, criterion-by-criterion acceptance matrix, separate English/overlay/language
readiness recommendations and proposed unexecuted cutover/rollback checklist.

Package D accepts only its four exact CI images and reviewed French fitting
proposal. No wider artwork/font/layout approval is inferred. Arabic and unreviewed
variants remain pending. Final production-readiness recommendation is not yet made.


## Patched dependency and recycling validation

The direct-pin advisory screen identified published issues in Pillow 12.0.0 and
fonttools 4.60.1. An isolated Pillow 12.3.0 / fonttools 4.60.2 trial rendered 44
Based/Decade/Playlist outputs across all 17 font hashes. Fresh direct calls to the
original approved API on the same inputs and generated parents produced identical
bytes for all 44 outputs (ledger identity
`7e392814005b6d4c9ab26aa453787bbeb343b3f6350e494f8db27d0515ac948f`).
The two project pins are updated. A second advisory query returned no matching
published advisories for those versions; this is not a transitive/native SBOM.
All final acceptance runs must use the patched environment. Earlier partial runs
were explicitly stopped and retained: 1,378 verified English jobs and 2,760
verified overlay jobs. Neither partial run passed full acceptance. Only validated
owner-token scratch was cleaned; final outputs, database receipts and stop records
remain available.

The interrupted English run also exposed three spurious retries at worker
recycling. Workers could send success and exit before the parent drained every
ready pipe. The scheduler now drains all ready responses and checks a final
response before treating process exit or timeout as failure. A deterministic
four-worker retirement regression failed before the fix; the patched worker and
recovery suite now passes all 15 tests. Failed attempts also retain their reason,
attempt and process identity in the existing immutable event stream. Rendering
statements and artwork inputs are unchanged.

Full patched English/overlay runs, benchmark completion, final Windows suites,
Linux CI, final acceptance matrix and production recommendation are still pending.
This intermediate report is deliberately not a Gate E approval.
