# M6 opt-in category contracts

This package implements the remaining category selectors from the approved
D01–D09 architecture. It is not imported by production generation, translation,
workers or publication. No contract is activated, no new approval is created,
and no historical image or receipt is rewritten. M7 is not implemented.

## Inventory and immutable selection

The authoritative `config.CATEGORIES` contains **22 selectors: 21 poster
categories plus Overlays**. Playlist already has its M3 package. M6 adds 21
packages and accounts for all 22, with **278 closed design variants**. The
Overlays package has 18 branch variants, each requiring standard and bigger.

[`data/release-v1.json`](data/release-v1.json) is the complete hash-pinned
**implementation inventory**, not an approved registry. Select its exact
canonical SHA-256 through `Implementation.load(expected_sha256=...)`; the
release constant in `release.py` identifies this review candidate. Every
contract and membership sidecar is separately pinned. Playlist refers directly
to the original M3 file, whose canonical SHA remains
`5047d834ecd3f8e5a0ed76ae24760b6947ae6b83e95198ce602e1715e445016b`.

The unchanged M1 registry requires real attributed approvals. Consequently
[`data/review-registry-v1.json`](data/review-registry-v1.json) deliberately has
zero entries. An implementation inventory cannot be substituted for that
registry. `authorize()` re-enters unchanged M1 `RegistrySnapshot.load/select`
through M5 `Authority`, including external maintainer attribution. Public JSON,
an `approved` flag, a reviewer name or an unkeyed checksum cannot supply it.
All 22 exact contract approvals are currently missing, including Playlist.

## Contract representation

Each package is an unchanged strict M1 `Contract` v1 document with semantic
version 1.0.0, maintainer ownership/provenance, exact naming rules, a closed
variant set and explicit contributor fields. New additive `Rules` and `Release`
documents use M1's bounded parser, strict bundled JSON Schemas, canonical JSON,
immutable bytes and Package E hashes. They introduce no persistence framework.

`compiler.py` is a metadata compiler from exact M2 records and approved design
documents. It never draws an image. Closed design cohorts distinguish protected
raw composer values, caption modes/templates/case, captured fitting bounds,
presentation roles and source classes. Exact historical per-item values remain
pinned, rather than replacing varied geometry/typography with one template.

Each sidecar records:

* Exact contract, M2 registry, source-main and architecture/matrix/exception pins.
* Protected raw style, caption content types and translation evidence, captured
  layout shape, source branches, required presentations and counterpart variants.
* Every stable output identity, exact source spelling/SHA, complete M2 record
  SHA, full effective-definition/job context SHA, required companions and
  identity-scoped historical exception evidence.

Captured size ranges are evidence, not permission to shrink a new caption.
Caption content types are closed. Unregistered new types or fitting evidence
require an explicit contract/design decision; YAML cannot silently extend them.
Background proposals stay disabled except for the original M3 Playlist opt-in.
Assignments and destinations remain controlled operator inputs, independent of
display names or contributor filename requests.

## Confirmed policies and historical uses

Playlist, Franchise, Genre, Seasonal and Universe retain WHITE_ONLY defaults.
Their 56 accepted source-preserving historical uses are exact pinned exceptions,
not extra contributor-selectable colour styles. Selecting the same cohort for
a new item still requires white treatment. A changed caption, background, path,
dependency, source or effective job cannot borrow the old exception.

Studio and VideoFormat preserve source colours, including intrinsically white,
black or monochrome artwork. Studio's two transparent text placeholders are
NOT APPLICABLE, rather than invented logo designs. Applicable Chart, Country,
Network and Streaming logos require their existing white/colour pairs. Stored
white PNGs and existing wash-derived whites keep their distinct semantics; a
controlled derived-white route must use the same master as its colour partner.
No geometry match or branding approval is inferred from filenames.

Text-only language/Based designs, Year/Decade families, icons, Awards and
Separators retain their measured rules. Placeholder and generated-composition
variants are explicit NOT APPLICABLE/SPECIAL designs, not inferred logo intake.
The six Country and four Network text counterparts retain their already present
paired destinations without being misclassified as paired logo assets.

Overlays retain all 18 existing white/colour/other source branches, their
source-preserving transformation and both 285×85/440×100 boxes. Poster wash
cannot enter their parameters. No extra branch, group, source or overlay is
inferred from a poster addition.

The 17 accepted alpha/background assets, covering 41 existing uses, remain normal
accepted artwork. They receive no cleanup, PNG reinspection, new warning or
regeneration. Full record/context pins scope every historical exception; changed
source bytes require M4 intake, not an exemption flag.

## Effective-definition and approval integration

`validate_selection()` uses M5's actual strict loader resolution and replays
Package E's planner. Every serialized final job must match that replay before
the category check. All jobs require controlled typed `Assignment` inputs;
unselected parents are not ignored, and missing parent bytes block planning.
Definitions, profiles, inheritance, generator expansion, nested overrides and
language application therefore cannot replace protected values after validation.

`check_job()` checks raw and normalized composer values, protected style,
selected caption/provenance, fitting evidence, font hash, source/branch,
presentation and stable mappings. `check_membership()` requires complete,
nonduplicate white/colour or standard/bigger sets. Case/Unicode namespace
checks preserve literal historical mappings and reject equivalent collisions.
`validate_overlays()` separately replays the existing overlay planner; poster
planning never manufactures overlay output membership.

Individual validation reports retain the M5 effective-validation guard shape.
Existing `expanded.validation.require_current` and typed
`expanded.review.consume/require_current/attach` can bind them to M4's isolated
`LogoArchive`; no second approval database or alternate decision record exists.
M4 remains responsible for real PNG integrity/alpha, existing white-wash,
comparison calibration, owned preview receipts and externally attributed
submitter/maintainer decisions. Fixture validation is explicitly unapproved.

**Remaining intake limitation:** M4's poster previews are logo-only and cannot
receive final approval of a complete new poster composition. M6 does not turn
these into approved new source-preserving exceptions. Pending/forged/replayed
requests remain blocked; existing exact historical exceptions remain accepted.
An end-to-end approved *new* poster exception still needs complete composition
evidence and the later separately authorized integration. No numeric logo-match
threshold or publication approval is invented to bridge this gap.

## Dependency and compatibility evidence

`dependencies.bind()` returns a new M5 `Snapshot`, preserving the original graph,
receipt references and render fingerprints. Exact package hashes are audit
provenance nodes. Per-output material rule hashes exclude other items' aggregate
colour/measurement/approval containers, so a metadata-only or independent
variant addition does not itself invalidate unrelated artwork. Existing actual
caption, fit, background, source, transformation and dependency context remains
in the output closure. Required companions are retained independently of
changed-pixel impact.

`compare_implementations()` compares actual material projections using M5's
existing graph comparison and reports the separate package approval/adoption
requirement. It grants neither adoption nor publication. A proposed category
style change needs its complete affected-output assessment and maintainer
decision; a package checksum alone cannot authorize a bulk regeneration.

The read-only audit covers all 14,079 exact M2 records against the unchanged M5
historical graph, fresh physical inputs and final expanded definitions. It
distinguishes compatible uses, accepted historical exceptions, intentionally
missing contract approvals, unresolved interpretation and incompatibility.
Two private Awards intermediates retain owned evidence without public receipts;
all 14,077 public records retain their original published response references.

Run explicitly, from the repository root:

```powershell
python -m create_defaults.bulk.contracts.categories `
  --release-sha256 926de31d1df4ee90e911c4e91df81ee3ca914f5179df784ff3d41e9b716ada2a `
  --report config/m6-review/audit.json
```

Without `--object-root`, this reuses M2's fresh guarded discovery. An explicitly
selected immutable M2 object cache may be supplied to avoid rediscovery; every
exact object name, typed record/hash, registry/schema pin, current source and
physical input is still checked. The cache reader never opens a database. One
exact-name directory index avoids repeated full-directory scans. Reports use
M5's isolated immutable writer, outside assets/state/output. `--category` selects
a category audit from that same fully pinned immutable record population.

An existing immutable M5 graph can additionally be selected with both
`--dependency-snapshot` and `--dependency-sha256`. It must match the exact
accepted historical M5 graph. Current code/catalog pins, every actual physical
input and every selected effective definition are still checked; this only
avoids rebuilding already pinned dependency metadata. CI builds the graph
fresh and retains the independent M5 impact oracle.

Tests cover all 278 closed variants, all 22 selectors, actual M5/planner replay,
pair completeness, source/context swaps, protected fields, literal names,
historical exceptions, forged approvals, dependency scope and the complete
inventory. M2/M5/M6 tests share one freshly verified immutable context per session;
all original receipt/source checks and the independent M5 impact oracle remain.
The large graph cache is released after its last historical test consumer;
decoded category indexes are module-scoped. This preserves the existing worker
parent-memory budget instead of retaining audit data through unrelated tests.
This is test-only reuse, not a production cache or activation mechanism.
