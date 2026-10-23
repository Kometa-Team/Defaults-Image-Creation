# Bounded Windows/Linux validation

The original reliability repair remains the full legacy validation baseline.
Explicitly authorized P3/M1 adds a separate focused matrix, required by the same
**Validation acceptance** check. It grants no contract approval, activation,
publication or later-milestone authority.

## Required Phase 3 foundation extension

`ci/phase3.py` independently collects and executes the complete maintained
`ci/phase3-test-ids.json` selection from `create_defaults/phase3/tests/` on both
platforms. It reuses the original pytest phase-report validator and requires
every focused ID, no skips/xfails, exact head/schema/selection pins and matching
fixed canonical golden vectors. Both platform reports are downloaded by the
existing aggregate and included in `coverage-equivalence.json`.

`needs: [collection, validation, phase3]` and explicit strict result checks make
this extension mandatory through existing **Validation acceptance**. A missing,
failed, cancelled or skipped focused matrix fails acceptance. There are now 21
required jobs/checks; the legacy 19 and every original test/command remain
required, with their unchanged ID snapshot and deterministic group plan. Each
job retains 15 minutes and independent Windows/Linux reporting. The workflow's
exact M7 pin advances through authorized maintenance; all 190 memberships,
other source pins and protection logic remain intact. No branch-protection
settings are changed; the existing aggregate still needs to be required.

## Measurements before choosing boundaries

`evidence/before.json` records job/step timestamps, full historical audit
summaries and pytest summaries from the actual GitHub logs, with exact-head
job links. The baseline is main `d35b0684a096277dcdbdea70e4683e0c786325bc`,
whose tree matches PR #22's successfully tested final head.

| Original run | OS | Entire job | Bulk pytest | People pytest | Historical capture |
| --- | --- | ---: | ---: | ---: | ---: |
| PR #22 final, 39864198685 | Windows | 756 s | 535.21 s | 120.34 s | 144.70 s |
| PR #22 final, 39864198685 | Linux | 717 s | 605.05 s | 5.20 s | 252.09 s |
| PR #24, 39871173437 | Windows | 914 s, cancelled | unfinished at 88% | not reached | 290.45 s |
| PR #24, 39871173437 | Linux | 560 s | 456.06 s | 4.36 s | 179.35 s |

The timeout is 15 minutes; GitHub's setup/cancellation cleanup can extend the
reported entire-job interval. Cancelled pytest progress is not a passing result.
PR #22's first Windows attempt finished all 1,541 bulk tests in 709.45 s but
timed out during People tests; its second attempt timed out during bulk tests.
There were no assertion failures before these cancellations.

Collection of all 1,671 original pytest IDs took 1.54 s locally. Historical
fixture inspection and collected fixture closures identify exactly three
consumer modules: contract adoption, categories historical, expanded historical.
They share one discovery/context in the original process; M7 reuses M6's
complete audit. Splitting those modules across jobs would repeat the expensive
capture. They therefore remain together in one pytest process on each OS.

The successful Windows capture spent 103.92 s in M2 discovery, 0.25 s checking
source pins, 3.22 s checking physical inputs, 24.55 s expanding definitions and
12.76 s building the M5 graph. Its M7 audit took 0.54 s. PR #24's first Windows
attempt spent 210.06 s in M2 discovery, 0.49 s on source pins, 6.23 s on inputs,
46.81 s on expansion and 21.60 s on the graph. Repeated M7 reconciliation is
not the observed bottleneck. Runner-dependent Windows filesystem/compute
latency affects both capture and People tests. Existing logs alone cannot
separate CPU time from filesystem latency or antivirus activity.

The original fixture release already records real RSS and cycle collection;
the worker test enforces an actual parent RSS below 512 MiB. Neither measure
is mocked, removed or relaxed. The new reports measure collection and every
test's setup, call and teardown separately. Before/after profiling supplements
the original aggregate logs rather than inferring missing per-test timings.

## Boundaries and coverage

`validation-plan.json` explicitly lists every pytest file exactly once:

* historical: the three complete capture consumers, preserving fixture reuse;
* contracts: M1/M3/M4/M5/M7 negative controls and isolated state tests;
* categories: M6 variants and expanded planner validation;
* generation: catalog, workers, resources, remote inputs and basic bulk state;
* review: Package D/E, canaries, staging and review/approval infrastructure;
* people: the original four compatibility modules in a separate process.

Two further mandatory groups preserve the remaining commands:

| Group | Original coverage retained |
| --- | --- |
| core | compileall; all 120 renderer/font/license unittests; all 35 Package A unittests; base-to-head whitespace check |
| smoke | historical literal baseline; frozen 9,958 effective jobs; offline D smoke and original artifacts; bounded E smoke and original artifacts |

Core additionally runs the CI gate's negative-control unittests. There are no
intentional duplicate test executions. Collection is repeated only to prove
coverage and never instantiates historical fixtures. Small immutable contract
release fixtures may load in multiple processes; full 14,079-output historical
capture occurs only in the historical group. Worker tests run without a retained
historical graph, with the original memory budget and subprocess safeguards.

`original-test-ids.json` freezes every original pytest ID and each unittest ID
collected from the baseline, not merely totals. The collection jobs execute
the original two pytest collection selections on both platforms. The final
gate compares those sets to the frozen original IDs and the union of actually
collected **and completed** partition IDs. Each test needs setup, call and
teardown evidence, or a visible documented existing platform skip. Duplicate
IDs/phases, xfails, missing calls, failed/interrupted sessions, stale heads,
changed plans, missing/duplicate artifacts and omitted/failed non-pytest commands
all fail. Unittest execution validates the original per-root IDs before running
the complete suite and requires successful completion of every selected test.
No original test is deleted, renamed, disabled or deselected.

Reports are bound to exact PR head, OS and normalized plan SHA-256. Each job
checks out `pull_request.head.sha`, with full history for existing historical
scope assertions. Pytest setup/call/teardown timings, outcomes and skip reasons
are retained in per-group evidence; stdout retains M6/M7 and real worker metrics.
`coverage-equivalence.json` contains both complete ID lists per OS and empty
missing/extra/duplicate lists only after successful reconciliation.

## Fail-closed acceptance and branch protection

All eight groups and original collection run on **both** operating systems,
with independent matrix results, `fail-fast: false`, and the unchanged
15-minute per-job timeout. No required group has path filtering or a conditional
job predicate. The always-running **Validation acceptance** job requires both
matrix jobs to report success, then requires every individual OS/group report
before comparing coverage. Cancellation, failure, skipped jobs or missing
reports cannot become success. Superseded runs may be cancelled by the existing
PR concurrency policy; they are never accepted as passing.

Maintainers should require **Validation acceptance** in branch protection,
replacing the former two `python-validation` matrix check names. Individual
`Validate (<OS>, <group>)` and `Collect original (<OS>)` checks may also be
required. Settings are not modified by this PR. The separately path-filtered
People Grayscale Sweeper workflow remains unchanged.

## Local reproduction

Use Python 3.13 with `create_defaults/requirements-bulk.txt` installed:

```
python ci/validation.py collect
python ci/validation.py run --group historical --base origin/main
```

Run each other explicitly maintained group similarly. Reports are isolated in
ignored `config/ci-validation`; neither report collection nor these commands
activate production contracts. Exact-head GitHub evidence and the measured
after-runtime table are recorded in the PR acceptance report after the complete
Windows/Linux workflow finishes.
