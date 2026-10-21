# Playlist contract — M3 (opt-in)

This is a real `Contract` using M1's unchanged strict v1 JSON Schema. It is a
review candidate, **not an activated or exact-package-approved contract**. No
production entrypoint imports this package. Importing it creates no state.

| Artifact | Version / canonical SHA-256 |
| --- | --- |
| [Contract](contract-v1.json) | 1.0.0 / `5047d834ecd3f8e5a0ed76ae24760b6947ae6b83e95198ce602e1715e445016b` |
| [M1 review registry](registry-v1.json) | 1.0.0 / `8f653ccd64c0635cebcf148261b7ff48871929eac569a84875d58a334947925b` |
| Complete M2 adoption registry | 1.0.0 / `0b0c2af06124379206d43c36a4c12fb456e3861dd335343f4382865a7aab6a05` |
| [Nine original M2 records](historical-outputs-v1.json) | `dfd5948dd9b80975ee30a58d1cc412232be34702a3d065df5a1eaaba869744d5` |
| [Compatibility report](compatibility-v1.json) | `ea812f2d7afbad6ee784271792ee4d3870ec5f99252a95dde44ed102fc58c138` |

All are canonical Package E hashes, independent of pretty printing and object
key order. Exact historic Unicode is retained. The historical record extraction
is checked against the **complete 14,079-member externally pinned M2 registry**,
its original six schema pins and each member/job hash; it is not a replacement
adoption registry. No historical receipt or approval is rewritten.

M1 requires a real `ContractApproval` and external `TrustedDecision` for an
approved registry entry. The implementation authorization is not approval of
this newly authored exact package hash. Consequently the bundled review basis
has **zero approved entries**, rather than a forged approval or placeholder
approval hash. `PlaylistBoundary.load` requires three explicit external pins
and exposes candidate validation only. This basis cannot select Playlist through
M1 `RegistrySnapshot.select`.

After an actual exact-package decision, `registry_for_decision(approval,
trusted_decisions=...)` checks the unchanged M1 authority boundary and constructs
a separate `playlist-contracts` registry. The caller must review/pin its new
hash. It persists/activates nothing. Ordinary JSON cannot construct the trusted
decision map. `ContractStore.pin` can archive either immutable version in an
explicit isolated root; it never approves, publishes or activates them.

## Validation boundary

* `verify_membership` requires the exact nine M2 records, without substitutes,
  duplicate identities, output collisions, missing context or extra members.
* `verify_design` binds the exact release to typography, all composer values,
  nine captured measurement contexts, background assignments, original
  acceptance references and the unchanged white-wash implementation.
* `validate_existing(identity, definition, job)` compares the complete expanded
  definition and complete raw/effective job against the independently pinned M2
  record. Inherited, nested, language, normalized and renderer-clamped overrides
  cannot bypass equality. This function never renders or adopts a job.
* `validate_submission(content, source_root=..., identity=..., request=...)`
  accepts only `display_name`, `source` (exact path/hash), `content_type` (only
  `timeline-order`, optional), and `background_proposal`. The first, source and
  background are required. It hashes confined, exact-case PNG references under
  `logos_playlist/`. It **does not decode PNGs or prove transparency**. New names
  must already be NFC. A supplied identity comes from controlled assignment,
  outside contributor JSON; M3 assigns no IDs or filenames.
* `validate_proposed_definition` additionally checks a prospective authored
  effective definition, locked composer/caption, independent background
  proposal, exact assigned English paths and raw/effective equality. Overrides,
  generators and dependencies are closed. Metadata is always pending; it is
  not a new accepted catalog item or render-ready job. A fixed-size prospective
  layout has no measurement: historical captures cannot be copied as new fit
  approval. Actual fit/preview checks await M4 and subsequent gates.
* `audit()` rereads the actual nine catalog definitions, source/font/shared
  bytes, pinned translation input and renderer implementation/encoding. It
  produces per-item compatibility outcomes and reports extra/missing membership.
  Existing normal accepted alpha assets get no new pixel check or warning.

The background proposal never becomes a maintainer-approved assignment. Default
treatment stays WHITE_ONLY even while SOURCE_PRESERVING is requested. Requests
use M1 `ExceptionRequest` separately, with reason, exact assigned identity,
source, contract/variant, transform and material context. `request_context` is an
evidence interface, not a decision. Content, source or context changes invalidate
the request binding. Intentional-background requests use the same pending path.

`ExceptionState` distinguishes default selected, source-preserving requested,
pending review, externally verified approval and rejection. **M3 can emit only
the first three**. M1's preview, submitter confirmation and maintainer exception
decision types remain future evidence interfaces. No contributor-provided
reviewer, approved state or raw wash toggle is accepted. M4 must verify actual
previews, complete output membership, two independent decisions and current
context before it can supply an approved/rejected outcome. Submitter confirmation
and contract approval never grant publication authority.

## Reproduce without rendering

```sh
python -m create_defaults.bulk.contracts.playlist \
  --contract-sha256 5047d834ecd3f8e5a0ed76ae24760b6947ae6b83e95198ce602e1715e445016b \
  --registry-sha256 8f653ccd64c0635cebcf148261b7ff48871929eac569a84875d58a334947925b \
  --adoption-sha256 0b0c2af06124379206d43c36a4c12fb456e3861dd335343f4382865a7aab6a05
python -m pytest create_defaults/bulk/tests/test_playlist_contract.py -q -p no:cacheprovider
```

The CLI writes JSON to stdout only, exits 2 on blocked/incompatible evidence and
has no force, renderer, persistence, staging or activation option. Source changes
outside the exact accepted M2 context fail closed, requiring explicit assessment.
No new language, caption key, automatic shrink, pixel metric, production
preflight, lifecycle operation or publication path is implemented. General
multi-category expanded-definition/dependency integration remains M5; mandatory
translation preflight remains Phase 3. Overlays remain independently
SOURCE_PRESERVING, with their original white/color branches and both sizes.
