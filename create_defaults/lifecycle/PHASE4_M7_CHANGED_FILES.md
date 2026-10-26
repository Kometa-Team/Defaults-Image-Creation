# Complete M7 changed-file inventory

Baseline: `68179d1c568449375ca72b23239b57770dfc229e`.
Exactly 15 intended files: 14 additive files and one existing documentation file.
The final draft PR indexes the exact tested commit and verifies this inventory.

| Path | Purpose |
| --- | --- |
| `.github/workflows/lifecycle-m7-validation.yml` | Additive read-only Windows/Linux M7 groups and acceptance; unchanged 15-minute caps |
| `ci/phase4_m7.py` | Existing exact-ID execution protocol, immutable baseline checks and M7 report/artifact verification |
| `ci/phase4-m7-test-ids.json` | Explicit disjoint M7 executor inventory |
| `create_defaults/phase4/m7_tests/conftest.py` | Existing native M5 ADD/UPDATE fixture and disposable test isolation |
| `create_defaults/phase4/m7_tests/helpers.py` | Thin test calls to original M6 APIs and retained snapshot/false-authority checks |
| `create_defaults/phase4/m7_tests/test_sequence.py` | Actual encoded lifecycle chain, cold read-only replay, exact retries and compensation |
| `create_defaults/phase4/m7_tests/test_recovery.py` | Post-UPDATE marker/move interruption, cancellation and lost acknowledgement controls |
| `create_defaults/phase4/m7_tests/test_boundaries.py` | Post-UPDATE/M6 stale adapter, corruption, graph retirement and authority rejection |
| `create_defaults/phase4/m7_tests/test_ci.py` | Exact evidence/ID/phase/artifact rejection and original-limit/source-preservation controls |
| `create_defaults/lifecycle/PHASE4_ACCEPTANCE_REPORT.md` | Technical acceptance, preserved historical baselines and operational limits |
| `create_defaults/lifecycle/PHASE4_M7_IMPLEMENTATION.md` | Implementation/evidence architecture, measured workload and handoff dossier |
| `create_defaults/lifecycle/PHASE4_M7_COVERAGE.json` | Complete T01–T22 matrix with exact test IDs and expected boundaries/results |
| `create_defaults/lifecycle/PHASE5_PREREQUISITES.md` | Unresolved operational prerequisites; no Phase 5 authorization |
| `create_defaults/lifecycle/PHASE4_M7_CHANGED_FILES.md` | This exact inventory |
| `create_defaults/lifecycle/ROADMAP.md` | Current M6/M7 status and dated decision; earlier logs and six permanent phases retained |

No existing runtime, test body, test inventory, workflow, source-pin manifest,
dependency, production YAML, font, artwork, category/logo policy, historical
exception, receipt or mapping changes. Ignored local logs/scripts/artifacts are
not PR files. Preexisting unrelated worktree changes are preserved and excluded.
