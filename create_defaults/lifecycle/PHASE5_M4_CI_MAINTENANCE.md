# Phase 5 M4 exact source/CI maintenance — independently approved prerequisite

2026-10-30. Starting main `120ed09a166ddfdc5380219aad35959c8a0de169` includes
merged M3 PR #56. Before editing existing source/CI, the exact audit and three
unapplied runtime/routing/roadmap patches were presented in
`tmp/phase5-m4/review/MAINTENANCE_PREREQUISITE.md`. The maintainer explicitly
responded **“Approve prerequisite scope and patches.”** This approves only the
documented narrow transition, not production authority or merge.

The exact 22-path delivery intersects **0/190 production**, **0/299 adopted** and
exactly **3/2,927 frozen M7** members. Original source inventories, manifests,
accepted receipts/artwork, thresholds and M7 BASE/ALLOWED remain immutable.

| Existing successor | Approved LF SHA-256 |
| --- | --- |
| `ci/dependabot_maintenance.py` | `b3eaa38e945dcedf39a28578f9ded1fec555c2d909c7aaee4b0712344a8faeb5` |
| `ci/dependency_tests/test_phase5_m3_maintenance.py` | `159aa71d339c00a11d62adc8be9ec713c2d054c333da2c619bfced51aae59c9e` |
| `ci/phase5_m3_maintenance.py` | `e449d0fed2bbcddb84027b81198941dfbf03c6af9fe13d1b18bf3fdb7cb0ce7c` |
| `create_defaults/bulk/lifecycle/apply.py` | `2f43fb9757020d5ba4e576afa0ced6a436dc3e47c8ada7e9d7976795370d6056` |
| `create_defaults/bulk/lifecycle/mappings.py` | `69ad60140dfec8cdecda9d12d3fac5e40a47e5b69444c43e230945d8abb9f6b8` |
| `create_defaults/bulk/lifecycle/recovery.py` | `246574f6974363d4f862e9d5e279db724a443537bcb18202de1f50c94dc7097d` |
| `create_defaults/lifecycle/ROADMAP.md` | `c830b33101d202e6118c84c7d63ccf40b0a7639eefcaa6687d73e2c9469d87fc` |

`ci/phase5-m4-maintenance-v1.json` binds each exact predecessor from the selected
main, each current successor, and explicit absence for new paths. Its fixed member
set and canonical hash are selected by `ci/phase5_m4_maintenance.py`, the other new
trust anchor. Those two anchors plus twenty members are the complete cohort.
All final new-file hashes are reviewable in the draft code PR; no historical
manifest is refreshed during implementation.

The original M3 helper delegates only the fixed M4 scope and verifies M4 before
projecting original M3 bytes. The existing dependency historical view delegates
the exact M4 frozen successors. In-memory projection may repeat, but each call
first reads and verifies the actual physical current successor; rollback of the
real file never becomes an accepted predecessor. M2/M3 manifests stay unchanged.
The existing M3 test keeps its ID and exact old assertions after that verified
projection. New independent controls reject tamper, rollback, missing files,
manifest resealing, unknown membership, deletion, rename and symlink modes.

The M4 scope belongs only to the checkout that owns its source/verifier. An
inspection of a different or minimal planning repository cannot inherit these
runtime allowances. Its original unknown-runtime rejection remains in place;
neither its missing history nor a policy module from another checkout supplies
the exact M4 prerequisite. Existing M7 tests and assertions remain unchanged.

Exactly three frozen runtime seams change: the original atomic coordinator can
consume one concrete current transaction, native recovery can verify its exact
immutable lineage against the accepted prefix, and M6 replay can consume only
that verified snapshot. Original M5 stale guard, operation schemas, renderer,
review/authority/P3 consumers and publication transport are unchanged. No caller
boolean, generic success callback, wildcard, new SQL state index or publication
permission is introduced.

The roadmap's exact reviewed status successor records M3 complete and M4 in
progress, adds one new dated entry and updates the closing summary. All earlier
decision entries remain verbatim. M4 acceptance still needs final-head CI and
independent review. M5–M7 and Phase 6 remain unstarted.

The additive M4 native fault/recovery groups are partitioned after observing a
Windows timeout; the 15-minute cap is unchanged. Their independent native seed
needs ADD then RENAME, while the complete sequence separately retains its real
initial M5 UPDATE. No original assertion, validator or live capability is skipped.

The additive M4 Windows/Linux workflow retains read-only permissions, pinned
actions, existing requirements and 15-minute limits. Every inherited mandatory
workflow, original node identity, source pin, historical acceptance and 512 MiB
parent/worker safeguard remains required. No baseline refresh, test renaming,
production-source/catalog/artwork change, package approval, publication or merge
is authorized by this maintenance.
