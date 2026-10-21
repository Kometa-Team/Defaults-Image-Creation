# Phase 2 / M3 — Playlist contract and adversarial validation

Implemented under the explicit M3-only authorization from source `main`
`f2b7843fd1d832e2aecc36d66046b1010ed7fd5d` (merged M2 PR #16).
M1 and M2 are COMPLETE. M3 and Phase 2 remain IN PROGRESS pending maintainer
review; M4–M7 and Phases 3–6 remain NOT STARTED. The accepted discovery,
exceptions, category matrix and approved D01–D09 design are unchanged.

## Exact artifacts and authority

| Artifact | Version / canonical SHA-256 |
| --- | --- |
| Playlist contract | 1.0.0 / `5047d834ecd3f8e5a0ed76ae24760b6947ae6b83e95198ce602e1715e445016b` |
| M1 review registry (empty approved membership) | 1.0.0 / `8f653ccd64c0635cebcf148261b7ff48871929eac569a84875d58a334947925b` |
| Full M2 identity/provenance registry | 1.0.0 / `0b0c2af06124379206d43c36a4c12fb456e3861dd335343f4382865a7aab6a05` |
| Exact nine original M2 record extraction | `dfd5948dd9b80975ee30a58d1cc412232be34702a3d065df5a1eaaba869744d5` |
| Reproducible nine-item compatibility report | `ea812f2d7afbad6ee784271792ee4d3870ec5f99252a95dde44ed102fc58c138` |

The [implementation and reproduction guide](../bulk/contracts/playlist/README.md)
links every artifact. The [full report](../bulk/contracts/playlist/compatibility-v1.json)
includes all nine exact local/public paths, source hashes, ten context
fingerprints per output, historical exceptions, owned-worker/actual-response
receipt references and accepted output hashes. There are **nine compatible
items, zero unexplained mismatches**. These are retained historical output-byte
facts, not fresh renders or remote downloads.

M1 correctly refuses to index an approved contract without a separately
attributed exact-package decision. This implementation creates no fictional
`ContractApproval`, new historical approval or fake pending approval hash. The
bundled empty review registry cannot select Playlist as approved. Candidate
validation explicitly requires external contract/registry/M2 pins. A real future
decision can pass through `registry_for_decision` and unchanged M1
`RegistrySnapshot.load`, producing a new externally pinned registry. Neither
path activates enforcement or grants publication permission. Package E's
isolated `ContractStore` pins/transactions/events remain the persistence API;
no new tables, production adapters, schema changes or competing store are added.

## Nine historical identities and exact source bytes

Every source below remains under `logos_playlist/`. Display names, source names
and output names are independent; MCU's public output remains the full Marvel
Cinematic Universe name. The complete literal mappings are in the report.

| Stable identity | Source filename | Source SHA-256 | Background | Outcome |
| --- | --- | --- | --- | --- |
| `playlist.playlist-arrowverse-timeline-order.09b7e4b8` | `Arrowverse.png` | `256787f4761e845b3a626ab2c23b943eb626ce0d006a98a92a16ded4fac01f8b` | `#2B8F40` | COMPATIBLE |
| `playlist.playlist-dc-animated-universe-timeline-order.66af9f87` | `dca.png` | `94fba21cefc046ea0a4c4d813a0f376f8a9d85e9ca8441e7fc8eee651f066132` | `#2832C4` | COMPATIBLE |
| `playlist.playlist-dragon-ball-timeline-order.24c7063f` | `DragonBall.png` | `52f4b15178c1cce8e8c1aae9ba73e8683fa88123936b2487bd5d2b5cb0a8c799` | `#E39D30` | COMPATIBLE |
| `playlist.playlist-marvel-cinematic-universe-timeline-order.d704757c` | `Marvel Cinematic Universe.png` | `75b0a1f58deca7a02ab0ebf15997da40d7554d82aa643e647f2d8495af4e82e8` | `#AD2B2B` | COMPATIBLE |
| `playlist.playlist-pok-mon-timeline-order.efe5925f` | `Pokémon.png` | `fc03b941138c112254d545e39be14d6c1f507a02c529b488a029ce1e420ecbde` | `#FECA06` | COMPATIBLE |
| `playlist.playlist-star-trek-timeline-order.53320ead` | `Star Trek.png` | `8a84de6dc3c0e5a5d6002f136b1b7fa496de929cba3b8035b32c92da13b2f2df` | `#0193DD` | COMPATIBLE |
| `playlist.playlist-star-wars-the-clone-wars-timeline-order.c6750e0c` | `Star Wars The Clone Wars.png` | `10e14d9cf5fdc3f63d06dde6690a89a0a8ae216d004e87729a09bcb793a62ebe` | `#ED1C24` | COMPATIBLE |
| `playlist.playlist-star-wars-timeline-order.0af9472c` | `Star Wars.png` | `ed6408d3e9134ef2c528e164ef204feb05148edc54f60abc98cbadfbd39d7cea` | `#F8C60A` | COMPATIBLE |
| `playlist.playlist-x-men-timeline-order.627ce505` | `X-men.png` | `f57574eeefecafbb435ac45cd8b350e51cb8303a78a83f1cdb623e9a8d2191b4` | `#636363` | COMPATIBLE |

## Locked inventory and contributor boundary

* Bundled `fonts/BebasNeue-Regular.ttf`, Bebas Neue Regular, weight 400, SHA-256
  `08e4623805102d819f58601e46e345648846075e363b2ceb23313c2d1c83ec73`.
  Size **154**; nine original captured measurements in 1600 × 1000 retain their
  separate evidence hashes and historical 100–154 bounds. No autoshrink is
  authorized. The contract measurement pin hashes the complete identity-to-layout
  evidence map, `e63d6241d873396b1f2c05198f7b55d18004e5b3dd7fc3cc6edf8cdc0e42c05d`.
* Required `key_names.TIMELINE_ORDER`, current English `TIMELINE ORDER`, uppercase,
  exact translation trace/resource; no alternate type, key, fallback or language.
  Caption canvas 1900 × 1000; white text centered at offset +450.
* Logo width 1600, centered horizontally, vertical offset −200; WHITE_ONLY default
  using the existing alpha-preserving white-wash implementation. Gradient 1;
  border disabled with retained color `#FFFFFF` and width 15; `clean: true`;
  average/dominant sampling false and both image references null. All remaining
  effective values and existing output stems match the frozen records exactly.
* Nine assigned backgrounds and lineage remain exact; assignment-map SHA-256
  `f8c90880f7f69a4fea8da0940552760b7206d3c6d81d3f4109ce333096f6479d`.
  2000 × 3000 RGB JPEG, quality 100, subsampling 0; exact historical English
  output paths and literal Unicode/case are unchanged.
* Contributor fields: proposed display name, exact source PNG reference/hash,
  proposed background, and optional closed `timeline-order` content type.
  Background assignment always awaits maintainer approval. Identity/path
  assignment is separate; no lifecycle operation is implemented. Unknown nested
  fields, fonts, geometry, effects, captions, versions, reviewer/state fields and
  destinations fail validation.

Historical definitions/jobs are checked as complete objects, including raw
intent before renderer normalization. Prospective authored effective metadata
has its own strict boundary; a pending source/background request cannot alter
locked fields or reuse a historical measurement as new approval. This covers
Playlist only, not general production expansion/dependency validation.

## Requests, tests and remaining prerequisites

M1 `ExceptionRequest` represents justified SOURCE_PRESERVING and intentional
background requests against exact assigned identity/source/package/variant/
transformation/material context. The white default remains selected. M3 emits
default, requested and pending conditions; approved/rejected enum values are
reserved for separately verified future authority. No full interactive workflow,
comparison preview, submitter confirmation or final exception transition is
implemented. Changing source or material context makes the old binding fail.

Adversarial tests cover font/size/geometry/case/effects/wash overrides, unknown
caption keys, unapproved background assignments, nested/language overrides,
raw clamp/normalization bypass, schema/version/pin tampering, forged approval,
wrong category/M2 association/context, dependency/input hashes, missing/duplicate
membership, exact/case/NFC collisions, deterministic hashes, immutable Store
versions/restart, per-item audit failures and rejection as publication authority.
The full compatibility test prohibits Pillow image opening, rendering, workers,
production Store and network. Existing Windows/Linux CI discovers this suite
without workflow changes; exact-head results belong to the draft PR.

M4 still needs explicit authorization: real PNG/integrity/alpha inspection,
preview/fit evidence, complete variant membership, two-role decisions and
invalidation, plus deterministic comparison calibration with automation off
until approved evidence exists. Metadata acceptance proves no pixel quality or
transparency. All accepted historical assets remain unchanged without new
warnings or retroactive transparency requirements. No numeric tolerance is
invented. M5's general job/dependency gates and Phase 3 translation safeguards
are not claimed as implemented.

Only new opt-in M3 code/data/tests/docs and the requested roadmap status change
are included. No original YAML, renderer, font/logo/artwork, translation,
publication/destination/workflow, historical approval or Default-Images changes;
no generation, upload, merge or activation. Stop after M3 for maintainer review.
