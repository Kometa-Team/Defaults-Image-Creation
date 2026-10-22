# Phase 2 / M6 — Remaining category contracts

**IN PROGRESS; maintainer review required.** Started 2026-10-22 from merged M5
PR #19 at `e611076e23cab31efa578ee92f1514bc993e9f93`, on
`feat/lifecycle-m6-category-contracts`. M1–M5 are COMPLETE; M7 and Phases 3–6
remain NOT STARTED. This report does not grant exact contract approval,
production activation, new artwork approval, publication or merge authority.

## Scope and category accounting

The authoritative inventory has 22 selectors: 21 poster categories and Overlays.
Playlist already has its exact M3 v1.0.0 package; M6 adds 21 packages. The complete
inventory contains 278 closed design variants, including 18 overlay branches
with both standard/bigger outputs. No unusual or text-only selector is omitted.

See [complete coverage and package hashes](PHASE2_M6_CATEGORY_COVERAGE.md),
[implementation inventory](../bulk/contracts/categories/data/release-v1.json),
and [interfaces, policies and limits](../bulk/contracts/categories/README.md).
Every package is version 1.0.0. The canonical implementation inventory hash is
`926de31d1df4ee90e911c4e91df81ee3ca914f5179df784ff3d41e9b716ada2a`.
The original Playlist hash remains
`5047d834ecd3f8e5a0ed76ae24760b6947ae6b83e95198ce602e1715e445016b`.

M6 preserves all 14,079 historical identities: 9,957 posters (9,955 public and
two private Awards intermediates) and 4,122 overlays. This is 14,077 public
outputs, not 14,079 public images. Historical source assets are not extra output
records. No missing image is inferred from mismatched source counts.

## Policy and provenance

The approved D09 defaults remain unchanged. Playlist, Franchise, Genre,
Seasonal and Universe use WHITE_ONLY with individually scoped historical
source-preserving exceptions. Studio uses SOURCE_PRESERVING, including naturally
white/black/monochrome artwork. Applicable Chart/Country/Network/Streaming logos
require their actual white/colour pairs. Overlays preserve original source
branches independently of poster wash. Other categories retain their measured
icon, text, era, Awards, separator, video-format and special composition rules.

The metadata compiler captures actual protected raw style, font identity/hash,
caption mappings/case, geometry, captured fitting, effects, backgrounds,
encoding and transformation provenance. It does not implement a new renderer
or reduce the library to one generic template. Captured sizes are not automatic
shrink permissions. Contributors cannot insert arbitrary composer, profile,
variant, font, wash, contract or approval fields.

Each category's `data/rules/<selector>-v1.json` contains the complete exact member
and exception mapping: source spelling/SHA, stable identity, complete M2 record
SHA, effective-definition/job context SHA, required companions, exception codes
and original evidence hashes. The 56 accepted source-preserving historical uses
and 17 accepted alpha/background assets covering 41 uses retain their exact
scope. Changed material context cannot reuse their acceptance. Unchanged assets
receive no new alpha warnings, cleanup, image decoding or regeneration.

M1 canonical documents/schemas and immutable pins are reused. The complete
implementation inventory is deliberately separate from the unchanged M1
approval registry: the review registry has **zero entries**. All 22 exact
contract approvals, including Playlist, remain missing. Implementation,
compatibility, contract approval, activation, artwork approval and publication
are separate states; neither this PR nor a future merge manufactures approval.

## M1–M5 integration

The new adapter replays actual M5/Package E final jobs and checks every selected
effective definition. Nested overrides, inherited profiles, registered generator
children, raw values that normalize to a default and post-planning resealing
cannot bypass the chosen design. Controlled typed assignments preserve stable
IDs and exact mappings independently of display names. Paired outputs and both
overlay sizes must be complete and nonduplicate; source swaps and case/Unicode
collisions fail closed. Overlay validation uses its existing separate planner.

Existing M1 authority and M4 PNG/white-wash/review/storage remain unchanged.
M6 effective reports retain M5's current-job guard shape for typed M4 review
binding. No separate approval database, source-processing algorithm or renderer
is introduced. New intake remains ineligible for artwork/publication authority.

The reporting graph adds per-output material rule projections to M5's immutable
dependency model. Full package hashes are audit provenance; other items'
aggregate approval/colour/measurement containers do not become shared material
dependencies. Metadata-only or independent-variant revisions therefore cannot
force unrelated artwork invalidation. Actual rule changes require a complete
impact assessment and separate exact approval/adoption, never an automatic
regeneration. The original graph and worker/remote receipts remain unchanged.

The only existing test infrastructure edits share one freshly guarded immutable
M2/M5 context across historical tests. All original source/receipt checks and
the independent M5 dependency oracle are retained. No existing M1–M5 production
behavior is changed to make M6 pass. Batch physical source verification retains
exact case/ledger, collision, link and byte-hash checks, with directory-stability
checks around its temporary name index.

## Historical compatibility and validation

The complete read-only audit and final-head Windows/Linux CI are **pending in
this draft**. Compatibility is not claimed from the compiler's membership
counts. The full evidence will record every category/variant, accepted exception,
receipt count, unresolved interpretation, incompatibility and performance cost.

Focused validation so far: 529 category/effective-job tests pass; 22 additional
exact-authority checks pass; batch source tests pass (six passed, one Windows
symlink privilege skip). Existing renderer/font tests: 120 passed. Existing
Phase 2 tests: 35 passed. Historical baseline verification passes and the frozen
effective-job check validates 9,958 entries. The complete regression run and
read-only audit are still running; these are not substituted for final CI.

## Explicit remaining boundaries

There are no new unresolved D09 business decisions. Exact contract-hash approval
and production activation remain deliberately separate, ungranted decisions.
M4's complete new poster composition evidence is still absent: logo-only
previews cannot approve a new poster or new source-preserving poster exception.
M6 preserves the accepted historical exceptions and blocks pending/forged/replayed
new exceptions; it does not weaken M4 to manufacture a positive approval test.
An end-to-end approved **new** poster exception remains an explicit integration
gap, requiring separately authorized complete composition evidence. Numeric
logo-comparison auto-approval thresholds remain uncalibrated; no values are
invented. These limits do not authorize starting M7 or later lifecycle phases.

No production definitions, fonts, logos, translations, renderer, publication
logic/workflows or Default-Images files changed. No production image was
generated, no Timeline Order pilot poster was added, and no remote artwork
write, enforcement activation, lifecycle operation or merge occurred.
