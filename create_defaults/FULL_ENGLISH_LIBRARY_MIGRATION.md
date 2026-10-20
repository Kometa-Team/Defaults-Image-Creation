# Kometa Default Posters — Full English Library Migration, Visual Validation and Batched GitHub Publishing

## Project context

Repository: `Kometa-Team/Defaults-Image-Creation`

Existing migration: Draft PR #12, branch `feat/default-posters-python-generator`.

Production image repository: `Kometa-Team/Default-Images`, branch `master`.

The Python rearchitecture has already progressed through Packages A–E. We have validated the English catalog, Python renderer, bulk workers, dependency handling, output manifests, caching, typography, font replacements, overlay transformations and review/approval infrastructure.

The first seven-image English canary was successfully published through Default-Images PR #198.

Production merge commit:

`22c5ff5225fab7dce972f369bb16bf17a7abe8e0`

The seven canary images are already approved and published. Preserve those accepted image identities and do not regenerate or republish them unless a genuinely changed source/version context makes it necessary and is separately reviewed.

**We now need to synchronize the complete published English Default Posters library with the validated, deterministic Python/Pillow outputs, replacing legacy ImageMagick/PowerShell bytes whenever the approved Python output differs.**

Visual equivalence permits replacement under a valid, approved policy; it is never a reason to skip a binary-different artifact. Only an exact SHA-256 match counts as synchronized.

For example, if an existing ImageMagick JPEG is 700 KB and the Python/Pillow JPEG is 650 KB, and the candidate passes the approved visual-tolerance policy and any required font/layout review, include the exact 650 KB Python JPEG in the publication manifest. Publish it once the separate remote-write and publication authorizations are granted.

This is a full library synchronization, not merely a visual-equivalence cleanup. This correction does not itself approve a tolerance policy, artwork, remote writes, publication merges or production cutover.

This is primarily a catalog reconciliation, visual-validation and reliable publication exercise. It is not another renderer rewrite.

## 1. Critical distinction: validation, approval, transport and publication

Do not interpret batching as a request to create hundreds of separate PRs or demand individual approval for every 100 images.

We need four separate concepts:

**A. Generation and technical validation**

Generate or reuse the entire validated English catalog, including dependency-aware outputs and their exact source/rendering identities.

**B. Visual-equivalence validation and approval**

Determine whether the candidate is visually equivalent to the existing published image, affected by an intentionally replaced font, meaningfully changed in layout, or unexpectedly different.

**C. GitHub transport batching**

Break the upload of large numbers of JPEGs or PNGs into reliable technical batches to avoid push failures, excessive request volume, timeouts and recovery problems.

**D. Publication units**

Group approved changes into a small number of logical PRs or rollout groups.

These concepts must be designed and implemented independently.

A transport batch does not require another human approval if all its contents are already covered by a valid, explicit, version-bound acceptance policy.

A PR may contain multiple transport batches.

A logical publication group may cover many thousands of images, provided every included artifact is eligible under the approved policy and its exact manifest is verified.

## 2. Existing scope and baseline

The previous full English validation covered:

- 9,957 English generated outputs.
- 9,955 public English destinations.
- Two private intermediate outputs.

The private intermediates must never be published as public artwork.

The first seven published canary destinations are:

- `based/Book.jpg`
- `decade/2020.jpg`
- `franchise/Death in Paradise (2011).jpg`
- `genre/Action & Adventure.jpg`
- `genre/Splatter.jpg`
- `year/2020.jpg`
- `year/best/2020.jpg`

The font replacements and layout decisions made in the migration must remain intact.

Before implementing any new publication logic:

1. Read the current migration reports and validation runbooks.
2. Identify the exact existing English catalog and validated manifests.
3. Fetch the current `Default-Images/master` HEAD.
4. Confirm the seven-image canary merge exists.
5. Detect subsequent production changes instead of assuming the historical baseline is still current.
6. Record current source, renderer, fonts, assets, definitions, dependencies (including Pillow and encoding libraries/settings), validation policies and published repository identities.

Determine which of the 9,948 other public destinations need updating from actual SHA-256 comparisons and valid approval evidence; do not preselect or exclude them based on visual similarity.

Do not assume that every byte difference indicates a meaningful visual difference.

Do not assume a successful render grants visual approval.

## 3. Reuse existing generation infrastructure

Use the current Python implementation under `create_defaults/`, particularly its established rendering and bulk-generation components.

Reuse:

- The native Pillow poster renderer.
- Existing category definitions and generators.
- Translation handling, restricted to English for this migration.
- Font provenance and replacement policies.
- Planner and dependency expansion.
- Persistent multiprocessing workers.
- SQLite state, leases, checkpoints and resumable workloads.
- Content-addressed outputs and validation receipts.
- Source/policy/renderer identity tracking.
- Existing approvals and review evidence.
- Existing comparison tools where suitable.

Avoid inventing a parallel rendering engine, alternative job planner or unrelated publishing architecture.

Revalidate existing cached outputs and receipts against the current source and renderer identities.

If the exact accepted validated outputs are still present and all identities match, reuse them rather than rerendering everything.

If a necessary rerender is required because of changed code, fonts, dependencies, assets or missing/corrupt outputs, report the cause and invalidate the affected outputs appropriately.

Never silently reuse a stale candidate or approval.

## 4. Full English destination inventory

Build a fresh read-only inventory covering every public English destination.

For each candidate, retain:

- Logical poster ID and category.
- Exact canonical published destination.
- Candidate source/output path.
- Candidate SHA-256 and Git-compatible blob identity.
- Existing published SHA-256 and Git blob identity.
- Existing and proposed file dimensions.
- Source asset and dependency fingerprints.
- Current and historical font identity.
- Renderer and policy version.
- Layout/caption configuration.
- Technical validation status.
- Approval status.
- Difference metrics.
- Publication eligibility.
- Baseline repository commit/tree.

Prevent path collisions, case-only duplicates, unexpected deletions, and accidental publication of private intermediate outputs.

Classify every public destination into mutually understandable statuses such as:

- `exact_match` - candidate and published SHA-256 hashes are identical; skip publication.
- `renderer_equivalent` - hashes differ, but the candidate passes the approved renderer-equivalence policy in its current context; include it in the upload plan when all required approvals are valid.
- `font_changed`
- `layout_changed`
- `unexpected_difference`
- `missing_published`
- `blocked`

Keep difference classification, approval status, publication eligibility, transport status and remote verification as separate fields. A measured visual similarity under a proposed or unapproved policy is pending review; it cannot establish approved `renderer_equivalent` eligibility. Intentional font/layout changes retain their applicable review requirements even when numerical comparison metrics pass.

Also independently track whether it was already published through the canary. Do not let historical canary membership override current hash verification. Reuse the exact accepted canary artifacts when their identities remain valid; any current mismatch requires reconciliation and appropriate review, never an implicit exemption.

Return actual counts globally, by category and by font family.

Reconcile the total to the entire expected public catalog.

### Required synchronization decision sequence

1. Verify the exact candidate bytes and published bytes at the recorded baseline and compare their SHA-256 hashes. Git blob identities supplement this check; they do not replace it.
2. If both hashes match, classify the destination as `exact_match`, mark it synchronized and skip publication.
3. If hashes differ, evaluate technical validity, visual equivalence, font-change and layout-change approval requirements against current, version-bound evidence. A missing published image cannot be an exact match and follows the applicable new-file approval path.
4. If eligible under a valid, explicitly approved policy or appropriate artifact/group review, include the exact Python output in the publication manifest and upload plan, including every eligible `renderer_equivalent` file. Appearance, decoded-pixel equivalence and file-size similarity never suppress a required replacement.
5. If further review is required, withhold the candidate until approved. If blocked, do not publish it.
6. Perform remote staging and publication only under their separate explicit authorizations. Approval grouping, GitHub transport batching and publication PR grouping remain independent.
7. After authorized publication, retrieve the actual remote artifact bytes at the refreshed production commit and verify that their SHA-256 matches the approved Python output hash. A successful push, merge, Git blob check or visual comparison alone does not establish this result.
8. On subsequent runs with unchanged inputs, fonts, assets, renderer and encoding dependencies/settings, verify that the generated SHA-256 matches the published SHA-256 and skip it as `exact_match`. Investigate any failure of deterministic reproduction; do not silently bless a new hash or rerender accepted artifacts unnecessarily.

Never implement a shortcut that treats visually equivalent but binary-different images as already synchronized. Review requirements or blockers may explain an outstanding mismatch; they do not make it synchronized.

## 5. Understand Pillow versus ImageMagick differences

We expect file-size, compression and decoded-pixel differences between Pillow and ImageMagick.

These differences are not automatically visual problems. They still require replacement when SHA-256 differs and the exact candidate is eligible under valid approvals; visual equivalence does not waive byte synchronization.

The user expects many unchanged-layout outputs to be visually within roughly one or two pixels of the historical render. This is a hypothesis to measure, not a universal tolerance to assume.

Implement or extend the existing automated image-comparison capabilities to distinguish encoding variation from meaningful visual changes.

Include:

- Width/height and color-mode validation.
- Full decoded RGB comparison.
- Per-channel and combined mean absolute error.
- High-percentile absolute errors.
- Maximum pixel error.
- Proportion of changed pixels at useful thresholds.
- SSIM or an appropriate perceptual structural measure, where useful.
- Perceptual color difference where useful.
- Edge and geometry displacement analysis.
- Text-region comparison.
- Logo-region comparison.
- Background/gradient comparison.
- Clipping, overflow and unexpected transparency diagnostics.

Use bounded memory, streaming where practical, and deterministic outputs.

Distinguish these situations:

1. JPEG bytes differ, but decoded artwork is effectively equivalent.
2. Text or logo edges differ because of antialiasing.
3. The same artwork is shifted by one or two pixels.
4. A font substitution intentionally changes character shapes or line geometry.
5. Text wraps differently or moves enough to alter the intended composition.
6. The wrong font is used.
7. Text, logos or artwork are clipped.
8. Something is missing, substituted, corrupted or unexpectedly recolored.

Do not simply move or align the candidate over the original and declare it equivalent.

Alignment-aware diagnostics are acceptable, but preserve and evaluate the original unaligned geometry.

### Establish a calibrated tolerance policy

Use existing approved renderer comparison examples and representative current images.

Include known-valid examples and deliberately altered negative controls.

Negative controls must cover:

- Wrong font.
- Changed text.
- Missing logo.
- Clipped caption.
- Meaningful positional shift.
- Incorrect color or gradient.
- Missing or corrupted graphic.
- Incorrect aspect ratio.

Measure false-positive and false-negative behavior.

Propose explicit thresholds for relevant regions and difference types, and document their justification.

Use an immutable/versioned tolerance policy.

**Do not start automatically approving or publishing images under an unapproved tolerance policy.**

The first deliverable is a proposed policy and evidence for maintainer review.

## 6. Focus review primarily on font substitutions

Font replacement is a major reason we need this migration.

Use actual font provenance, category definitions and renderer fingerprints to identify affected images.

Produce a font-impact matrix showing:

- Original font.
- Replacement font.
- Font source/license.
- Applicable categories and templates.
- Number of affected public destinations.
- Rendered label characteristics.
- Whether the change is intentional and approved at the font-selection level.
- Known typography/layout risks.
- Representative comparison candidates.

Distinguish approval of a font family from acceptance of every resulting layout.

We should NOT manually inspect thousands of essentially identical posters.

For changed-font collections, propose narrowly bounded, representative visual review groups.

Sample by relevant layout characteristics, including:

- Shortest and longest captions.
- Single-line and multiline labels.
- Uppercase/lowercase behavior.
- Wide and narrow glyphs.
- Numbers and punctuation.
- Accents and non-ASCII characters present in the English catalog.
- Maximum fitted font-size adjustments.
- Near-edge text and clipping risk.
- Different backgrounds or contrast conditions.
- High-difference outliers.

Use deterministic, stratified sampling plus worst-case selection, not arbitrary random samples.

A group-approval proposal must identify the complete candidate set, exact hashes, font/layout policy and the selected samples.

All unsampled members must still pass automated technical and tolerance checks appropriate to the approved group.

If a candidate falls outside the policy, move it into an exception queue.

Do not inherit acceptance from unrelated previous previews or apply a blanket font approval silently.

## 7. Design a manageable approval process

Separate the population into three practical review lanes.

### Lane A - Exact matches and renderer-equivalent replacements

`exact_match` requires identical candidate and published SHA-256 hashes and no publication.

`renderer_equivalent` is a separate, binary-different class. Images that meet a subsequently approved, well-calibrated renderer-equivalence policy should be eligible for collection-level approval without individual manual inspection. Include every eligible member in the exact publication manifest and upload plan, even when its appearance is effectively identical to the current published image. This eligibility does not grant remote-write or merge authorization.

Maintain exact identities and an audit record explaining why each candidate qualified.

### Lane B — Intentional font/layout changes

Provide review galleries with representative examples and worst-case outliers.

Support explicit approval of precisely scoped groups, with complete manifest hashes and evidence linking the samples to the members of that group.

Require individual review for outliers or exceptions.

### Lane C — Unexpected changes and blockers

Require targeted diagnosis and specific approval or correction.

Never hide them within a passing aggregate score.

The review interface can initially remain a local/static gallery. Do not build Poster Studio as part of this migration.

Produce a summary dashboard showing counts, distributions, examples, pending decisions and exceptions.

The intended result should be a small number of meaningful human decisions rather than thousands of repetitive approvals.

## 8. Overlay migration — independent publication group

Also inventory the already validated overlay transformation collection.

Existing Package E validation covered 4,122 overlay transformations.

Overlays should be treated separately from the ordinary English JPEG poster migration because their processing rules and acceptance checks are different.

Investigate:

- Exact mapping from generated transformations to real public destination paths.
- Whether every technical transformation corresponds to a published file.
- Existing versus candidate PNG hashes; exact matches can be skipped, while eligible binary-different overlays enter their separate approved publication group even when visually equivalent.
- Missing files and unrelated extras.
- Dimensions and resizing.
- Alpha channel integrity.
- ICC/profile handling.
- Foreground coverage and transparency.
- Cropping and placement.
- Differences from historical ImageMagick output.
- Whether the previously corrected LA/ICC cases remain valid.
- Prior individually accepted overlay samples.

The objective is **one logical overlay publication group, preferably one consolidated PR**, even if the files must be uploaded in multiple technical batches.

Do not assume all 4,122 transformations require new public files.

Do not treat the prior technical pass as blanket visual approval.

Propose a defensible overlay acceptance policy based on automated invariants, calibrated visual comparison, representative examples and clearly identified exceptions.

Retain the exact existing 64 approved overlay sample decisions where their original context and hashes still match.

Any changed context must receive appropriate new review.

## 9. GitHub upload batching and reliability

The reason for batching is to avoid operational GitHub upload failures while moving thousands of binary images.

Prefer standard authenticated Git transport for large publication sets rather than thousands of GitHub Contents API PUT requests.

Use existing `gh` authentication and verify the repository access available to `bullmoose20`.

No new personal access tokens or GitHub Apps are required for this migration design.

Investigate actual Git transport behavior, repository size, packfile size and GitHub limitations before selecting batch sizes.

Design a resumable, bounded upload mechanism.

Control batch size by:

- Maximum number of files.
- Total file bytes.
- Estimated or actual Git pack size.
- Observed network transfer success.
- Timeouts and server-side responses.
- Remaining changes.
- Recovery requirements.

Initial candidate operating range: 250–500 images per technical upload batch, subject to practical byte-size caps and measured evidence.

These are tunable defaults, not hard GitHub limits.

Support:

- Deterministic upload manifests containing every eligible binary-different candidate, including `renderer_equivalent` replacements, and excluding `exact_match`, withheld and blocked files.
- Incremental local commits when needed.
- Normal non-forced Git pushes.
- Idempotent reconciliation after ambiguous push outcomes.
- Verification that remotely accepted commits match the approved manifests, including SHA-256 checks of the actual remote image bytes against the exact approved Python outputs.
- Safe resume after interruption.
- No accidental publication of unapproved files.
- No unrelated worktree modifications.
- No history rewriting or force pushing.
- No racing changes against production master.
- No automatic fallback to a broad token or another account.
- Explicit stop conditions for repository/head drift.

GitHub's REST API secondary limits must not be confused with normal Git push transport restrictions.

A large logical publication PR can contain multiple verified transport batches.

Do not require separate human approval for every transport batch after its complete, exact artifact manifest has been approved.

Do not start remote writes while merely benchmarking the transport system.

Use local Git repositories and offline test remotes for benchmarking until publication is separately authorized.

## 10. Publication grouping

We do not want approximately 100 separate PRs for a 10,000-image library.

Propose a small number of logical publication groups based on:

- Verified renderer-equivalent outputs.
- Major font substitutions.
- High-risk layouts requiring specific acceptance.
- Category or dependency groups when useful.
- Overlay transformations as a separate group.

Aim for as few reviewable PRs as practical, but do not establish a fixed number without the inventory and Git size measurements.

For large PRs, provide clear machine-readable summaries and local/static review galleries. Do not depend exclusively on GitHub's Files Changed UI for reviewing thousands of binary images.

Each PR must be tied to:

- A specific approved manifest.
- An exact target baseline.
- Exact candidate artifact hashes.
- Approved visual policy and/or font-group decisions.
- Validation evidence.
- Complete proposed diff.
- Transport-batch audit history.

Only files covered by valid approval decisions can enter a publication candidate. Include all such binary-different files in the appropriate publication manifests, including approved renderer-equivalent replacements. Do not re-encode, optimize or otherwise modify the approved Python bytes during staging or transport; any changed artifact hash invalidates its approval binding.

Report the planned replacements by difference class so that eligible `renderer_equivalent` files cannot disappear from the upload plan. A skipped publication must have a recorded reason: exact SHA-256 match, pending required approval or blocker. If publication authorization is still pending, retain every eligible replacement in the manifest and upload plan and record that authorization as pending.

All staging PRs must remain draft until reviewed.

Never automatically merge a publication PR.

After an authorized merge, refresh production HEAD, retrieve and SHA-256-verify the actual published bytes against the approved manifest, record verification evidence and reconcile the next publication group. Verification failure remains an outstanding mismatch and stops dependent publication until investigated; it does not authorize an automatic corrective remote write.

## 11. Existing source and production protections

Preserve draft source PR #12 and all historical evidence.

Record the successful PR #198 canary as a separate completed production milestone.

Do not rewrite original acceptance records or historical reports.

Keep the production PowerShell scripts and launcher unchanged.

Do not switch the active production generator or remove legacy source until a later explicit cutover.

Do not activate non-English generation or translation publication.

Do not modify unrelated People Poster workflows.

Do not build or deploy the future online Poster Studio yet.

Do not install the previously prepared staging GitHub Actions workflow, create environments, install Apps or change repository permissions.

Do not enable any unattended publishing mechanism.

## 12. Implementation requirements

Build the minimum additional reusable tooling needed for:

1. Fresh English/overlay destination inventories.
2. Current-vs-proposed image comparisons.
3. Calibrated tolerance-policy evaluation.
4. Font-impact classification.
5. Review sampling and group manifests.
6. Static review galleries and exception queues.
7. Publication manifests.
8. Local/offline Git transport-batch preparation and testing.
9. Resume/recovery verification and audit reporting.
10. Full-library SHA-256 reconciliation before planning, after each authorized publication group and on subsequent unchanged runs.

Use existing infrastructure first.

Keep rendering, validation, approvals, publication planning and transport adapters independently testable.

Do not duplicate source-of-truth business rules.

All candidate records and decisions must be traceable to exact versions and hashes.

Implement unit, integration and failure-path tests covering visual comparison, stale approvals, wrong font, missing files, mismatched baseline, unexpected paths, partial upload recovery and dependency invalidation.

Also cover the synchronization decision sequence with focused tests:

- Identical SHA-256 hashes skip publication.
- Binary-different but approved renderer-equivalent outputs enter the exact upload manifest, including the 700 KB legacy / 650 KB Python example.
- Visual equivalence under an unapproved policy cannot approve or publish an image.
- Required font/layout reviews cannot be bypassed by passing visual metrics.
- Withheld and blocked artifacts cannot enter upload manifests.
- Stale source, baseline, font, layout, renderer, encoding or policy identities invalidate the affected approval/plan.
- Upload manifests preserve exact approved bytes and do not re-encode candidates.
- Remote byte mismatches fail verification even when the artwork looks equivalent.
- An unchanged rerun produces hashes matching verified published bytes and skips those files.
- Reconciliation accounts for all public destinations and every remaining mismatch without including private intermediates.

Run focused tests and existing CI.

Keep the solution portable and compatible with the current Python environment, with no unnecessary ML dependencies.

## 13. First execution and deliverables

**Proceed with the engineering and read-only/local validation now.**

Do not stop merely at another abstract design document.

Run the full English inventory using current available assets and verified validation outputs.

If existing caches are available and valid, reuse them.

If technical revalidation or partial generation is required, perform it within the established resource bounds and report the reason.

Run the overlay inventory separately.

Prepare representative comparison galleries, font-impact samples, calibrated tolerance evidence and publication-group recommendations.

Return a complete results report with:

1. Current source PR commit and CI status.
2. Fresh production `Default-Images/master` SHA and canary verification.
3. Total English catalog inventory and reconciliation.
4. Actual image counts by difference class.
5. Changed-image counts by category.
6. Font-impact matrix and proposed review groups.
7. Tolerance-policy proposal, including negative-control test evidence.
8. Number and nature of images requiring human attention.
9. Overlay transformation/publication inventory and exceptions.
10. Recommended Git technical upload batch sizes and byte caps.
11. Local Git transport/recovery test results.
12. Proposed logical publication groups and approximate PR counts.
13. Paths to local visual comparison galleries.
14. Source code/tests/documentation changed.
15. CI results and remaining blockers.
16. The exact maintainer approvals required before the first publication staging operation.
17. The full-library SHA-256 reconciliation described in section 15, including the number of eligible renderer-equivalent replacements in the upload plan. At this local/read-only stage, report actual prior publications separately from proposed replacements; do not claim planned files are published or remotely verified.

Be precise about work actually executed versus estimated or proposed.

If complete source images or local caches are unavailable, report the exact missing resources. Continue with the portions that can be completed rather than inventing counts or falsely claiming full validation.

## 14. Authorization boundaries

This assignment authorizes:

- Read-only GitHub inventory and comparison.
- Local Python rendering and verification.
- Reuse of verified caches.
- Local image analysis and review-gallery generation.
- Calibration and policy proposals.
- Local/offline Git transport testing.
- Changes to Python tooling, tests and documentation in source draft PR #12.
- Normal source PR CI.

It does NOT authorize:

- Creating publication branches or PRs in `Default-Images`.
- Uploading replacement artwork to `Default-Images`.
- Changing production `master`.
- Automatically approving artwork.
- Activating an unapproved tolerance policy.
- Merging PRs.
- Removing or replacing PowerShell production scripts.
- Installing publisher credentials, Apps or workflows.
- Publishing overlays or translations.
- Deploying Poster Studio.
- Starting unrelated migration phases.

No remote artwork writes are permitted in this assignment.

**Deliver the full English reconciliation, calibrated visual-risk analysis, overlay inventory, efficient Git transport design and proposed publication groups. Our goal is to synchronize the complete English library with the exact validated Python outputs through a manageable number of approvals, logical publication groups and reliable technical upload batches.**

## 15. End-state SHA-256 reconciliation and steady state

Produce a final reconciliation report for the complete expected public English catalog. Keep the separately inventoried overlays outside the English poster totals. Record the candidate manifest identity, generation context, compared production commit/tree, approved manifest identities, publication commits and remote verification evidence.

Report at least:

- Total expected English public images, reconciled to the fresh inventory rather than assumed from the historical count of 9,955.
- Exact binary matches at the planning baseline and at the final compared production commit.
- Binary-different images approved for replacement, broken down by difference class, including `renderer_equivalent` and approved font/layout changes.
- Images actually published and remotely SHA-256-verified against their approved Python outputs, including already verified canary publications separately from the current rollout.
- Images withheld for review or blocked, with per-destination reasons and the exact approval or resource needed.
- Remaining Python-versus-published SHA-256 mismatches, with every path, both hashes where available, classification, disposition and an explanation. Report missing or unreadable candidates/published artifacts explicitly; unavailable verification is not a match.

Distinguish baseline populations, publication activity and final-state totals so that an image published during this rollout is not double-counted as both an outstanding approved replacement and a final mismatch. At each snapshot, assign every expected destination one primary hash state: exact match, verified unequal hashes, missing candidate, missing published artifact, or unverifiable. List all applicable missing-resource details separately and ensure the primary-state counts sum to the expected public catalog total. Track approvals, publication progress and blockers independently.

Every eligible binary-different artifact must be traceable to an exact publication-manifest entry, including while publication authorization is pending. Its outstanding mismatch remains visible until the published bytes match. Successful publication requires actual remote SHA-256 verification, not only a transport success response.

The intended successful steady state is **zero unexplained SHA-256 mismatches** between the current deterministic Python-generated English outputs and their corresponding published images. Approved replacements still awaiting publication, review exceptions and blockers remain visible as explained outstanding mismatches; they are not synchronized and do not establish completion of full-library synchronization. Full synchronization requires all expected public outputs to be available and hash-verified as exact matches, with no unresolved replacements, missing files or verification gaps.

On a later run with unchanged inputs, fonts, assets, renderer and encoding dependencies/settings, generated hashes must match the published hashes. Those destinations become `exact_match` and are skipped without uploads. A binary-different image never qualifies as synchronized solely because it is visually equivalent.

These end-state requirements describe verification after separately authorized publication. They do not grant remote-write, merge or production PowerShell cutover permission under this assignment.
