# Phase 2 / M4 — logo validation and two-stage review foundations

M4 starts from `main` at `22ab7c2eb73ca4199ec1f4b68be4290470f47663`, the
confirmed merge of M3 PR #17. Work is isolated on
`feat/lifecycle-m4-logo-approval`, targeting `main` in one draft PR. M1–M3 are
COMPLETE; M4 and Phase 2 remain IN PROGRESS pending maintainer review. M5–M7 and
Phases 3–6 remain NOT STARTED. No production activation or merge is authorized.

## Delivered implementation and boundaries

| Area | Verified implementation / limit |
| --- | --- |
| New PNG validation | Real signature, complete bounded chunk/CRC stream, integrity/decode, modes/alpha, visible content, size/resource guards and alpha/edge/matte/soft-edge measurements. Corrupt/disguised/truncated/empty/oversized data fails before review; alpha alone is not proof of transparency. No background removal or format repair. |
| Historical assets | The exact 17 normal accepted assets, across 41 M2 uses, bypass new-source diagnostics through a hash-pinned exact-use lookup. Replacement bytes/new uses do not inherit acceptance. No cleanup, warning, image decoding or regeneration is imposed. |
| White-wash | Narrow adapter extracts only the three approved inline renderer statements after checking the existing M3 source pin. Original PNG remains immutable; original alpha is retained exactly. No production renderer change or independent replacement algorithm. |
| Category requirements | Explicit M1-approved selection or controlled M4 fixture only. D09 defaults checked where confirmed; other category contracts are not invented. Both presentations are tracked for selected paired designs; a single master can derive white. |
| Preview evidence | Exact source/default/requested/member hashes and distinctly typed owned isolated-preview receipts. Recheck current sources and deterministically reproduce small tasks before trusting evidence. Even fully resealed fake previews fail. |
| Poster previews | Logo-only, explicitly incomplete for final poster/layout/caption/fit approval. A proposed background is context, not an approved assignment or rendered poster background. Final poster-addition approval stays blocked until faithful composition evidence is supported. |
| Overlay previews | Existing unmodified source-preserving overlay transform, selected branch and both standard/bigger boxes. Color/white source branches remain independent; no poster wash or invented group. This is isolated composition evidence, not M5 production-job validation. |
| Comparison | Translation/uniform scale only on analysis copies; alpha/overlap/boundary/components/cutouts/proportions/context retained. No automatic MATCH. Exact same-canvas native binary part/cutout addition/deletion may flag MISMATCH; other uncertainty remains REVIEW REQUIRED. |
| Exceptions | M1 request types plus exact-bound supplemental context represent SOURCE_PRESERVING, intentional background and different brand lockup. Justification, default/requested views and complete membership required. No arbitrary wash toggle or category-default mutation. |
| Two-stage decisions | Exact submitter confirmation followed by distinct allowlisted, externally attributed maintainer approval/rejection. No silence-as-consent, self-review, skipped confirmation, JSON-derived trust or cross-source/category replay. Rejection/withdrawal are explicit states. |
| Persistence | M1 isolated ContractStore, existing Package E transactions/events, immutable blob/revision sidecars, CAS, exact idempotent retries and restart-time revalidation with external attribution. Interrupted writes leave no approved pointer; corruption is not silently repaired. |
| Later authority | Source validity, preview completeness, human logo/design decisions, contract compatibility, artifact review, publication staging and merge are separate. Every M4 result has publication/merge authority false. |

The [module guide](../bulk/contracts/logos/README.md) documents interfaces,
resource budgets, trust boundaries, preview guarantees and reproduction commands.
M1–M3 foundations/schemas are unchanged; the new M4 evidence schema is additive.
M1 request/preview/confirmation/maintainer-decision types are reused. No competing
approval system or rewrite of Package E worker/visual receipts is introduced.

## Sealed synthetic calibration evidence

| Artifact | Identity |
| --- | --- |
| [60-pair corpus](../bulk/contracts/logos/corpus-v1.json) | SHA-256 `3d62c3fdc83f41f21d00132cedaf9b7c9d50476300807e3158c13f829576859d` |
| [Raw evaluation](../bulk/contracts/logos/calibration-v1.json) | Construction-labeled synthetic controls; no real-brand or policy approval |
| [Grid sensitivity](../bulk/contracts/logos/stability-v1.json) | 12 resolution/AA pairs measured at 64 and 128; zero verdict changes |
| [Overlay fixture](../bulk/contracts/logos/overlay-fixture-v1.json) | SHA-256 `cf81756217fe7006def273f74358a9790ec3d041373379233edb4eb931967e6f`; fixture only |
| Existing M3 Playlist contract | SHA-256 `5047d834ecd3f8e5a0ed76ae24760b6947ae6b83e95198ce602e1715e445016b`; still awaiting separate exact-package approval |

Six source families are split 3/3 between calibration and held-out evaluation;
no family crosses partitions. The controls cover exact equivalence, resolution,
soft alpha, padding, missing letters, altered symbols, proportions, missing
cutouts, clipping and intentionally different lockups. Labels are documented
construction ground truth, not fabricated human decisions.

Each split has 30 pairs: 12 positive and 18 negative/lockup cases. Results:
**9 hard structural flags, 9 negative manual reviews, 12 positive manual reviews,
0 false matches and 0 false mismatches**. Automatic MATCH coverage is **0%**;
100% of positives and 50% of negatives still need review. This conservative
abstention is intentional and does not establish a production classifier.
Resolution/AA/grid changes alone cannot silently become a structural verdict.

The 64/128 grids and alpha probes are recorded measurement settings, not invented
universal tolerances. Real maintainer-labeled families, measured stability and
resource evidence, a sealed candidate policy and untouched held-out evaluation
must precede explicit exact-policy approval and any future automatic MATCH.
Numeric automation remains disabled. No accepted historical artwork is used as
a cleanup or regeneration corpus.

## Review artifacts and reproduction

```sh
python -m create_defaults.bulk.contracts.logos --evidence-root config/lifecycle-m4-evidence
python -m pytest create_defaults/bulk/tests/test_logo_workflow.py -q -p no:cacheprovider
```

The CLI checks M1 state-root isolation, generates private synthetic galleries,
source/derived PNG evidence, pending fixture review records and JSON reports.
It records no actual human confirmation or approval. It offers no operational
contract-approval, publication, merge or public-service commands. After material
implementation changes use a fresh evidence root; immutable old reviews are
retained rather than rewritten as current approval.

The local handoff links the fresh gallery/report. Both full overlay examples and
logo-only poster examples are labeled accurately. Original source, derived
default white and supplied white candidates are separately visible in the
calibration gallery, including all structural negative controls.

## Validation and remaining dependencies

Tests explicitly cover signatures/modes/alpha/CRC/decode/resource limits, mattes,
edge/halo diagnostics, exact wash/alpha/source preservation, comparison negatives
and resolution controls, complete pairs/sizes/branches, missing receipts,
source/derived/context/runtime/contract mutation, fully resealed fake previews,
forged attribution/self-review/replay, skipped/rejected/withdrawn confirmations,
idempotence, blob/transaction interruption, corruption/restart, new material
revisions and unrelated-review preservation. M1/M2/M3 regression suites remain
part of existing Windows/Linux CI. Final-head counts/results are recorded in the
draft PR rather than claimed from an earlier commit.

Limitations stay blocked, not represented as completed functionality:

* Full poster composition/fit and production expanded-definition/dependency
  integration remain M5/M6. Logo-only evidence cannot approve a complete poster
  addition. General lifecycle operations and translation safeguards are absent.
* M3 Playlist has no separate actual exact-package approval. A merged M3 PR
  supplies no such approval; M4 recognizes it only as an isolated fixture.
* Real decision attribution must come from the controlled operator, as in M1.
  No new authenticated web application/login service is implemented. An actual
  authenticated capture adapter is required before operational deployment.
* Comparison labels/measurements are synthetic; uncertain correspondence and
  source quality remain human review. No numeric MATCH policy is approved.
* Isolated preview receipts are distinctly typed and replay-verified; they are
  not production worker receipts or accepted publication artifacts. Production
  worker wiring and later publication gates remain separate.

No original logo/font/artwork/definition, production Python/renderer, translation,
workflow/publication destination, old receipt or Default-Images file changes.
No historical library generation, production activation, upload or merge occurs.
M4 remains IN PROGRESS for maintainer review; stop before M5.

## Complete changed-file list

* `create_defaults/bulk/contracts/logos/__init__.py`
* `create_defaults/bulk/contracts/logos/__main__.py`
* `create_defaults/bulk/contracts/logos/assets.py`
* `create_defaults/bulk/contracts/logos/wash.py`
* `create_defaults/bulk/contracts/logos/comparison.py`
* `create_defaults/bulk/contracts/logos/evidence.py`
* `create_defaults/bulk/contracts/logos/workflow.py`
* `create_defaults/bulk/contracts/logos/storage.py`
* `create_defaults/bulk/contracts/logos/historical.py`
* `create_defaults/bulk/contracts/logos/calibration.py`
* `create_defaults/bulk/contracts/logos/corpus-v1.json`
* `create_defaults/bulk/contracts/logos/calibration-v1.json`
* `create_defaults/bulk/contracts/logos/stability-v1.json`
* `create_defaults/bulk/contracts/logos/overlay-fixture-v1.json`
* `create_defaults/bulk/contracts/logos/README.md`
* `create_defaults/bulk/contracts/schemas/logo-evidence-v1.schema.json`
* `create_defaults/bulk/tests/test_logo_workflow.py`
* `create_defaults/lifecycle/PHASE2_M4_IMPLEMENTATION.md`
* `create_defaults/lifecycle/ROADMAP.md`
