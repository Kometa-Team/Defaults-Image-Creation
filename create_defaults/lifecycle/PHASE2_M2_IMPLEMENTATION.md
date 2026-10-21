# Phase 2 / M2 — historical adoption and compatibility audit

M2 implements read-only adoption under the maintainer's explicit authorization.
M1 was merged through PR #15 at `3d97bb888a2c3787609e4a0c88d5ee3e99bdcae2`, the
M2 branch base. M1 is COMPLETE; M2 and Phase 2 remain IN PROGRESS pending review.
M3–M7 have not started. The accepted discovery, category matrix, exception
register and D01–D09 architecture are unchanged.

## Verified baseline

| Identity | Exact value |
| --- | --- |
| Source snapshot | `3d97bb888a2c3787609e4a0c88d5ee3e99bdcae2` |
| Accepted discovery runtime-source baseline | `e7febf88d1dc8f8b93408e88da78e524b191acea` |
| Artwork snapshot | `dfff31ab08446353844bb97de601c3a64edc8220` |
| Source/schema/evidence pin set | `b2006d1b1327bad2db15054871b3155d704a9c8a14a6efa651a3f90231d147e3` |
| Historical evidence index | `b93a56c4d413517978f16830d7e54a6722db7448316da4afb8210b00d27d7728` |
| Factual adoption registry | `0b0c2af06124379206d43c36a4c12fb456e3861dd335343f4382865a7aab6a05` |

Complete tree IDs, all source/schema file hashes, original receipt origins and
per-category/group counts are committed in the [source pins](../bulk/contracts/adoption/source-pins-v1.json),
[evidence index](../bulk/contracts/adoption/evidence/index-v1.json) and
[audit](../bulk/contracts/adoption/baseline/audit-v1.json). These are pinned
historical snapshots, not a claim to have newly downloaded current remote art.

| Accounting unit | Verified count |
| --- | ---: |
| Declared definitions / generator families | 4,372 / 102 |
| Concrete posters / generated children within posters | 9,957 / 5,687 |
| Public posters / private Awards intermediates | 9,955 / 2 |
| Overlays / groups / size variants | 4,122 / 18 / 2 |
| Total output records / unique local output paths | 14,079 / 14,079 |
| Public records / unique public paths | 14,077 / 14,077 |
| Unique nongenerated source/font/shared-input paths | 2,106 |
| Nongenerated dependency references / generated-parent edges | 83,613 / 165 |
| Owned worker specifications and output-byte identities verified | 14,079 |
| Historical actual production-response receipts verified | 14,077 |
| Historical approval evidence found / private outputs without inferred approval | 14,077 / 2 |
| Unexplained material, identity, destination or membership changes | 0 |

Dependency revisits are not extra output records. The 2,061 original public logo
PNGs and 22 separator templates outside the generated catalogs remain protected
and are not adopted as missing generated outputs or deletion candidates.

## Method and retained exceptions

The audit expands the existing catalog with the registered Package E generators,
compares fully expanded definitions and exact raw/effective parameters with the
native accepted jobs, verifies original worker-spec/receipt ownership bindings,
rehashes required physical assets/fonts, and reconciles all public outputs with
their original actual-response receipts. It neither runs rendering workers nor
uses filenames as visual-equivalence evidence.

Stable poster IDs and existing overlay instance IDs are frozen in the
[complete identity mapping](../bulk/contracts/adoption/baseline/stable-mapping-v1.json.gz).
Source identity, display, caption/reference, definition, local/public names,
kind/size, semantic family member and dependencies remain independent. Any
filename-only change conflicts with the frozen mapping rather than silently
creating a replacement identity.

Historical flattened render jobs omit generator-family origin metadata. M2 adds
explicit links for all 5,687 children to their 102 pinned declarations; it does
not edit old jobs, receipts or render fingerprints. The accepted source-case
bridge affects 307 poster contexts. The accepted public-mapping bridge records
one Action & Adventure mapping and 22 canonical overlay worker mappings. Those
22 worker mappings correspond to **21 historical public renames** because the
bigger Tokyo MX public path was already canonical. These are accepted historical
representations, not new renames or unexplained differences.

Paired output membership is preserved for Chart (1,182), Country (602), Network
(564) and Streaming (256). Existing white-source PNG branches remain distinct
where used; Country's derived-white treatment is retained. This records current
membership without implementing silhouette comparison or new BOTH_REQUIRED
intake enforcement. All 18 overlay groups remain source-preserving in both sizes.

Nine Playlist definitions retain their Bebas Neue/font-size-154 designs, geometry
and individual colors. All 56 existing source-preserving assignments across
Franchise, Genre, Seasonal and Universe remain intact, including Splatter's red
appearance, Black History and Monsterverse. Studio, era typography, generated
compositions, two private Awards outputs, exact Tokyo MX/Action & Adventure case
and all literal Unicode/punctuation mappings are preserved. The 17 normal
accepted historical alpha assets have 41 existing output uses and receive no
new warnings, cleanup, generation or review. The accepted exception register
remains the authority; tags are bound to exact adopted records and hashes.

## Authority, persistence and testing

Factual adoption, material compatibility, historical approval evidence and new
publication authorization remain separate. All 14,079 records verify unchanged
historical material. Compatibility with future category contracts is explicitly
**not assessed** because M3/M6 have not authored those contracts. Two private
intermediates retain byte/ownership evidence without inferred visual approval or
public membership. Original human decisions are copied verbatim as evidence,
not recreated, broadened or promoted into new publication permissions.

Two new historical-fact schemas use M1 immutable `Document` / `Identity` APIs and
an empty, hash-pinned M1 basis registry. The existing contract-approval/adoption
types are deliberately not misused to fabricate category approval. The isolated
M1 Store gains additive `contract_adoption_*` sidecars; atomic blobs precede a
single transaction for the complete registry pointer, basis pin and event.
Rollback/restart, idempotence, immutability and corrupt-state rejection are tested.
No existing Python module or M1 schema requires modification.

Synthetic tests cover source/context mutation with unchanged hypothetical image
bytes, exact/NFC/case collisions, missing/duplicate/extra outputs, ordering,
wrong receipts, schema/hash pins, incomplete pairs, write/transaction interruption,
restart, corrupt state and rejection of adoption records as publication approval.
One full baseline test recomputes all 14,079 records and the complete registry
hash while explicitly prohibiting rendering, live state and network access.
Existing Windows/Linux CI discovers these tests without workflow changes; final
results and the exact implementation commit are recorded in the draft PR.

The [complete changed-file list](../bulk/contracts/adoption/CHANGED_FILES.md)
contains only new M2 modules/schemas/metadata/tests/documentation and the explicitly
requested roadmap status update. No definitions, fonts, artwork, renderer,
translation/publication logic, production destinations or Default-Images files
change. No PR is merged and production enforcement remains inactive.

Before M3, the maintainer must review M2 and separately authorize the next
milestone. Actual Playlist contracts and future contract compatibility still need
their own implementation; calibration, intake workflows, translation gates,
lifecycle operations and production activation remain later work.
