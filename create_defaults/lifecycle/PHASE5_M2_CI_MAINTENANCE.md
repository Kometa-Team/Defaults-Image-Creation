# Exact Phase 5 M2 CI scope maintenance — separate review item

2026-10-29. Pre-edit enumeration at main
`8e0bfa22329c33bd9b342760976b23dc205eabc4` found **zero intersections** with the
190 protected production files and 299 adoption-source members. No protected
production transition, historical hash refresh or original inventory change is
needed. All five existing mandatory workflows and their budgets stay byte-identical.

The fixed M7 changed-path guard still requires an explicit exact successor for
the additive M2 delivery. This is a narrowly identified CI maintenance change,
to be reviewed independently of observation semantics. It is isolated in dedicated
commits in the draft PR; implementation acceptance does not imply CI-policy approval.

Only one existing CI source changes: `ci/dependabot_maintenance.py`, the latest
maintenance trust anchor. Three hooks verify the new exact cohort, expose its
exact scope to the existing M7 maintenance chain, and delegate scope validation.
No changes to `ci/phase4_m7.py`, its BASE/ALLOWED/planning set, historical bytes
projection, production pins, source pins, original validation plan/IDs or checks.
No production hash selector is added because no protected member changes.

`ci/phase5-m2-maintenance-v1.json` binds the exact 12 delivery members listed by
`ci.phase5_m2_maintenance.MEMBERS`, with predecessor hashes for the existing helper
and roadmap and explicit absence for ten additions. Its canonical hash is pinned
by the new maintenance helper. Those two files are the reviewed trust anchors.
The complete 14-file inventory is in [the dossier](PHASE5_M2_IMPLEMENTATION.md).
The original Dependabot maintenance manifest stays unchanged. The new helper
checks main ancestry, regular files/no reparse points, exact bytes, predecessors,
complete diff rows and add/modify-only modes. Unknown paths, deletion, rollback,
rename, symlink, hash/membership changes or mixed cohorts fail closed.

Eight new mandatory dependency-provenance controls exercise this transition,
including every member's tamper/rollback/deletion, manifest/baseline resealing,
unknown paths, unsafe diff modes, unchanged original workflows/manifests/IDs and
the new reporter's exact ID/phase/head/no-skip requirements. Original provenance
tests continue unchanged. M7's existing allowed status path for the roadmap keeps
its original scope routing; its exact current bytes remain bound by this cohort.
The new separate M2 Windows/Linux workflow uses pinned
actions, read-only repository permission, no persisted checkout credentials,
controlled fixtures, Python 3.13, exact-head reporting and 15-minute job limits.

Review this exact maintenance commit and its machine-readable predecessors/
successors before merging the M2 PR. It grants no operational authority, future
milestone wildcard, artwork write, publication, contract approval or automatic
merge. Any changed delivery bytes need their own exact successor review.
