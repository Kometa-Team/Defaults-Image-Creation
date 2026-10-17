# Package E - acceptance verification in progress

Gates A-D were formally approved and Package E authorized from
`166a007c00f14b166a97be8887a4532ea42078b8` on draft PR #12. Production cutover,
merge, ready transition, deployment and artwork/translation writes remain
unauthorized. Earlier acceptance reports, fixtures and Package D sample decisions
are unchanged. This intermediate report is not a Gate E approval.

## Source and platform validation

The final acceptance workloads started from executable source
`6bb5844b4ebe1ea8b681c826105a008a8f673ede`. Its
[Linux CI](https://github.com/Kometa-Team/Defaults-Image-Creation/actions/runs/39058762806)
passed: Phase 1 120, Package A 35, B-E 216 and People 129, totaling 500 passed
and two Windows-only skips. Both baselines, compilation, focused rendering and
whitespace checks passed. Four Pillow deprecation warnings concern the existing
palette `getdata()` call; it remains supported by the pinned version.

The preceding E run at `e0cf670ff9ba4fd2a7587fd83c631551c4e20e9e` passed 492 tests
and two skips but failed its final whitespace check on extra trailing blank lines.
Those lines were corrected; the check was not weakened. Logs and artifacts for
both runs remain under ignored `config/package-e/` evidence roots.

Windows uses Python 3.13.15; Linux uses Python 3.13.16. Final Windows suites,
full-catalog rendering and the language audit are still running. Subsequent test
and report changes do not modify the executable source being exercised.

## Complete reconciliation

The corrected capture remains 9,958 English jobs. All 21 categories reconcile,
with the approved D02 green Splatter duplicate retired: 9,957 active contracts,
9,955 publishable destinations, two private Awards intermediates and zero duplicate
paths. Red `#990000` Splatter and Death in Paradise `(2011)` remain unchanged.
Patched-stack preflight has no blocked English variants: 3,022 ready, 4,285 with
warnings and 2,650 shared. All 9,957 retain historical color provenance. The single
preserved clipping warning is `defaults-en/collectionless.jpg`; warnings are not
silently removed by changing approved appearance.

Read-only Default-Images inventory at commit
`59e49ede8d41ac5991f971e66e93af596402329a` / tree
`e1664efb92db5872db112cf18253910da77355df` found 9,954 exact paths, two private
exclusions and one case conflict: expected `genre/Action & adventure.jpg`, published
`genre/Action & Adventure.jpg`. This needs an explicit future mapping decision.
Selective image comparisons follow full local output verification.

The fresh authoritative translation snapshot still discovers all 14 resources at
`a7bddf45d0fb2cc37c794af05d5fb807880c9a80`; registry SHA-256
`4f3e741b5d252addfbb4c1a4ed3c7eadf231b5aa3636afa9d2b833816c05ed1b`.
The original-stack fresh audit completed all 139,398 contracts; final patched-stack
audit and consistency checks are running separately. Arabic and unreviewed
translated variants remain pending.

## Narrow fixes and focused evidence

- Warm reuse still hashes inputs/outputs and checks exact finalized SQLite
  receipts and image headers. It avoids redundant full decoding of already
  verified bytes. New atomic promotions still require full decoding; no mtime
  shortcut or receipt rewrite is used. Loaded dependency metadata is cached per
  process; renderer source hashes are rechecked.
- A paired profiled Year warm observation fell from 51.189 to 35.777 seconds with
  identical manifest `c6e06332c32d89e6c68ba81b6cb7aa4b2d7fc7f1d2978eb0b9f11a077feb7e25`,
  451 verified cache checks for 301 unique outputs, zero renders and zero worker
  starts. This is one profiled pair, not a universal isolated speedup claim.
- The first partial English run exposed three spurious retries when workers sent
  success then retired before every ready pipe was drained. The scheduler now
  consumes buffered success before classifying exit/timeout as failure. A
  deterministic regression failed before the fix; all 15 focused worker/recovery
  tests pass after it. Failed-attempt reasons enter the existing immutable log.
- Generated-family selection previously omitted parents of unlisted family
  children. The index loader now includes every member's dependencies. Six focused
  family/bounded-selection cases pass. Benchmarks exclude family selectors and
  enforce a 64-output effective-graph budget.
- The comparison CLI now fails on unexplained rendering differences. A four-item
  synthetic concurrent group decision commits exactly once and records the exact
  two-item inspected subset as a representative group, without inventing individual
  inspection. Both focused cases pass.
- An additional isolated approved-color integration and overlay input-change test
  pass: only the predicted poster or two overlay sizes rerender; unrelated outputs
  and approvals remain valid. All synthetic approvals exist only in pytest roots.

## Dependencies and retained partial runs

Advisory screening found issues in Pillow 12.0.0 and fonttools 4.60.1. The isolated
Pillow 12.3.0 / fonttools 4.60.2 trial rendered 44 Based/Decade/Playlist outputs
covering all 17 font hashes. Fresh calls to the original approved API on the same
inputs and generated-parent bytes matched all 44 exact image hashes. Comparison
ledger identity: `7e392814005b6d4c9ab26aa453787bbeb343b3f6350e494f8db27d0515ac948f`.
The two pins are updated; a fresh query found no matching published advisories for
the patched versions. This is direct-pin screening, not a transitive/native SBOM.

The original-stack full runs were explicitly stopped after 1,378 verified English
jobs and 2,760 overlay jobs. These are partial evidence, not full passes. Final
outputs and receipts remain; only validated token-owned scratch was removed.
Final full acceptance uses fresh roots, patched dependencies and bounded resources.

## Performance and completion status

All 18 poster scaling observations completed: five workloads at 1/2/4 workers,
plus a mixed repeat at every count. Every warm run used zero renders/workers; cold
runs had zero retries/failures. Five matched isolated legacy batches completed all
95 posters. A separate overlay comparison reproduced 36 grouped mogrify operations
on 38 copied inputs: all dimensions match Python, all retain measurable pixel
differences, and no new visual approvals are granted. Renderer time was 9.553 s.
Two workers are the preliminary conservative recommendation; final tables follow.

The final English run, 4,122-overlay verification, patched multilingual audit,
Windows suites, cross-platform comparison, detailed acceptance matrix, independent
readiness recommendations and proposed cutover/rollback checklist remain pending.
No incomplete run is labelled fully successful. Outputs remain local and the PR
remains draft. Stop for final maintainer review after all evidence is assembled.
