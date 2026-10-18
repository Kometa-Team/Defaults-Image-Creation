# English production canary preparation — execution not authorized

Gate E is approved for the recorded validation scope at
`83ed3d1b11576f8e258aed08a3ae7ff13bf4791c` on draft PR #12.
[Gate approval](bulk/evidence/package-e/gate-e-approval-20261017.json) and
[audit events](bulk/evidence/package-e/gate-e-approval-20261017-events.json)
are additive records. This preparation grants no production permission and does
not approve uninspected artwork, activate translated layouts or adopt all overlays.
PR #12 stays draft. Existing PowerShell remains intact.

## Current readiness: seven images visually accepted; staging not authorized

The maintainer personally inspected every proposed image in the preparation-v1
review gallery and explicitly accepted **all seven exact images** for the controlled
English canary. The [individual visual acceptance record](bulk/evidence/english-canary/visual-acceptance-20261017.json)
and [portable review-service events](bulk/evidence/english-canary/visual-acceptance-20261017-events.json)
bind each decision to the exact image SHA-256, renderer/source/font/layout identities,
current validation fingerprint/policy version, owned receipt and documented published
comparison. Seven individual `Reviews.decide` approvals, with the exact current
nonblocking warnings, were recorded; no group or unrelated artwork was approved.

All **7/7 image hashes** were verified against the preparation report, actual gallery
files and sealed archive. The gallery HTML and archive SHA are unchanged. Published
RGB MAE/max differences and old/new blob/hash identities remain historical evidence;
acceptance applies to those exact comparisons, not a general pixel tolerance.
Acceptance-record envelope SHA-256: `139ed5b73c5ee555488163e024c85e33850207a401aa65b546d87c6b1a7f3919`.

This acceptance is a separate, version-bound record; do not repack the archive to
insert it or rewrite its historical pending-review labels. Future workflow validation
must retrieve the acceptance/audit records from a trusted pinned preparation revision,
verify their envelope hashes and seven-member bindings, and verify the unchanged
archive and its checksum inventory. No artwork needs reapproval while these exact
bytes and contexts remain valid; changed artifacts require new review.

**No staging or Default-Images write is authorized.** The proposed operational plan,
workflow implementation/deployment, credentials, reviewers/rollback owner, durable
artifact transfer and explicit staging permission remain outstanding. Visual acceptance
does not approve those steps, publication, PR #12 merge or PowerShell replacement.

| Requirement before staging | Current status |
| --- | --- |
| Gate E scope | Approved at `83ed3d1`; unchanged. |
| Exact canary artwork | **7/7 personally inspected and accepted**; current renderer/validation bindings verified. |
| Operational plan and workflow | Staging-only implementation prepared for review; not installed or enabled. Publishing/merging remain unimplemented. |
| Scoped credentials and environments | Separate setup authorization/review required; no write credential enabled. |
| Ownership and coordination | Name environment reviewers and rollback owner; confirm actual legacy launcher/configuration and a 30-minute single-writer/observation window. |
| Durable handoff | Local sealed archive verified; approve durable transfer/retention and retain the separate acceptance/audit records without repacking it. |
| Fresh target preconditions | Recheck exact target base/tree and seven old blob/hash identities before any later write; drift stops for review. |
| Staging permission | **Not authorized**; a later approval must name workflow/source, artifact, bundle/preparation/acceptance hashes, target base and seven paths. |

Validation of this acceptance update: twelve focused Windows checks pass, including
seven-member/image/context bindings, retained historical difference records and
explicit rejection of any staging/production authority. Full PR CI runs separately.

## Staging infrastructure prepared for review — not installed

The [staging-only implementation and exact setup guide](canary/STAGING_INFRASTRUCTURE.md)
now include a real YAML template outside `.github/workflows`, disabled policy and
unauthorized templates, seven-file guarded helper, minimal deployment manifest,
failure-path tests and a local-only Git dry-run. The
[separate action/authorization checklist](canary/STAGING_AUTHORIZATION_CHECKLIST.md)
lists every future configuration and staging operation. `bullmoose20` is proposed
as primary reviewer and rollback owner; no confirmation or GitHub assignment is inferred.

The prepared workflow implements **verify/stage only**. No publish, merge or rollback
mode exists. The broader publication ideas later in this plan remain future proposals,
not this implementation. All gates remain disabled, no App/environment/credential
is installed, and PR #12 is still draft. A separate infrastructure-only source
deployment is needed because source main lacks the shared runtime; copying YAML
alone is insufficient and merging PR #12 is not authorized.

The proposed read-only intake uses a source prerelease asset. Public exposure of
the unchanged ZIP requires a separate artifact-sharing decision; no source release
or upload was performed. If private intake is required, leave this template disabled
until an alternative adapter is reviewed. Preparation/visual approval does not grant
artifact publication, App installation, staging or any Default-Images write.

## Concrete candidate and observed results

Seven English posters in five categories, with a real generated Year parent/child
chain. No overlays, translations, private intermediates or unrelated artwork.

| Category | Exact public destination | Proposed SHA-256 prefix | Published SHA-256 prefix | RGB MAE |
| --- | --- | --- | --- | --- |
| Based | `based/Book.jpg` | `366a97b27d8e` | `fa8f19287c7a` | 0.126313 |
| Decade | `decade/2020.jpg` | `2f203c63553b` | `1d03a2d9639f` | 4.106223 |
| Franchise | `franchise/Death in Paradise (2011).jpg` | `d1a0ed5653e6` | `f10c0a851faa` | 0.123287 |
| Genre | `genre/Action & Adventure.jpg` | `6e117a400959` | `167e5dde50f4` | 0.247524 |
| Genre | `genre/Splatter.jpg` | `7ed904a5e3bc` | `842a21c48e79` | 0.253226 |
| Year | `year/2020.jpg` | `c7be058188e0` | `584851abc0c7` | 2.762548 |
| Year | `year/best/2020.jpg` | `48b58132ddf6` | `9cd75035e487` | 2.861623 |

Prefixes aid reading only. The [preparation evidence](bulk/evidence/english-canary/preparation-20261017.json)
contains **all full SHA-256 hashes**, exact published Git blobs, sizes, diagnostic
codes, captions/parameters, fonts/assets, layouts, renderer and policy identities.
The Action & Adventure destination MUST retain the exact case shown; publishers
must use `destination`/manifest `remote_relative`, never a local basename.

Fresh local strict preflight passed. Cold generation produced seven outputs using
two workers; unchanged warm generation produced zero renders and zero worker
starts and retained the exact manifest. Every output was fully decoded as a
2000×3000 RGB JPEG and its hash/render fingerprint exactly matches the approved
full-English run. The child `year/best/2020.jpg` uses the newly generated
`year/2020.jpg` bytes with dependency hash
`c7be058188e042d4b7b7d001ee9848e7c2995592a7d76c0e55b76d8863d0f9f4`.
Preparation executable checkpoint: `41b326b`; actual helper SHA and complete
renderer/version identities are in the evidence. All renderer/catalog inputs were
checked against approved `83ed3d1`; only preparation tooling is new.

The GET-only comparison fetched and Git-blob-verified all seven existing destinations
against current `Kometa-Team/Default-Images`, branch `master`, head
`59e49ede8d41ac5991f971e66e93af596402329a`, tree
`e1664efb92db5872db112cf18253910da77355df`. The branch head was checked again after
fetching. All paths exist exactly: zero missing paths or case conflicts. All seven
candidate images differ in both file bytes and decoded pixels from published
artwork. The MAE values above are observations, **not acceptance tolerances**.
Parity with validated Python outputs does not approve these seven for publication;
no old visual acceptance is automatically transferred. The maintainer subsequently
inspected and accepted these seven exact candidates as recorded above; publication
authority remains separate.

Local review page: `config/english-canary/preparation-20261017-v1/review.html`.
Click each image for full resolution; left is proposed and right is pinned published.

```powershell
Set-Location C:\Users\bullmoose20\Defaults-Image-Creation
Start-Process -FilePath (Resolve-Path 'config/english-canary/preparation-20261017-v1/review.html').Path
```

## Verified local handoff and backup

[Bundle index](bulk/evidence/english-canary/bundle-index-20261017.json) binds a
local archive, complete file inventory and all backup checksums. No archive or
image was uploaded to Default-Images or added to this PR.

- Archive: `config/english-canary/preparation-20261017-v1/english-canary-review-bundle.zip`.
- Archive SHA-256: `97d82b19eb237908cbd4657c67ca16eefe089b5a6d6a5f9e1690fda6cdb597c5`.
- Archive size: **7256318 bytes**, 26 members. `SHA256SUMS.json` binds the other 25.
- Preparation envelope SHA-256: `bc7657363fb253bb41965b56bd73ef650be5dc9606bfff486ac8aa76eb2d77be`.
- The archive contains seven proposed images, seven verified old image blobs,
  manifests/receipts/results, review HTML, checksum inventory and source backups.
  It contains no credentials, fonts, SQLite databases or runnable publisher.
- Existing production source repository `main` was pinned at
  `57ef136833a3f54da2bf1e4ddef98addfa36d583`. Exact current
  `create_defaults/create_default_posters.ps1`, `create_defaults/create_poster.ps1`
  and `.github/workflows/default-poster-validation.yml` bytes were fetched read-only,
  Git-blob-verified and backed up. Their hashes and source tree are in the index.
- Default-Images `master` was observed unprotected; its `.github/workflows`
  directory returned 404. No target workflow was found or installed. This is an
  observation at preparation time, not a guarantee about future settings.

An [offline rollback rehearsal](bulk/evidence/english-canary/rollback-rehearsal-20261017.json)
in a fresh local Git repository with **no remote** copied the old images, committed
exactly the seven replacements, and reverted that local commit. All seven original
hashes and the original tree were restored; an unrelated sentinel stayed unchanged.
This proves the copied-file/Git procedure only. It does not test production access,
branch rules, concurrent writers, CDN behavior or permission to roll back production.

Do not edit/repack the archive after acceptance. Any changed bytes, source, font,
layout, policy, candidate scope or target base require a new preparation version,
comparison and appropriate review. Retain prior versions. Before a future write,
refresh the baseline and backups: the pinned comparison is not a live authorization.

## Proposed workflow and publication mechanism — not installed

Recommended new workflow name: `english-poster-canary.yml` in
`Kometa-Team/Defaults-Image-Creation`. It must be independently reviewed and deployed
only after setup approval; it is **not** added to `.github/workflows` in this PR.
No production publisher implementation, secret, environment or branch setting was
enabled. Existing validation CI continues to run on the draft PR.
This task adds no CI workflow edits and does not replace the PowerShell entry point.

Use manual `workflow_dispatch` with an explicit `stage`, `publish` or `rollback`
mode, pinned approved preparation source, exact bundle artifact ID and SHA-256,
preparation envelope SHA-256, target base commit, and (for publishing) the reviewed
candidate commit/PR number. Reject missing/mismatched values and any extra path.
No push, schedule, PR or workflow-completed trigger may publish. Pass inputs as
validated structured data/environment values, never direct shell interpolation. The workflow must
exist on the source default branch before manual dispatch; this requires separately
authorized workflow installation, not merging PR #12. See GitHub's
[manual workflow requirements](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow).

| Job / step | Proposed behavior | Permission boundary |
| --- | --- | --- |
| Verify inputs | Download the exact approved review archive; verify archive SHA, duplicate/unsafe/symlink ZIP entries, exact inventory/checksums and all seven JPEGs. Read data only; never execute bundled scripts. Verify Gate E record, source/renderer/font/layout/policy and seven artifact decisions. | Trusted pinned code; source `GITHUB_TOKEN` has `contents: read`, `actions: read`; no target write token. |
| Recheck target | Fetch fresh branch/tree and seven old blobs; require exact approved base SHA, old hashes and exact-case paths. Verify writer reservation and backup availability. | GET-only target access. Drift stops the run; never automatically rebase or regenerate. |
| Stage, after setup/staging approval | Mint short-lived target App token, create seven new blobs, a tree based on the approved target tree and a commit with exactly that base as sole parent. Create a new `canary/english-<unique-id>` branch and open a review PR against `master`. Verify its complete diff is exactly the seven images and new hashes. | Protected staging environment; target `contents: write`, `pull_requests: write`. No master update or auto-merge. This staging is a future remote write and is not authorized by Gate E/preparation approval. |
| Publish, after a second explicit approval | Require human-reviewed exact candidate commit and seven-file PR. Recheck current base and blobs, verify backups and all final hashes. Update only `refs/heads/master` to that exact candidate commit using Git refs API with `force: false`. | Separate protected production environment, required maintainer review and no bypass. Never call merge on PR #12. No blob regeneration or additional commit during publication. |
| Verify publication | GET the new target head/tree, the exact seven blob bytes and their raw delivery URLs. Verify counts/hashes/dimensions and unchanged other paths. Retain receipts and monitor the finite canary. | Read-only verification; no automatic expansion or further runs. |
| Rollback | Only after separately explicit rollback authorization and selected-path ownership checks: make a new commit restoring the seven saved old blobs on the then-current head. Review it and publish with the same non-forced ref procedure. | Preserve history and unrelated commits. Stop for conflicts; no `reset --hard` or forced remote ref update. |

The candidate has the approved base as its sole parent. A non-forced fast-forward
ref update fails if a competing writer adds a divergent commit between the last
read and publication. This server-side guard matters because a prior GET alone
cannot prevent a race. Treat every non-fast-forward/ref error as a stop, not a retry
with `force: true`. Respect any branch rules added later; never bypass protection.
The [Git refs API](https://docs.github.com/en/rest/git/refs?apiVersion=2022-11-28)
documents the update and `force` behavior.

Use one concurrency group, `default-images-english-canary`, with
`cancel-in-progress: false`. This does not lock the existing PowerShell process or
other workflows: a maintainer must reserve a write-free interval for the seven
paths. No competing writer is automatically paused or modified by this proposal.
Set a 15-minute job timeout and disallow automatic retries of write steps. On an
ambiguous network failure, GET current refs/objects first. If the exact intended
commit is already present, verify and retain it; otherwise stop for reconciliation.

## Credentials and permissions — none activated

The built-in source workflow token is limited to its own repository; it cannot
be treated as a Default-Images write credential. See
[GitHub token scope](https://docs.github.com/en/actions/concepts/security/github_token).
Use a separately installed GitHub App restricted to **Default-Images only**, with
Metadata read, Contents write and Pull requests write. No Administration, Workflows,
Actions write, deletion or organization-wide access is required by this design.
A future installation token must be minted only inside the approved protected job,
kept out of logs/artifacts and never persisted in checkout credentials. Revoke it
at job completion. Select and pin any token action to a reviewed immutable SHA
before workflow deployment; do not substitute an unreviewed floating tag.

App installation/configuration and its environment-scoped private key/app/installation
IDs require separate setup authorization. Do not reuse a broad personal `gh` login
or add target write scopes to the read-only preparation helper. The proposed
`english-canary-stage` and `english-canary-production` environments require named
maintainer reviewers, restricted trusted refs and a tested no-bypass policy. The
maintainer must choose reviewer membership and whether independent review is required.
Environment secrets are released only after configured protection passes; see
[GitHub deployment controls](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/control-deployments).

## Backup, failure stop and rollback procedure

Before future staging/publication, verify and retain the approved archive in durable
restricted artifact storage with its exact SHA and per-file inventory. The local
archive is currently the handoff, not durable shared storage. Retain at least 30 days,
and keep a second verified copy outside an expiring Actions artifact. Save old target
head/tree, all seven old blob IDs/SHA-256 hashes, new candidate hashes, source/workflow
commits, dependency/font/policy versions and the execution/approval receipts. Recheck
these against the current target before obtaining a write token.

Stop **before the next write** for any missing approval, stale base, unexpected path,
case conflict, missing backup, mismatch, unaccepted warning, source/renderer/policy
change, competing writer, token/permission error, failed decode, extra diff or
ambiguous write result. Preserve all evidence and revoke/end the job token. No
fallback, broad copy, partial seven-file publication, overwrite retry or automatic
rollback is allowed. If only a staging branch exists, leave it unmerged for review;
master must remain unchanged. Do not automatically delete forensic branches.

If production verification fails after publication:

1. Stop the job and all further canary writes; capture current head/tree, request
   outcomes and actual affected hashes. Notify the designated maintainer through
   the run report; no automated messages to third parties are installed.
2. Request explicit rollback approval naming the published canary commit, seven
   paths and saved baseline. Production rollback is itself a production change.
3. Re-read current selected blobs. They must still match the canary's proposed hashes.
   If another writer has changed any selected path, stop for manual reconciliation;
   do not overwrite that writer. Unrelated commits may be preserved by basing the
   rollback on the newly approved current head.
4. Construct one new rollback commit restoring only the saved seven old blobs, verify
   the exact diff, and request/obtain required review. Publish non-forced against
   the pinned current head. A concurrent change again requires a stop/review.
5. Verify all seven restored SHA-256 hashes and dimensions, unchanged unrelated paths
   and raw delivery. Record the restorative commit. Leave the existing PowerShell
   generator/workflow intact; if it was administratively paused for the canary,
   the designated owner may resume it only under the separately approved schedule.

## Measurable success criteria

| Check | Required result |
| --- | --- |
| Scope and strict validation | Exactly seven English outputs, five categories, zero overlays/multilingual/private extras, zero blocked variants and all current warnings explicitly accepted for those seven. |
| Render and dependency parity | Seven exact full-run hash/fingerprint matches; child refers to the verified generated parent's SHA. Full decode: 2000×3000 RGB JPEG. |
| Cache and limits | Unchanged warm run: zero renders/worker starts, identical manifest. Local preparation within 900 seconds, two workers, 2 GiB sampled process-tree ceiling, 64 MiB output cap and 2 GiB free-disk floor. No complete-production speedup claim. |
| Fresh published baseline | Exact approved base/tree and seven old blob/hash identities; zero missing paths or case conflicts, including uppercase `Adventure`. |
| Candidate review | Maintainer has inspected and accepted the seven exact proposed bytes and documented all observed published differences. No approval inheritance from Gate E or other samples. |
| Staging | Exactly seven image changes; no workflow, multilingual, overlay, source or unrelated artwork changes in the target commit; zero deletions or renames. |
| Publication | One explicitly authorized non-forced target ref update to the reviewed commit; no partial per-file updates. All seven canonical remote blob SHA-256 hashes equal the approved candidates. Other paths unchanged. |
| Delivery and observation | Seven public raw URLs return HTTP 200 and expected image bytes within 10 minutes; repeat blob/hash checks at 0, 5 and 30 minutes. Thirty-minute writer reservation and named observer. Any mismatch stops progress; no automatic expansion. |
| Recovery readiness | Durable verified backup and named rollback owner available; local seven-file restorative rehearsal passed. No claim of remote rollback permission testing. |

## Remaining approvals and exact operator steps

**Not executable yet:** the staging-only helper/workflow is prepared for review,
not installed or enabled. The production publisher remains a future proposal. There is no current Run workflow button for `english-poster-canary.yml`,
no enabled write credential and no canary branch/PR. The steps below are conditional
instructions after the stated approvals, not commands to run now.

1. **Completed: visual acceptance of all seven exact images is recorded.** Preserve
   the acceptance and audit records alongside the unchanged bundle. Verify their
   exact hash/context bindings before a later operation; a changed artifact/scope
   needs a fresh sealed proposal and appropriate new review.
2. Choose the named rollback owner, environment reviewers and 30-minute observation
   window. Identify the actual existing PowerShell launcher/scheduler, arguments and
   configuration, preserve them, and confirm a single-writer reservation for the seven
   paths. These operational ownership details were not inferred from a validation workflow. Approve the
   proposed PR-stage/non-forced-publication mechanism or request changes.
3. Separately authorize review/deployment of the prepared staging-only workflow
   and narrowly scoped App/environment setup, following the infrastructure guide. The setup review must provide the
   exact workflow/helper/action SHAs and proof that all missing/stale approvals and
   stale-base paths fail closed. Installing it on the source default branch needs
   its own reviewed change; **PR #12 remains draft and unmerged**.
4. Approve the artifact-intake backend before any upload. The current proposal uses
   a published source prerelease asset, which would make the ZIP public; that sharing
   needs explicit approval. A private backend would require its own reviewed adapter.
   Verify downloaded bytes equal the archive SHA above;
   record the artifact ID, digest and retention. Do not rerender in a Linux publisher:
   these reviewed artifacts are bound to the recorded Windows renderer context.
5. After setup verification and a fresh target comparison, give a **staging-only**
   approval naming the bundle SHA, seven paths, source/workflow SHA and target base.
   In source repo Actions → English Poster Canary → Run workflow, select the trusted
   deployed ref, mode `stage`, exact source release asset ID and explicit confirmation.
   The helper reads approved hashes/base from the reviewed authorization JSON, not
   arbitrary workflow inputs.
   Approve only the staging environment. Verify the resulting seven-file target PR;
   master must remain at the approved base. No automatic merge.
6. Inspect that PR and its exact candidate commit. Give a **separate production
   approval** naming the candidate commit, target PR, base head, bundle/preparation
   SHA, seven paths, observation window and rollback owner. A future production
   implementation must first be separately prepared, reviewed and deployed.
   The prepared staging workflow has no `publish` mode; never treat it as permission
   or code to execute this future production operation. This step is the first
   authorization to change production files; nothing in Gate E/preparation substitutes.
7. Watch its retained verification receipts and 0/5/30-minute checks. On failure,
   follow the stop/explicit-rollback procedure. On success, report the result and
   stop. No wider cutover, extra categories, overlays, translations or phase starts.

Suggested subsequent plan/setup authorization wording — **not granted by visual acceptance**:

> I approve the proposed staged-canary/rollback plan for the seven already visually
> accepted images in preparation envelope
> `bc7657363fb253bb41965b56bd73ef650be5dc9606bfff486ac8aa76eb2d77be`. I authorize preparation
> and review of the guarded workflow and scoped credential setup for approval.
> Do not create the target canary branch/PR or publish until separately authorized.

Future staging authorization must name the deployed workflow SHA and artifact ID;
future production authorization must additionally name the resulting candidate
commit and target PR. Those identities do not exist yet and are deliberately not
invented in this preparation. Rollback authority must also be explicit if needed.

## Reproduce preparation only

Using the existing isolated bulk environment, a fresh root and explicit read-only
GitHub access:

```powershell
& 'config/package-e/dependency-trial/venv/Scripts/python.exe' -m create_defaults.bulk.e_canary --root config/english-canary/preparation-review-v2 --compare-published
```

A fresh environment uses Python 3.13 and `create_defaults/requirements-bulk.txt`.
The exact Windows/Python/native/dependency versions in the accepted evidence are
required to reproduce its byte identities. Other environments create new artifacts;
fail parity rather than transfer approval. The command generates local evidence,
uses bounded GET-only comparison and has no publishing or dispatch command. A fresh
root never replaces this v1 evidence. It does not package a new bundle automatically;
a changed proposal must receive its own verified checksum inventory and archive.
