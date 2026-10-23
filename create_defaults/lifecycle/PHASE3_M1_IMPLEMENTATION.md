# Phase 3 / M1 implementation and review dossier

2026-10-22. **P3/M1 implemented, pending maintainer review. Phase 3 IN PROGRESS.**
P3/M2–M5 and Phases 4–6 remain NOT STARTED. No merge or later milestone is authorized.

## Authority and prerequisites

The maintainer explicitly approved P3-D01–D04 for implementation and authorized
M1 only. GitHub confirms merged prerequisites: M7 PR #21 at
`0058ac6f109054dd0a25e88f4c707b020460f875`; People repair PR #22 at
`d35b0684a096277dcdbdea70e4683e0c786325bc`; CI PR #25 at
`9022c7c7639f3a2238e5941ec79cc250e4a8ca85`; planning PR #24 at
`78464d2d051dc5da5f305bc4fd9f03868999636f`. The new branch
`feat/lifecycle-phase3-m1-policy-foundations` starts at that latest main.
The merged [proposal](PHASE3_DESIGN_PROPOSAL.md),
[behaviour audit](PHASE3_EXISTING_BEHAVIOUR_AUDIT.md) and
[six-phase roadmap](ROADMAP.md) are the planning baseline.

| Approved decision | Rationale and M1 boundary |
| --- | --- |
| P3-D01: verified commit/content freshness and explicit reverification before readiness | Content integrity and timestamps cannot establish current source selection. M1 binds exact Git/resource/value and explicit verification context, with no arbitrary TTL or live freshness engine. |
| P3-D02: externally authenticated ownership/authorization, fail closed | A name, URL, actor or self-declared grant cannot establish permission. M1 implements typed trusted-caller interfaces, unavailable default and synthetic-only controls; no live provider exists. |
| P3-D03: explicitly authorized English user-owned destinations | Official English-only routing does not require every English item to target official publication. M1 represents that permission without evaluating target eligibility or authorizing publication. |
| P3-D04: separately approved versioned non-English contracts | Finding a translation or using a user repository cannot widen an English-only package. M1 keeps discovery, policy registration and declared contract scope distinct; all current packages remain unchanged. |

## Delivered foundation

The [package documentation](../bulk/contracts/language_policy/README.md) specifies
all six typed documents, versioned closed schema, immutable hash/reference rules,
trusted authority/source contexts, security assumptions and unsupported operations.
No frozen schema, receipt, category package or persistence framework is extended.
The new structural bundle checker performs consistency checks only and grants no
operational outcome. Every attestation is informational with publication,
enforcement, READY and ACTIVE fixed false.

The synthetic suite covers valid round trips and invalid fields/versions/stages,
language/alias ambiguity, repository/pin/path attacks, altered evidence and
membership, forged/unavailable/expired/revoked authority, exact canonical golden
vectors, cold import and canonicalization side effects, protected-source scope,
and missing/cancelled/stale/substituted CI proof. Sources and destinations are
synthetic metadata; these tests call no real repository, permission API or renderer.

## CI integration and maintenance scope

Implementation uses a dedicated matrix in the **existing** bounded workflow,
rather than a separate optional workflow. Both Phase 3 jobs are dependencies of
existing mandatory **Validation acceptance**. It reconciles all old IDs and
commands plus every new focused ID and the same golden hashes on both OSes.
No repository setting change is required to extend the existing aggregate;
maintainers must still require **Validation acceptance** in branch protection.
No settings are changed by this PR.

The workflow is one of 190 protected files. Its hash alone advances from the
merged planning baseline through `maintenance_context.phase3_previous_manifest_sha256`
and `phase3_baseline_commit`; the canonical manifest checksum changes accordingly.
The original guard algorithm, 190 memberships, 189 other source hashes and exact
People repair identity remain unchanged. The existing workflow-boundary test is
updated only to include the additional required job. Existing CI cancellation and
coverage controls are strengthened to include Phase 3, with original test IDs intact.

Full Windows/Linux checks must retain 22 selectors/packages, 278 variants,
14,079 historical outputs / 14,077 public references, 190 protected source checks,
all 299 historical source pins, fonts/translations/artwork, actual resource limits,
zero unexplained differences, 22 missing real approvals and zero READY/ACTIVE.
The original CI's isolated regression/smoke fixtures remain required coverage;
M1 introduces no artwork generation command or production image processing.

## Acceptance evidence and changed-file inventory

The draft PR records its exact final commit, complete changed-file inventory,
focused test counts/golden vectors, all mandatory Windows/Linux job URLs and
conclusions, full ID reconciliation artifact, historical/source/resource results
and any limitations. Evidence belongs to the tested commit; this dossier does
not substitute an earlier passing baseline for final-head results. The focused
runner retains `phase3-report.json`; the aggregate's `coverage-equivalence.json`
includes both full legacy coverage and focused per-OS IDs/vectors. Acceptance
requires the complete workflow, not just the new focused jobs.

Intended inventory: new `language_policy/` code/schema/docs;
`create_defaults/phase3/tests/` synthetic fixtures/tests/goldens;
`ci/phase3.py` and exact focused ID list; existing CI aggregate and tests;
existing workflow plus exact M7 pin metadata/checksum; this report and current
proposal/roadmap status. No production definitions, category packages, old schemas,
assets, fonts, translations, renderer, People code or publication destination changes.

## Remaining work before P3/M2

Review M1 and explicitly authorize M2 before adding required-key enumeration or
translation preflight. Source reverification protocol/trust, authoritative source
advancement and the verification-to-consumption boundary remain future reviewed
implementation details. No live owner/provider, organization/delegation grants,
Weblate API/review attribution, complete destination eligibility, operational
readiness consumer, new non-English contracts, lifecycle operations, activation
or publication is implemented. Synthetic comparisons of explicit times are not a
freshness TTL or evidence of external authentication. All real approvals remain
outstanding. Stop for maintainer review; do not merge or begin P3/M2 automatically.
