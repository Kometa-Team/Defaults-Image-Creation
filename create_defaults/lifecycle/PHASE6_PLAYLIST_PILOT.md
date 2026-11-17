# Phase 6: offline Playlist pilot preparation

Status: IN PROGRESS / draft review. This is an isolated fixture pilot, not live execution or final Phase 6 acceptance.

## Authorization and accepted baseline

On 2026-11-17 the maintainer authorized offline preparation for exactly avp, babylon, bsg, gundam, jrrt, sao, stargate and wdu. Local fixtures and fixture approvals are the only permitted positives. Real contract/artwork/operation approvals, live catalog writes, publication, activation and merge require separate decisions.

Fetched main is `dcbfa072dbedcb0069dd27be920ef3103687b5a4`, the verified merge of [PR #71](https://github.com/Kometa-Team/Defaults-Image-Creation/pull/71). Its accepted head `00d8916ea414e1af1b1c00c855c9f763dc4dece6` passed all 12 workflows / 257 jobs. Independent M7 replay passed in 1589.013 seconds against all 255 GitHub-digest-verified archives / 1,191 files and all 34 requirements. The independently supplied provenance export SHA-256 is `1d613c06d8212e6d57f94ec1f44c17b7bee8ad7de4b40102094ee1f652435263`; exact workflow links and output remain in the merged PR evidence index. No accepted CI was rerun to update the roadmap.

The merged [Phase 5 handoff](PHASE5_HANDOFF.md) and M2-M7 evidence remain immutable historical records. Its eight-request list is preserved. Phase 5 technical acceptance still grants only 27 conditionally supported offline English Genre variants; 251 remain blocked, all 22 real package approvals are absent, and operational authority remains false. This separately authorized fixture work does not rewrite that acceptance or activate Playlist.

## Provisional manifest

[PLAYLIST_PILOT_MANIFEST.json](../phase6/PLAYLIST_PILOT_MANIFEST.json) binds all eight original supplied PNG bytes to proposed display names, persisted UUID proposals, semantic keys, and local/public output paths. The UUIDs are retained across fixture replays; they are not reservations in a live registry. Final names, semantic scope, persistent registry reservations and output mappings remain pending confirmation.

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

Naming questions: Alien & Predator versus Alien vs. Predator; Middle-earth versus the supplied Middle Earth Collection wording; and the Gundam timeline/series scope. The Battlestar, Stargate and Walking Dead franchise scope and every final output name also need confirmation. `#123456` is an explicit disposable fixture background, not an approved brand assignment. Source-preserving treatment or intentional background exceptions require their own exact review; the fixture uses the existing default white treatment.

The first real-source fixture stopped at the unchanged native PNG quality gate (`source_transparency_or_quality_review_required`, 125.18s). All eight logos have edge-contact/clean-background diagnostics; avp/jrrt also have embedded ICC diagnostics. Babylon, Gundam, SAO and WDU additionally have `rectangular_alpha_background_not_proven_transparent`. The manifest preserves every complete source-quality report and its digest, with a separate explicit synthetic-only acknowledgement. The owned fixture capability admits only those exact reports on the exact original PNG bytes, keeps all findings in native evidence, rejects new findings/opaque sources, and grants no real quality or intentional-background approval. All eight require separate real source/artwork quality decisions before live use. No pixels were repaired or edited.

## Reused path and exact gaps

The existing path is retained: `IdentityRegistry.allocate` -> `poster_candidate` / `PlaylistBoundary.validate_proposed_definition` / `playlist_mapping` -> `operations.propose(ADD)` -> native composition and immutable worker receipts -> current Phase 3 translation/source/destination consumption -> submitter confirmation and independent synthetic maintainer review -> `Transaction.prepare` / `apply.commit_synthetic` -> `OwnedCatalog` / `prepare_catalog` -> `NativeSelection` / `plan_operation` -> original M6 operator binding, staged catalog/artwork bytes, scoped bare-Git draft transport, complete tree/byte verification and idempotent retry.

The inherited prospective Playlist layout rejection was confirmed on untouched current main: `test_prospective_playlist_layout_gap_is_explicit_never_waived` passed (214.77s). Ordinary Playlist requests retain that rejection. A separately typed `OfflinePlaylistPilot` lifetime capability permits the exact M3 prospective fixed layout only inside its newly created CompositionTrial and real isolated registry, for the eight manifest-bound identities, names and unchanged logo bytes. Its manifest digest is part of the Phase 3 dependency evidence. It cannot adopt a supplied root, other category, arbitrary identity, closed trial or UPDATE.

Three existing Genre-only gates are narrowly extended for that capability: ADD transaction admission, staged Playlist catalog/index preparation, and Playlist artwork selection/destination preparation. Default Genre behavior is retained. No alternate renderer, catalog loader, review approval, Git protocol or live publisher is introduced. M6 draft transport, resource/batch limits and recovery remain unchanged.

The source fixture copies the actual Genre/Playlist catalogs, profiles and full index. It stages only eight prospective Playlist definitions/index additions; all nine historical Playlist definitions and every existing index entry remain unchanged, and Genre/profile bytes are exact. The local destination fixture uses explicitly synthetic JPEG bytes at the existing Genre/Playlist paths. Its full preimage tree must be byte/blob/mode identical after the eight additions. This proves fixture preservation, not a fresh audit of live Default-Images bytes. Historical artwork is never regenerated; protected source/adoption and output-inventory evidence remain historical authority.

## Validation and retained evidence

The focused module proves one real addition first, then all eight with partial two-file batches, resume and exact retry; it checks all baseline poster blobs and unchanged catalog entries. Negative cases cover changed/missing/replaced staged logos, UPDATE, foreign roots and closed capabilities. The separate CI provenance tests cover immutable-object batching, fresh physical files, missing files, rollback, unknown paths, mode/link changes and closing HEAD movement.

```text
python -B -m unittest ci.dependency_tests.test_phase6_playlist_maintenance -v
python -B -m pytest create_defaults/phase6/tests -v --maxfail=1 --junitxml=config/phase6-playlist-evidence/tests.xml
```

Native JPEGs, worker receipts, exact snapshots/catalog pre/postimages, measured Git packs, journals, remote-byte responses, local draft receipts and a transport bundle are exported using the existing M6 artifact exporter under `config/phase6-playlist-evidence/`. Actual commit SHA, results, timings and remaining platform gaps belong in the draft PR evidence index. The new read-only Windows/Linux workflow uses the existing pinned actions and a 60-minute job budget; existing workflows and all their budgets/test selection are unchanged.

`ci/phase6-playlist-maintenance-v1.json` is a new exact successor receipt at the merged M7 baseline. Prior sealed receipts and 190/299 inventories are not edited. The existing M7 owner delegates only the new receipt's exact file set, projects exact approved physical successors onto their immutable merged predecessors for historical consumers, and retains entry/closing HEAD proofs and per-file checks. Only overlapping M7 members are checked inside generic inherited M6 calls; full Phase 6 scope checks separately authenticate the new cohort, avoiding repeated unrelated PNG reads. Immutable Git objects alone may be reused across calls.

## Decisions still required for live work

- Confirm all eight final display names, franchise/timeline scope, registry reservations and mappings.
- Approve the exact Playlist package, backgrounds, logo treatment and complete final artwork separately; fixture confirmation/approval is not real approval.
- Supply authenticated source, identity, role, destination/head, withdrawal/revision, expiry and revocation authority.
- Authorize exact real catalog and destination operations, transport, publication and activation separately. Revalidate current heads and complete membership at each prospective write.
- Accept final-head Windows/Linux pilot evidence and independent artifact replay before considering further Phase 6 work. Other operations/categories, live recovery and final production acceptance remain outside this fixture pilot.

No live catalog write, public artwork publication, activation, automatic merge or deletion is authorized by this document.
