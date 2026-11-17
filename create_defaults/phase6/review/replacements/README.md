# Two historical Playlist replacements: review preparation only

`replacement-plan.json` binds the two approved JPEGs to the existing historical catalog IDs and unchanged public paths. Pinned production metadata and exact old file bytes came from GitHub plugin GET reads only. Both old Git blob IDs, decoded SHA-256 hashes, sizes, ordinary file modes, and root/subtree membership were verified. The helper also checks both candidate hashes and the visual approval's catalog/comparison hashes.

The generic `create_defaults/bulk/operator_publication.py` workflow supports an inventory with non-null `published_sha256` and actual `published_blob`, leading to same-path replacement members. `library_stage.verify_diff` requires precisely an `M` diff with old/new `100644` modes and both blob identities for such members. This can preserve the historical IDs because no catalog edit is needed.

The Phase 6 Playlist lifecycle adapter cannot perform this historical update. `NativeSelection.verify` requires assigned entries and the owned Playlist pilot permits ADD only; `prepare_catalog` admits UUID-style assigned IDs and rejects overlap with historical Playlist index IDs; `playlist.operator_membership` recognizes only additions with absent preimages. No safety gate was changed or bypassed.

This plan is not an operator approval, staging authorization, executable batch plan, publication, or merge. The existing visual approval permits replacement fixtures and explicitly withholds live execution/publication. A later authorized generic operator proposal needs a sealed exact inventory, proposed policy and candidate manifest, current production HEAD/tree and actual preimages, full review context, supported named maintainer attribution, exact policy/manifest hashes and explicit individual-exception acceptance. Any drift requires a refreshed proposal and appropriate decision. No branch, PR, push, or other remote write occurred.

Source references within `../style-candidate/`:

- `create_defaults/bulk/operator_publication.py:12` prepare candidate membership; `:48` exact maintainer decision; `:73` authorize; `:150` stage and baseline refresh.
- `create_defaults/bulk/library_stage.py:128` complete replacement diff and committed SHA-256 verification; `:286` transport/current-head and non-force draft branch staging.
- `create_defaults/bulk/library_sources.py:130` production snapshot; `:160` pinned existing blob bytes.
- `create_defaults/bulk/lifecycle/publication_preparation.py:90` Playlist ADD-only; `:98` assigned-origin native selection; `:192` full preparation revalidation.
- `create_defaults/bulk/lifecycle/catalog_preparation.py:257` UUID catalog scope and historical Playlist overlap rejection.
- `create_defaults/phase6/playlist.py:334` test-only operator membership recognizes absent preimages only.
- `create_defaults/bulk/lifecycle/draft_transport.py:196` typed owned local lifecycle proposal; `:224` fixture binding.

`prepare_review_plan.py` reproduces the byte verification from the captured GET results without network or imports from the candidate worktree. All files written by this preparation are confined to this directory.

## Unapplied binary patch

`two-playlist-replacements.patch` is a Git binary patch generated with `git diff --binary --full-index` for exactly the two unchanged paths. Size: 1,413,084 bytes. SHA-256: `a32e232ae315b58ca05f443b4c5301ae2886950657f5b496652ec3167789f108`.

`prepare_binary_patch.py` created two new local repositories under this folder, each containing only the verified preimage JPEGs. It has no remote and refuses to reuse existing fixture directories. In the second fixture, `git apply --check --index` passed, applying the patch produced the exact approved SHA-256 and Git blob hashes, and the complete staged raw diff contained exactly two `M` entries with old/new `100644` modes and the approved blob IDs. Regenerating the staged binary patch produced identical patch bytes. Reverse-check and reverse-apply passed; both original SHA-256/blob identities were restored and the validation fixture was clean.

`patch-validation.json` and `replacement-plan.json` record these results. The patch remains unapplied to any real repository. No remote write or live authorization was introduced.

| Public path | Preimage Git blob | Approved Git blob |
| --- | --- | --- |
| `playlist/X-Men (Timeline Order).jpg` | `8ecca4724ea343a5f9865aef914ef1eaee57bd10` | `d5c34027fe1f00fa4facba9490e5bed4994f2a77` |
| `playlist/Star Wars The Clone Wars (Timeline Order).jpg` | `918d77e4e888cd78387c1597836d16c2bd30ed88` | `b981a39db31947dc619e0704cb9c40957d2bf28b` |
