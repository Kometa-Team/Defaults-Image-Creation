# English library synchronization tooling

These commands inventory and compare existing Package E outputs. They do not
publish artwork, record approvals, merge PRs, install workflows, or select the
production generator. Use Python 3.13 with `requirements-bulk.txt`; the established
local environment is `config/package-e/dependency-trial/venv/Scripts/python.exe`.

```powershell
$python = 'config/package-e/dependency-trial/venv/Scripts/python.exe'
$root = 'config/library-sync-20261018'
& $python -m create_defaults.bulk.e_validation baseline --root "$root/catalog"
& $python -m create_defaults.bulk.library_sync snapshot --root $root
& $python -m create_defaults.bulk.library_sync inventory --root $root --kind english --output config/package-e/full-en-final/output --catalog "$root/catalog" --local-published C:/Users/bullmoose20/Default-Images --workers 2
& $python -m create_defaults.bulk.library_sync inventory --root $root --kind overlays --output config/package-e/overlays-full-corrected/output --local-published C:/Users/bullmoose20/Default-Images --workers 2
& $python -m create_defaults.bulk.library_review fonts --root $root
& $python -m create_defaults.bulk.library_review calibrate --root $root --output config/package-e/full-en-final/output --local-published C:/Users/bullmoose20/Default-Images
& $python -m create_defaults.bulk.library_review calibrate-overlays --root $root
& $python -m create_defaults.bulk.library_review plan --root $root --inventory "$root/english-inventory.json"
& $python -m create_defaults.bulk.library_review plan --root $root --inventory "$root/overlays-inventory.json"
& $python -m create_defaults.bulk.library_report --root $root
```

Supply the actual checkout path on your machine. The checkout is read-only and
its bytes are reused only after checking the exact blob identity in the freshly
fetched production tree. Missing/different blobs are downloaded by pinned commit,
with a 20 MB per-file bound. Canary bytes are fetched independently of the old
checkout. Git SHA-1 establishes the tree-to-blob binding; candidate and published
SHA-256 are computed from actual file bytes and retained separately.

The snapshot uses the existing GET-only inventory and verifies merged PR #198
and production ancestry. Refresh it before a subsequent rollout; a stored
snapshot is a dated comparison baseline, not an assertion of live HEAD.

The Package E compressed ledger, payload, complete manifest, receipts, rendering
dependencies and assets are checked. English outputs must match fresh preflight
identities. The one accepted public destination case correction is applied from
the additive canary acceptance record, retaining its old identity. Other drift
fails closed. Overlay planning is checked against a fresh existing overlay plan.

The comparator uses unaligned decoded RGB stripes, channel MAE, percentile and
changed-pixel distributions, conservative text/logo/background regions, full-size
edge error, and explicitly named global luminance SSIM. Transparent artwork is
compared over black and white, with alpha and coverage diagnostics retained.
It does not certify clipping, infer fonts from raster pixels, or perform OCR.
Font/layout provenance and existing preflight diagnostics remain review gates.
Tagged ICC comparisons require specific colorspace review; identical raw RGB
values alone cannot establish renderer equivalence for tagged artwork.

SQLite caches measured comparisons by both SHA-256 hashes, parameters and visual
algorithm source identity. A rerun rehashes candidates and inputs before reuse.
Each completed comparison is checkpointed. The default comparison concurrency is
two, with an explicit four-worker option; per-image comparisons are bounded to
24 million pixels. The default time
budget is three hours after setup. A `STOP` file stops new comparisons and records
remaining destinations as blocked. Remove only a STOP file you intentionally
created, then rerun the same command to resume. Prior comparison caches and
historical Package E evidence are retained.

Results include `*-inventory.json`, complete replacement inventories, proposed
approval-group memberships and representative `*-review/review.html` galleries.
Full-resolution links may point into the read-only local checkout; preview images
are local to the gallery. Font matrices contain every member and deterministic
samples. Replacement impact follows the existing generated-input dependency
graph, including changed fonts inside derived artwork whose own caption font
is unchanged. Calibration records separately identify seven accepted historical
positive pairs, current category samples, and eight deliberately defective
controls. Unchanged-font positives and intentional direct/inherited font changes
are reported separately. Passing a proposed screen grants no approval.

## Planning from explicit maintainer decisions

Without `--approvals`, no new decisions are inferred. The 64 original overlay
decisions can enter the plan only when their image, render, validation, policy
and historical published comparison identities still match. Their old and current
worker receipts are recorded separately. All other unapproved binary-different
images remain withheld in the replacement inventory. An
externally supplied approval receipt must contain:

- `reviewer`, `decision: approved`, `scope`, `inventory_sha256`, exact `baseline`,
  `policy_sha256`, and an envelope `sha256` over canonical JSON excluding itself.
- Complete `members`, each with `destination`, `candidate_sha256`,
  `published_sha256`, `context_sha256`, and `membership_sha256` over that list.
- For `renderer_equivalent`, explicit `policy_approved: true`. Every member must
  pass the approved screen and have no font-change or unresolved layout warnings.
- For `font_layout_group` or `overlay_group`, an exact approved `group_policy`,
  `group_policy_sha256`, `policy_approved: true`, and explicit
  `accepted_layout_warnings`. Every member must pass those bounds. Unexpected
  differences and layout exceptions require `individual` approval.

The allowed attributed reviewers follow the existing five-user model. As with
the existing local Reviews service, a JSON hash establishes version binding, not
reviewer authentication. Supply only decisions actually made by maintainers;
this CLI intentionally has no approve command. The resulting manifest still
grants no remote-write or merge authority.

```powershell
& $python -m create_defaults.bulk.library_review plan --root $root --inventory "$root/english-inventory.json" --approvals path/to/actual-maintainer-decision.json --max-files 300 --max-bytes 209715200
```

Only exact SHA-256 matches are skipped. Every eligible binary-different image,
including renderer-equivalent artwork, enters the exact upload manifest. No
encoding or optimization occurs during transport.

## Offline Git exercise

```powershell
& $python -m create_defaults.bulk.library_transport --plan "$root/english-git-batch-plan.json" --root config/library-offline-exercise --base-repository path/to/local-test-baseline
```

Use a local baseline repository whose HEAD equals the manifest baseline. The
exercise root must be new or already owned by that exact plan. All local commits
and non-forced pushes go to an isolated bare repository inside that root. No
network remote is accepted or configured. Existing baseline repositories remain
read-only. This command does not stage a Default-Images branch or PR.

The exercise verifies exact changed paths and SHA-256 bytes in every commit and
offline remote, measures incremental packs and enforces their byte cap, rejects
changed baselines/artifacts and unrelated worktree edits,
and recovers after a commit or successful push with a missing journal update.
Transport batches are independent of visual groups and publication PRs.

An actual-artifact benchmark can be created from a nonempty approved manifest:

```powershell
& $python -m create_defaults.bulk.library_exercise --manifest "$root/overlays-publication-manifest.json" --inventory "$root/overlays-reconciled-inventory.json" --root config/library-offline-benchmark-new
```

It copies verified prior image bytes into a synthetic baseline and rehearses the
approved replacements, including both ambiguous interruption cases. Its baseline
is explicitly distinct from production, and its results measure local transport.
The final report preserves the original analysis inventory, then reconciles
historical layout warnings independently from observed layout changes. It records
all remaining mismatches, missing destinations and verification gaps.

After any separately authorized real publication, use
`library_publication.verify_published` with actual downloaded remote bytes and
the refreshed production identity. A successful transport response is not remote
SHA-256 verification. Rerun the entire inventory to reconcile all remaining
mismatches and missing/unverified files.

## Unsigned first-wave preparation

The 9,785 renderer screen passes include 4,179 candidates with recorded layout
warnings. Screen passage does not resolve those warnings or establish unchanged
layout. The remaining 5,606 diagnostic-free members still need exact policy and
manifest approval. Do not silently reduce the requested wave or approve warnings.

Use a new preparation root, a fresh GET-only snapshot, a fresh `e_validation
baseline`, and a blob-filtered Git fetch into that root's `baseline.git`. Then run:

```powershell
& $python -m create_defaults.bulk.library_first_wave --root config/library-first-wave-20261018 --analysis config/library-sync-20261018 --output config/package-e/full-en-final/output
```

This rehashes every proposed candidate and comparison, checks current source,
native runtime, fonts, receipts, layout diagnostics and fetched remote identities,
and writes an unsigned decision request, exact candidate membership, exclusions,
warning inventory, non-executable transport proposal and unstarted upload journal.
Existing package JSON cannot be replaced with different content; use a new root
for changed evidence. Its hashes bind content and do not authenticate a reviewer.
It records no maintainer approval and makes no remote write. The existing local
transport rejects its proposal kind. Only a separately attributed exact approval
may produce an executable publication manifest after all diagnostics are resolved.

For the separately requested clean population, use a new root with fresh snapshot,
Git fetch and catalog preflight, then run `library_first_wave --population A` with
the same `--root`, `--analysis` and `--output` arguments. Counts are computed from
the verified membership; no historical count is padded. `group-a-population.json`
and `group-b-population.json` are disjoint sealed memberships. The Group A request
binds the exact proposed policy and complete candidate/context hashes and leaves
the reviewer and decision pending. It rechecks all Group A candidates and rejects
any current warning/error, source, receipt, font dependency or baseline drift.

Run `library_warnings --root <new-root> --analysis <analysis-root>` independently
for Group B. It rehashes both images, measures white caption cores in original
coordinates, compares row bands and bounds, and records historical typography
provenance. Foreground contamination and geometry differences remain withheld.
Its numerical geometry bounds are diagnostic proposals, not artwork approvals,
OCR, or readability certification. The SQLite cache resumes measured comparisons;
the report and worst-case galleries preserve every warning and exact membership.

After an explicit exact-hash policy/member decision, `library_stage --root
<final-staging-root>` consumes the externally attributed approval receipt, derived
publication manifest/plan and sealed draft-operation authorization. It has a fixed
Default-Images remote and dedicated Group A or policy-bound Group B branches; it
never pushes master or merges. Group B additionally requires matching population
attribution, the exact approved warning-policy content hash, its preserved visual
review receipt binding, and a branch suffix matching the approved manifest hash.
This does not grant warning acceptance or extend an approved population. A
metadata-only base and skipped index entries preserve untouched files.
Each batch checks the complete raw Git diff and exact stored bytes, measures and
caps its incremental pack, uses a normal push, reconciles ambiguous outcomes and
streams pinned remote image bytes for SHA-256/Git-blob verification. A single
owned journal resumes known prefixes. Synthetic test approvals cannot use the
network remote. Complete remote tree comparison covers all planned files without
depending on the PR files endpoint's pagination cap. PR creation remains a separate
explicitly authorized draft-only operation after all batches verify.

Individually accepted font changes and visual exceptions use a dedicated
`migration/english-python-exceptions-<manifest-prefix>` branch. The transport
requires every exact original visual-review decision and a version-bound bridge
to the current publication context. Candidate/published hashes and original
context must match, and unchanged material review context must be verified.
Exception classes remain `font_changed` or `unexpected_difference`; these are
not automatically accepted by the renderer-equivalence policy. Staging still
requires the maintainer's operation authorization and never merges or updates
master directly.
