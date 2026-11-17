# Phase 6: offline Playlist pilot preparation

Status: IN PROGRESS / draft review. This is an isolated fixture pilot, not live execution or final Phase 6 acceptance.

## Authorization and accepted baseline

On 2026-11-17 the maintainer authorized offline preparation for exactly avp, babylon, bsg, gundam, jrrt, sao, stargate and wdu. Local fixtures and fixture approvals are the only permitted positives. Real contract/artwork/operation approvals, live catalog writes, publication, activation and merge require separate decisions.

Fetched main is `dcbfa072dbedcb0069dd27be920ef3103687b5a4`, the verified merge of [PR #71](https://github.com/Kometa-Team/Defaults-Image-Creation/pull/71). Its accepted head `00d8916ea414e1af1b1c00c855c9f763dc4dece6` passed all 12 workflows / 257 jobs. Independent M7 replay passed in 1589.013 seconds against all 255 GitHub-digest-verified archives / 1,191 files and all 34 requirements. The independently supplied provenance export SHA-256 is `1d613c06d8212e6d57f94ec1f44c17b7bee8ad7de4b40102094ee1f652435263`; exact workflow links and output remain in the merged PR evidence index. No accepted CI was rerun to update the roadmap.

The merged [Phase 5 handoff](PHASE5_HANDOFF.md) and M2-M7 evidence remain immutable historical records. Its eight-request list is preserved. Phase 5 technical acceptance still grants only 27 conditionally supported offline English Genre variants; 251 remain blocked, all 22 real package approvals are absent, and operational authority remains false. This separately authorized fixture work does not rewrite that acceptance or activate Playlist.

## Provisional manifest

[PLAYLIST_PILOT_MANIFEST.json](../phase6/PLAYLIST_PILOT_MANIFEST.json) binds all eight original supplied PNG bytes to display names, persisted UUID proposals, semantic keys, and local/public output paths. The maintainer confirmed all eight names and the existing `(Timeline Order).jpg` filename convention, explicitly including `Mobile Suit Gundam (Timeline Order).jpg` and `The Walking Dead Universe (Timeline Order).jpg`. The UUIDs are retained across fixture replays; live registry reservations and catalog mappings remain pending.

| Logo | Proposed display name | Proposed persistent identity | Proposed public output |
| --- | --- | --- | --- |
| avp.png | Alien & Predator | `playlist.feec6426d0134e93973e8a2b36bd1ebe` | `playlist/Alien & Predator (Timeline Order).jpg` |
| babylon.png | Babylon 5 | `playlist.2d41498dd84b47a58ffd8f1728bfa32f` | `playlist/Babylon 5 (Timeline Order).jpg` |
| bsg.png | Battlestar Galactica | `playlist.ca5bf3fafc7a4f888dbee738fc6fea09` | `playlist/Battlestar Galactica (Timeline Order).jpg` |
| gundam.png | Mobile Suit Gundam | `playlist.70487260288d489fa6e4d06672990a67` | `playlist/Mobile Suit Gundam (Timeline Order).jpg` |
| jrrt.png | Middle-earth | `playlist.5eba47e8c0a04c2e9914f6618b621f2c` | `playlist/Middle-earth (Timeline Order).jpg` |
| sao.png | Sword Art Online | `playlist.c48a75120f4f4a8aa290c3683b2dc1d2` | `playlist/Sword Art Online (Timeline Order).jpg` |
| stargate.png | Stargate | `playlist.11d52d3953a64d0faabcd7a692fbb87f` | `playlist/Stargate (Timeline Order).jpg` |
| wdu.png | The Walking Dead Universe | `playlist.0aabd1b1c7d44b198858057648ba9514` | `playlist/The Walking Dead Universe (Timeline Order).jpg` |

Every proposed local output is `defaults-en/` plus its public path. Logos retain their exact supplied basenames in the manifest; the temporary native asset tree uses `logos_playlist/Fixture <label>.png` to satisfy CompositionTrial's existing isolation rule. The original PNG bytes are copied unchanged. Every logo is RGBA with transparent and opaque pixels. The manifest records raw SHA-256, dimensions and byte length; binary image digests are never newline-normalized.

All eight display names and filename conventions above are confirmed. The original shared `#123456` renders are retained as historical fixture evidence. The maintainer approved the revised eight-poster colour contact sheet for the offline pilot; [visual-approval.json](../phase6/review/visual-approval.json) binds its exact SHA-256 and all eight JPEG hashes. This visual review grants no real operational/package/source-quality authority. Gradient 1 (`fades/@center-out-fade.png`) and the existing default white logo treatment remain unchanged. Live registry reservations and catalog mappings remain pending.

| Playlist | Approved offline colour | Colour origin |
| --- | --- | --- |
| Alien & Predator | `#1EAC1B` | Existing Alien Predator Franchise colour |
| Babylon 5 | `#5B4A86` | New proposal approved for this offline set |
| Battlestar Galactica | `#3C6382` | New proposal approved for this offline set |
| Mobile Suit Gundam | `#285DA8` | New proposal approved for this offline set |
| Middle-earth | `#C28A25` | Existing Middle Earth Franchise colour |
| Sword Art Online | `#25A6B2` | New proposal approved for this offline set |
| Stargate | `#6C73A1` | Existing Stargate Franchise colour |
| The Walking Dead Universe | `#797F48` | Existing The Walking Dead Franchise colour |

[Approved contact sheet](../phase6/review/eight-poster-colour-proposals.png) Â· [Nine-poster historical comparison](../phase6/review/nine-poster-historical-comparison.png). Source line references and render hashes remain in [colour-review.json](../phase6/review/colour-review.json); original before/after measurements remain in [historical-comparison.json](../phase6/review/historical-comparison.json).

The first real-source fixture stopped at the unchanged native PNG quality gate (`source_transparency_or_quality_review_required`, 125.18s). All eight logos have edge-contact/clean-background diagnostics; avp/jrrt also have embedded ICC diagnostics. Babylon, Gundam, SAO and WDU additionally have `rectangular_alpha_background_not_proven_transparent`. The manifest preserves every complete source-quality report and its digest, with a separate explicit synthetic-only acknowledgement. The owned fixture capability admits only those exact reports on the exact original PNG bytes, keeps all findings in native evidence, rejects new findings/opaque sources, and grants no real quality or intentional-background approval. All eight require separate real source/artwork quality decisions before live use. No pixels were repaired or edited.

## Reused path and exact gaps

The existing path is retained: `IdentityRegistry.allocate` -> `poster_candidate` / `PlaylistBoundary.validate_proposed_definition` / `playlist_mapping` -> `operations.propose(ADD)` -> native composition and immutable worker receipts -> current Phase 3 translation/source/destination consumption -> submitter confirmation and independent synthetic maintainer review -> `Transaction.prepare` / `apply.commit_synthetic` -> `OwnedCatalog` / `prepare_catalog` -> `NativeSelection` / `plan_operation` -> original M6 operator binding, staged catalog/artwork bytes, scoped bare-Git draft transport, complete tree/byte verification and idempotent retry.

The inherited prospective Playlist layout rejection was confirmed on untouched current main: `test_prospective_playlist_layout_gap_is_explicit_never_waived` passed (214.77s). Ordinary Playlist requests retain that rejection. A separately typed `OfflinePlaylistPilot` lifetime capability permits the exact M3 prospective fixed layout only inside its newly created CompositionTrial and real isolated registry, for the eight manifest-bound identities, names and unchanged logo bytes. Its manifest digest is part of the Phase 3 dependency evidence. It cannot adopt a supplied root, other category, arbitrary identity, closed trial or UPDATE.

Existing Genre-only gates are narrowly extended for that capability: ADD transaction admission, the closed preparation DTO/schema, staged Playlist catalog/index preparation, Playlist artwork selection/destination preparation and original operator authorization. Default Genre behavior, including the exact three-file source DTO, is retained. A Playlist DTO must contain only the eight manifest identities, their exact addition paths, no preexisting output hashes, and the exact four-file owned source cohort. Parsing that read-only value grants no authority; planning/transport still require the live owned capability and exact native review. The original operator recognizes only a weakly retained, actual native preparation for the same live trial and exact member bytes/paths; no new policy flag can authorize another Playlist path. The original M6 policy shape, draft binding, transport, write guards, resource/batch limits and recovery remain unchanged. No alternate renderer, catalog loader, review approval, Git protocol or live publisher is introduced.

The source fixture copies the actual Genre/Playlist catalogs, profiles and full index. It stages only eight prospective Playlist definitions/index additions; all nine historical Playlist definitions and every existing index entry remain unchanged, and Genre/profile bytes are exact. The local destination fixture uses explicitly synthetic JPEG bytes at the existing Genre/Playlist paths. Its full preimage tree must be byte/blob/mode identical after the eight additions. This proves fixture preservation, not a fresh audit of live Default-Images bytes. Historical artwork is never regenerated; protected source/adoption and output-inventory evidence remain historical authority.

## Validation and retained evidence

The production Python path now has an explicit `playlist-contained-v1` style in `create_defaults/poster_styles.py` and reusable alpha-aware containment in `create_defaults/image_layout.py`. Normal Playlist plans select this style, include it in their render fingerprint, and pass it through the existing worker to `create_poster`. Direct Python/CLI callers adopt it explicitly with `style=` / `--style`. Callers without bounds retain their original behavior. The original PNGs, historical catalog definitions, captured measurements and prior receipts are not rewritten. The maintainer approved the WDU, Clone Wars and X-Men layouts and then the eight-colour visual set for the offline pilot; this grants no operational or package approval.

The historical whole-module transformation pin `ff748c9c8422a46f662f36a094a3ef523d2f9c4c23d622729f18c1f1894e0717` remains recorded in every original contract. The implementation registers only the exact renderer successor `ecf84c06bfeb5a7ee54b9f976d9fcd1de0dabb0680558e48cd975126d19af472`, whose unbounded path remains pixel-identical to the immutable main renderer. Unknown source hashes, changed encoding and changed canvas remain rejected. This compatibility registration preserves the old white-wash implementation evidence; it is not approval of the new bounded design. The new source files, style policy and candidate/P3 dependency fingerprints bind the proposed geometry separately.

On the unchanged 2000 x 3000 canvas, the logo box is `(200, 850, 1800, 1750)` (1600 x 900), centered on the old logo anchor `(1000, 1300)`. The caption box is `(50, 1850, 1950, 2050)` (1900 x 200), centered at the existing `(1000, 1950)` with 154pt typography. Its upper bound minus the explicit 100px gap determines the logo box's lower edge, 1750. The original 1600 x 1000 captured-fit box remains caption measurement evidence; it is not a logo-height limit. The existing native caption helper still uses its original 1900 x 1000 rasterization canvas and placement.

Each render crops to the source's visible alpha bounds, uniformly contains those pixels within both logo dimensions, and centers the final visible layer at the style anchor. Transparent padding has no influence on scale or centering. The renderer checks the actual fitted-logo and caption-layer bounds and their minimum gap. Caption overflow is rejected; new text fitting, font shrinking and Genre compositing are outside this patch. A whole-composition border resize is rejected for this style because it would invalidate these coordinates. Before/after comparison copies and the contact sheet are separate offline outputs; stored historical baselines and live outputs are never overwritten.

The pilot proves one real addition first, then all eight in a separate native fixture using the existing batch limits; it checks all baseline poster blobs and unchanged catalog entries. The eight-item builder validates each member using the unchanged single-item M3 API, after checking the complete owned cohort and requiring each independently planned job to equal its full-plan job. Its original hidden-new-companion rejection is unchanged. Fast tests cover every job, the original rejection, resealed omission, and fresh ownership/config/source checks. The pilot helper shares one freshly replayed registry view within each call instead of replaying that history once again per output; it retains a closing lifetime/root/manifest check. Original CompositionTrial checks remain in the composition path. Native negative cases cover changed/missing/replaced staged logos, UPDATE, foreign roots, unknown quality findings, unapproved operator paths and closed capabilities. Accepted M6 retry/recovery evidence is reused; this pilot does not repeat those unchanged scenarios. The separate CI provenance tests cover immutable-object batching, fresh physical files, missing files, rollback, unknown paths, mode/link changes, independently supplied expected HEAD and closing HEAD movement. Native fixture invocations bind their source HEAD at entry and exit; CI also runs full physical source proofs before and after the tests.

```text
python -B -m unittest ci.dependency_tests.test_phase6_playlist_maintenance -v
python -B -m pytest create_defaults/tests/test_create_poster.py create_defaults/tests/test_playlist_layout.py -q
python -B -m create_defaults.phase6.render_review --output-dir config/phase6-playlist-evidence/artwork-review
python -B -m pytest create_defaults/phase6/tests/test_playlist_pilot.py::test_one_playlist_add_reaches_local_draft -v --maxfail=1
python -B -m pytest create_defaults/phase6/tests -k preflight -q --maxfail=1
python -B -m pytest create_defaults/phase6/tests -m cohort -v --maxfail=1 --junitxml=config/phase6-playlist-evidence/cohort-tests.xml
```

Native JPEGs, worker receipts, exact snapshots/catalog pre/postimages, measured Git packs, journals, local-Git-backed RemoteBytes fixtures (HTTP forbidden; the legacy receipt format is not independent GitHub provenance), local draft receipts and a transport bundle are exported using the existing M6 artifact exporter under `config/phase6-playlist-evidence/`. Actual commit SHA, results, timings and remaining platform gaps belong in the draft PR evidence index. The new Windows/Linux workflow separates the single ADD from the eight-item job, with an explicit successful-job dependency. Expensive pilot jobs skip draft PRs and run only after a ready-for-review decision or manual dispatch. Proposed budgets are 100 minutes for the single ADD and 180 minutes for the cohort; no pilot workflow is dispatched here. The single checkpoint took 73m35.871s including an additional accepted-M6 retry, which the narrowed pilot no longer repeats. Cohort budget/platform confirmation remains pending; existing workflows and all their budgets/test selection are unchanged.

`ci/phase6-playlist-maintenance-v1.json` is a new exact successor receipt at the merged M7 baseline. Prior sealed receipts and 190/299 inventories are not edited. The existing M7 owner delegates only the new receipt's exact file set, projects exact approved physical successors onto their immutable merged predecessors for historical consumers, and retains entry/closing HEAD proofs and per-file checks. The existing dependency-audit successor chain also selects only the exact registered physical operator successor, with fresh entry/closing proofs; the central dependency selector, M6 historical selector and all sealed assertions retain their original bytes/pins. Physical closing metadata includes the delegated current hashes; historical projection retains the original bindings. The People/Pillow 13 implementation and all its receipts remain unchanged. Only overlapping M7 members are checked inside generic inherited M6 calls; full Phase 6 scope checks separately authenticate the new cohort and register a full aggregate closing proof, avoiding repeated unrelated PNG reads. Immutable Git objects alone may be reused across calls, keyed only by full immutable SHAs. Original sealed M7 unit fixtures keep their independent legacy roots and all original assertions unchanged.

## Decisions still required for live work

- Review live registry reservations and catalog mappings; all eight names and filename conventions are confirmed.
- Approve the exact Playlist package, backgrounds, logo treatment and complete final artwork separately; fixture confirmation/approval is not real approval.
- Supply authenticated source, identity, role, destination/head, withdrawal/revision, expiry and revocation authority.
- Authorize exact real catalog and destination operations, transport, publication and activation separately. Revalidate current heads and complete membership at each prospective write.
- Accept final-head Windows/Linux pilot evidence and independent artifact replay before considering further Phase 6 work. Other operations/categories, live recovery and final production acceptance remain outside this fixture pilot.

No live catalog write, public artwork publication, activation, automatic merge or deletion is authorized by this document.

## Local evidence checkpoints

Renderer/artwork checkpoint `5503ea2481ca675c3c38d3e6e8472df0efe6a1e8`: 56 renderer tests and 114 subtests passed (44.216s wall), plus all 14 focused Phase 6 provenance / inherited M6 batching checks (19.146s). Fresh bounded WDU candidate/composition/Phase 3 consumption passed in 212.001s; ordinary callers retain the legacy renderer. All eight colour renders reproduced direct-renderer JPEG bytes, kept the exact reviewed visible bounds and caption placement, and passed entry/closing checkout proofs (18.459s).

The nine historical comparisons preserve their original catalog artwork/backgrounds and immutable baseline: seven JPEGs are byte-identical. Clone Wars changes from 1600 x 967 to 1490 x 900; X-Men changes from 1600 x 979 to 1471 x 900. Both remain centered at the original anchor and fit the 900px safe height. WDU has a measured 145px caption gap.

Original shared-colour transport checkpoint `36082218ccae11fdeca8f06f953bf2870cb44715`: all nine native cohort/negative tests passed in 6556.177s wall, adding eight and preserving all 284 synthetic baseline posters. That proof remains archived separately and does not certify the new approved JPEGs. The final approved-byte run at `fa8870f4e23d6e0e0161b3fd43385ef9c90e045b` passed: both composition views and all eight retained destination JPEGs match the approved bytes, the verified local draft preserves 284 baseline posters, and zero network writes occurred (6105.271s wall). Exact paths/hashes, native proof and remaining platform gaps are in the [evidence index](../phase6/review/EVIDENCE_INDEX.md). Windows local evidence is available; Linux pilot execution and hosted final-head results remain pending. No repeated M7 replay or M6 hosted rerun was performed.
