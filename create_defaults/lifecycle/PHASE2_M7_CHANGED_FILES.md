# M7 complete changed-file inventory

Base: `c00a0f0b8efcb98857d24da659a30eb06043d6b0`. One dedicated draft branch,
`feat/lifecycle-m7-activation-safeguards`, targets `main`. The PR head and exact
Windows/Linux results are recorded on the draft; this document cannot contain
its own commit hash. All changes are additive isolated support/tests/evidence,
plus the explicitly requested roadmap status update.

| File | Purpose |
| --- | --- |
| `create_defaults/bulk/contracts/activation/__init__.py` | Isolated API exports; no production caller |
| `create_defaults/bulk/contracts/activation/__main__.py` | Read-only inspection/audit/proposal/state CLI and explicit synthetic simulation |
| `create_defaults/bulk/contracts/activation/models.py` | Canonical typed companion/proposal/gate/operator/revision documents |
| `create_defaults/bulk/contracts/activation/controller.py` | Ordered fail-closed state machine, unavailable real authority, fresh reads, revocation/rollback |
| `create_defaults/bulk/contracts/activation/storage.py` | Append-only sidecar in existing Package E transaction/event store; strict read-only inspection |
| `create_defaults/bulk/contracts/activation/simulation.py` | JSON-only synthetic principals/contracts; no real approvals or production activation |
| `create_defaults/bulk/contracts/activation/impact.py` | Existing M5 impact adapter with precise output/category/evidence scope |
| `create_defaults/bulk/contracts/activation/readiness.py` | All 22 exact-package blockers and fresh full-library acceptance dossier |
| `create_defaults/bulk/contracts/activation/protection.py` | Frozen production source/import/nonactivation verification |
| `create_defaults/bulk/contracts/activation/data/production-pins-v1.json` | 190 unchanged production source pins, including the explicit historical People parse exception |
| `create_defaults/bulk/contracts/activation/README.md` | Authority boundary, commands, states, evidence and recovery guide |
| `create_defaults/bulk/contracts/schemas/activation-v1.schema.json` | Additive strict schema; existing M1–M6 schemas unchanged |
| `create_defaults/bulk/tests/test_activation.py` | Synthetic adversarial, impact, transaction/CAS, restart, rollback and nonintegration tests |
| `create_defaults/bulk/tests/test_activation_historical.py` | Full read-only 14,079-record reconciliation and missing-approval inventory |
| `create_defaults/bulk/tests/conftest.py` | Release shared immutable M2 records after the last audit consumer; all discovery/assertions and the existing 512 MiB worker limit remain intact |
| `create_defaults/lifecycle/evidence/phase2-m7-acceptance-v1.json` | Fresh machine-readable historical/approval/nonactivation/handoff dossier |
| `create_defaults/lifecycle/PHASE2_M7_IMPLEMENTATION.md` | Human-readable Phase 2 acceptance dossier and explicit Phases 3–6 handoff |
| `create_defaults/lifecycle/PHASE2_M7_CHANGED_FILES.md` | This inventory |
| `create_defaults/lifecycle/ROADMAP.md` | M1–M6 COMPLETE, M7/Phase 2 IN PROGRESS, Phases 3–6 NOT STARTED; dated authorization entry |

No existing contract package, production definition, artwork, font, translation,
renderer, publication code, dependency declaration, workflow or legacy receipt
changes. No Default-Images write, artwork staging/publication, production
activation, pilot processing, merge or Phase 3–6 implementation occurs.
