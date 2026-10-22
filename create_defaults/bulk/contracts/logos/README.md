# M4 isolated logo validation and review

This opt-in package implements the authorized D09 foundations. No production
entrypoint imports it. It changes no renderer, definitions, historical assets,
old receipts, publication destinations or authentication service. Start from
`main` at `22ab7c2eb73ca4199ec1f4b68be4290470f47663` (merged M3 PR #17).

## Contract and authority selection

`Selection.approved` uses unchanged M1 `RegistrySnapshot.load/select`, requiring
an externally selected registry hash, exact package/version/hash/variant and
externally attributed `TrustedDecision` objects. Neither submitted JSON nor
stored reviewer strings populate this trust map. M4 does not approve the M3
Playlist package: its canonical SHA remains
`5047d834ecd3f8e5a0ed76ae24760b6947ae6b83e95198ce602e1715e445016b`.
Its empty M3 review registry still cannot select an operational contract.

`Selection.fixture` is an explicit controlled Python test/evidence path. Its
`fixture_only` marker is bound throughout the context and always withholds
operational eligibility. It is not an input field offered to contributors.
The [overlay fixture](overlay-fixture-v1.json) is synthetic, not a new approved
category contract. No M6 contracts are authored.

The selected contract supplies actual requirements. Confirmed WHITE_ONLY
defaults are checked for Playlist/Franchise/Genre/Seasonal/Universe; Studio is
SOURCE_PRESERVING; applicable Chart/Country/Network/Streaming designs are
BOTH_REQUIRED. Other categories are not assigned requirements from a universal
table: an explicit contract must identify a supported logo design. SPECIAL or
text-only variants cannot be used to invent logo additions. Overlays always
preserve their selected original branch and explicitly track standard/bigger.

## Source inspection and historical boundary

`inspect_png` checks actual PNG signature regardless of filename extension,
chunk extents/CRCs/IHDR/IEND, no trailing data/animation, successful verification
and decoding, supported modes, nonempty alpha support and resource limits.
RGBA, palette transparency and LA are supported; RGB/L/1 without genuine
transparency remain policy-blocked unless exactly excepted. No format repair,
automatic JPEG conversion or background removal exists.

Limits are parser/memory safety budgets, **not visual acceptance thresholds**:
16 MiB encoded bytes, 16,777,216 pixels, 8,192 pixels per edge, 65,536 chunks.
One decoded RGBA surface is at most 64 MiB; processing may hold several bounded
surfaces, not just one. Analysis is capped at 256 × 256 (65,536 cells).
Pillow decompression warnings/errors also fail closed. Unsupported 16-bit modes
are rejected instead of silently reducing precision.

The report retains original SHA/name/mode/dimensions, alpha distribution,
foreground bounds, border contact, possible rectangular mattes, color-profile
identity, soft-edge RGB observations and explicit quality-review status. One
clear pixel in an opaque rectangular field does not prove a clean background.
No fully clear pixels or rectangular alpha-background evidence keeps default
transparency blocked. An intentional-background request permits safe previews,
**not acceptance**; integrity/resource/empty-image failures cannot be excepted.
Clipping, complete lettering, brand authenticity, halos and intended-size
readability are measured/reviewed, not falsely certified by Pillow statistics.

`historical.preserve_existing` is a separate exact-use path: full pinned M2
mapping/registry → existing stable item → exact source path/SHA → actual bytes.
All **17 accepted historical alpha assets / 41 uses** return normal acceptance
without image decoding, diagnostics, cleanup, generation or new review. A new
use or replacement bytes must enter new-source intake. No `grandfathered` flag
can be supplied in contributor metadata.

## Existing white-wash adapter

The approved wash is three inline statements in `render_poster`; there is no
public wash helper. `wash.py` verifies the exact M3 source-text pin
`ff748c9c8422a46f662f36a094a3ef523d2f9c4c23d622729f18c1f1894e0717`,
extracts only that AST body and executes those original statements on a cloned
validated RGBA image in a restricted namespace. It neither invokes the complete
poster renderer nor independently reimplements the operation. Source drift or
an unexpected operation shape fails closed. No submitted Python or configurable
code path is compiled. Tests prove original immutability and byte-identical alpha.

Provenance binds original source hash, renderer/body identity, transform version
and parameters, original alpha report, derived artifact hash, selected package,
variant, background, geometry, runtime and complete required membership.
Overlay contexts identify the existing overlay transform instead; poster wash
is never applied to an overlay because it shares a logo with a poster.

## Preview guarantees and gaps

`prepare` creates immutable `Prepared` evidence without writing production
outputs. Original files are never modified. PNG previews have private hash
names and no official destination mapping.

* **Logo-only:** white/default and original/requested treatments under the same
  source context. SOURCE_PRESERVING exceptions retain both views. BOTH_REQUIRED
  tracks both presentations, with a separate white source optional. These views
  do not include final poster captions, font fit, backgrounds or category layout.
  They cannot pass final approval of a complete poster addition in M4.
* **Complete overlay:** the existing unmodified `overlays.render` performs the
  selected trim/fit/sRGB/PNG operation for both standard and bigger boxes. Each
  selected source branch stays source-preserving. Other branches/groups are not
  invented. This proves the selected isolated overlay composition only, not
  general production expanded-definition compatibility or publication readiness.

M1 `PreviewManifest` references distinctly typed **isolated-logo-preview receipts**,
not fictional production-worker receipts. These bind member/context/source,
runtime/transform and actual artifact bytes. `verify` rechecks current exact
source bytes and reproduces the small owned task to reject even fully resealed
fake previews. Blocked-default panels retain their blocked label after an
intentional-background exception is accepted; the exception is separate evidence.
Full poster composition and general production worker integration remain M5/M6
gaps; M4 does not weaken those gates to manufacture completeness.

## Comparison and calibration

`compare` preserves original geometry evidence and aligns analysis copies only
by translation/uniform scaling of visible bounds. It never mirrors, rotates,
stretches axes independently, repairs cutouts or changes rendering inputs.
Reports contain soft-alpha absolute difference, intersection/union, alpha-level
support, both directed four-neighbor boundary distances, eight-neighbor parts,
four-neighbor internal cutouts, native component signatures and RGB observations
excluding fully transparent pixels. Expected RGB differences are not a silhouette
mismatch. The 1/128/255 alpha probes and 64/128 experiments are measurements,
**not approved acceptance tolerances**.

There is **no automatic MATCH**. Exact native binary component/cutout additions
or deletions on the same canvas can flag MISMATCH; other evidence remains REVIEW
REQUIRED. Different dimensions, resolution, padding, resampling or soft alpha
cannot become MISMATCH merely because component counts differ. Ambiguous and
structurally blocked pairs require explicit resolution; a brand-lockup exception
never changes a category default or grants publication permission.

The [sealed corpus](corpus-v1.json) has **60 construction-labeled synthetic pairs**
in six families, split 3/3 without family leakage. It includes resolution/AA/
padding, missing letters, altered symbols, proportions, cutouts, clipping and
different lockups. Labels are synthetic ground truth, **not maintainer approval
of real logos or a numeric policy**.

| Split | Equivalent | Negative/lockup | Hard mismatch flags | Negative manual review | Positive manual review | False matches / mismatches |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Calibration | 12 | 18 | 9 | 9 | 12 | 0 / 0 |
| Held out | 12 | 18 | 9 | 9 | 12 | 0 / 0 |

Automatic MATCH coverage is **0%**. Zero observed errors do not establish a
production classifier: all positives and half the negatives still need review.
[Raw measurements](calibration-v1.json) are reproducible; [12 grid-sensitivity
probes](stability-v1.json) at 64/128 produced zero verdict changes while retaining
the measured alpha differences. The verdicts intentionally do not rely on a
tuned numeric tolerance. Real maintainer-labeled families, additional stability/
resource measurements, an exact sealed candidate policy, untouched held-out
evaluation and explicit maintainer approval are required before enabling MATCH.
Do not retune on held-out examples or treat historical accepted art as a new
cleanup corpus.

## Two-stage decisions and persistence

M1 `ExceptionRequest`, `PreviewManifest`, `SubmitterConfirmation` and
`ExceptionDecision` are reused unchanged. The spec binds original/optional-white
hashes and exact names, category/item/package/registry/variant, effective rules,
exception types/reason, background/geometry, transform/runtime, comparison policy,
default/requested panels, all required outputs and optional expiry. Permitted
departures are SOURCE_PRESERVING, intentional background and different brand
lockup, restricted to that exact scope. No contributor wash toggle exists.

`LogoArchive` composes `ContractStore` and the existing Package E transaction/
event API. A versioned `contract_logo_*` sidecar appends immutable snapshots with
CAS, blobs/artifacts before pointers, atomic events, idempotent retries and no
automatic corruption repair. Existing production databases/receipts are untouched.
Typed evidence and binary previews live only in the explicitly isolated root.

`PREVIEWS_READY → SUBMITTER_CONFIRMED → MAINTAINER_APPROVED` requires two real,
externally attributed exact decisions. Rejection and pending withdrawal are
explicit alternatives. New material revisions reset decisions. Changed sources,
derived bytes, context, selected contract, implementation, membership or expiry
invalidate affected evidence; unrelated reviews remain valid.

Stage 1 checks an external `SubmitterAttribution` against the exact M1 confirmation.
Stage 2 checks M1 `TrustedDecision`, its existing maintainer allowlist, that same
confirmed preview/membership and a distinct actor. No same-person role exception
is enabled. Restart requires fresh externally supplied attribution maps; stored
reviewer strings and evidence checksums are never authentication. This follows
M1's controlled-operator trust boundary and does **not** implement a new login
service. An actual authenticated deployment/decision capture adapter is still
required outside this isolated foundation. `status` only formats an already
verified result; callers must use `LogoArchive.load` before trusting any phase.

Source validation, preview completeness, human logo/design decisions, M5 contract
compatibility, artifact review, staging and merge remain separate. Even complete
fixture approval has `operational_addition_eligible: false`, no staging authority
and no merge authority. Publication rejects all these evidence kinds.

## Reproduce

```sh
python -m pytest create_defaults/bulk/tests/test_logo_workflow.py -q -p no:cacheprovider
python -m create_defaults.bulk.contracts.logos --evidence-root config/lifecycle-m4-evidence
```

The second command creates only explicitly synthetic/private galleries and pending
fixture reviews in a guarded M1 state root. It records no actual submitter or
maintainer approval. Existing different evidence is not overwritten as a new
approval; choose a fresh root after material implementation changes.
