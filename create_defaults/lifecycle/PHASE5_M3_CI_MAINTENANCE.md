# Phase 5 M3 exact CI maintenance — separately approved transition

2026-10-29. Before editing existing CI, enumerated the exact planned 14-file
delivery at main `67525e98c79425dfb669f7e9da1141f9b3c3a00e`. Its intersection
with 190 production members, 299 adopted sources and frozen M7 files is empty.
No protected production-source or historical hash successor is required.

The maintainer separately approved the concrete proposal and exact patch in this
session before application. Exactly two existing files change, with SHA-256 over
LF bytes. The roadmap successor includes the separately reviewed closing-summary
correction, approved before application:

| Existing path | Predecessor | Approved successor |
| --- | --- | --- |
| `ci/phase5_m2_maintenance.py` | `c76fca14c13dc4d6e6832ea9ef351c9029a5fd70098e1be15b8e633c469a963a` | `e9e514cf8145c3f43893b9a5dfe14543e8287192862d98940f848183189c7f4b` |
| `create_defaults/lifecycle/ROADMAP.md` | `8d15de091e0ff4a75f131b13ff7bce0063eadda8525e895497d190746c32a8fa` | `f776dea7e1d719439df2fb1f6c8ddea30297eda6bf63f30e9f93cea7f502ca96` |

The helper adds current M3 cohort verification, exact historical-byte projection
and scope delegation. The original M2 manifest stays byte-identical. Before
projecting an approved predecessor, the new helper verifies the actual current
successor and unchanged original bytes from the independently selected main.
Unknown paths, rollback, deletion, rename, symlink/nonregular modes, stale
ancestry, hash/membership changes and mixed unreviewed cohorts fail closed.
The roadmap keeps its original M7 allowed-path route and records M1/M2 completion
and M3 in progress without changing any earlier decision-log entry.

`ci/phase5_m3_maintenance.py` and `ci/phase5-m3-maintenance-v1.json` are the two
new exact trust anchors. The pinned manifest binds the twelve other exact
delivery members, predecessors for the two existing paths, and explicit absence
for ten additions. Final hashes are reviewed together in the draft PR; no
future-milestone wildcard is introduced. Nine new provenance controls verify
the approved bytes, every member's tamper/rollback/deletion, rejected scope/modes,
unchanged old manifests/workflows/IDs/consumers and exact M3 execution/artifacts.

All original six required workflows, M7 BASE/ALLOWED and preservation calls,
M2/People/dependency manifests, original tests and node IDs, historical evidence,
190/299 pins, 512 MiB safeguard and original timeouts remain unchanged. The new
M3 Windows/Linux workflow is additive, read-only, pinned by action commit, and
uses the existing requirements without credentials. It verifies native complete
encoded fixture artifacts as well as exact execution phases and both platforms.

This maintenance is isolated in its own commit and grants no real approval,
operation, production-source mutation, publication, activation, later milestone
or automatic merge. Final mandatory jobs must all pass at the final PR commit.
