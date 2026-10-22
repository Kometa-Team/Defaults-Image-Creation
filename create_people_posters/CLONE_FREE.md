# Clone-free people publishing

Clone-free publishing is the default. The public example and orchestrator use
`github_api` / `batch`, avoiding all seven local image clones. Full-clone
`local_git` / `persistent` remains an explicit fallback. Both modes remain
supported, and the Adobe/Selenium background-removal option is unchanged.

Historical diiivoy/diiivoycolor font replacement is a separate maintenance flow:
[Diiivoy Jost Migration](JOST_MIGRATION.md). It reads the existing local transparent
collection, reuses two-style API publishing with its own state/workspaces, and
cannot write to the other five repositories. Normal batch cleanup is unchanged.

## Dependency audit

The code repository stays on `main`. On 2026-10-14, read-only GitHub checks
confirmed that all seven image repositories have `master`, not `main`. The
maintainer explicitly approved using `master` for those repositories. No branch
is created or selected implicitly when a configured branch is missing.

| Dependency | Legacy consumers | Clone-free replacement |
| --- | --- | --- |
| Existence | ensure_people_repo, audit_people_images, scan_kometa_logs, find_and_download_missing_people | Authenticated branch validation and cached tree inventories across all seven repositories; a person is complete only if every style exists. |
| Metadata | compare_image_trees, image_check | Git tree paths, sizes and blob IDs; pixel-dependent metadata requires a selective download. |
| Image content | recover_edge_chops, resolve_original_images, image_check | Normal recovery inspects only the current generated batch. Explicit remote recovery downloads selected names, never the full library. |
| New images | sync_people_images | Same source validation, original JPEG normalization and transparent canvas normalization, followed by Git Data API publishing. |
| Git synchronization | ensure_people_repo, update_people_repos, orchestrator ensure_repo/update/push | API validation, authoritative inventory refresh, batched commits and non-forced ref updates. Existing local Git implementation remains available. |
| README generation | auto_readme, sync_md, update_people_repos | Preserve existing destination readme.yml workflows and [skip readme] convention; dispatch after all image publications succeed. |
| Quality auditing | sync_people_images, image_check, compare_image_trees | Validate current batch before publication. Whole-library pixel audits remain explicit local-library maintenance tools. |
| Edge recovery | recover_edge_chops | Existing detector, TMDb alternate selection and rendering are unchanged; workspace paths isolate the current batch. Selective remote inputs are available for named maintenance. |

`tmdb_people`, `truncate_tmdb_people_names`, `audit_people_images`,
`colorize_noncolor_ddcolor`, `prep_people_dirs`, `remove_bg_birefnet`,
`sel_remove_bg` and `create_people_poster.ps1` use configurable workspace paths.
Models, DDColor vendor code and browser profiles stay outside jobs. There is no
`colorize_noncolor.py` in the current tree; DDColor is the supported colorizer.

`compare_image_trees.py`, `grayscale_sweeper.py`,
`rebuild_since_signature_commit.py`, local README/grid generation and full-library
pixel audits are deliberately separate maintenance operations, not silently
skipped requirements of ordinary API publishing. They still require local
image trees. `resolve_original_images.py` accepts selected reference trees;
materialize selected remote names first when using it without clones.

The sweeper is an explicit optional operation, for example from this directory:
`python grayscale_sweeper.py --src "D:/Pictures/Headshots" --dest-other "./config/Downloads/other"`.
It supports `exact` (default), `sat`, `satq`, `colorfulness` and `auto`;
the [sweeper reference](README.md#sweep-any-tree-for-noncolor-images-helper)
describes their thresholds and heuristic limitations. It copies by default,
requires `--move` for removal and `--overwrite` for exact-name replacements,
and appends `DEST/.grayscale_sweeper.log`. It is not invoked by API publishing
or the orchestrator, and imports/help do not create folders or truncate logs.

All seven destination `readme.yml` workflows were inspected read-only. They
support workflow_dispatch and push, skip scripted [skip readme] commits, use
per-repository concurrency, read tree metadata without image downloads and
update master using non-forced Git Data API refs. They are not rewritten here.

## Setup and migration

No existing clone, staging image or checkpoint is deleted during migration.
Keep your existing libraries until you have tested the new mode. New installations
default to API/batch. Existing `.env` files are not overwritten: if yours selects
`local_git` / `persistent`, change these settings in `config/.env` to migrate:

```dotenv
PEOPLE_PUBLISH_MODE=github_api
PEOPLE_WORKSPACE_MODE=batch
PEOPLE_BRANCH=master
ORCH_GENERATE_READMES=false
PEOPLE_BATCH_RETENTION_DAYS=3
PEOPLE_FAILED_BATCH_RETENTION_DAYS=14
PEOPLE_AUTO_CLEANUP=true
PEOPLE_JOBS_MAX_GIB=20
```

Without an explicit mode setting, the orchestrator also defaults to API/batch.
The default never falls back to cloning automatically if authentication or an API
request fails. Fix access or explicitly select full-clone mode instead.

`PEOPLE_IMAGES_DIR` is ignored by ordinary API-mode orchestration; it may remain
configured for legacy maintenance. Set `PEOPLE_JOBS_DIR` and `PEOPLE_STATE_DIR`
to separate absolute directories if desired. Do not put persistent state or
model caches inside jobs. Never run legacy `clean_people_config --include-staging`
against a batch workspace; use the receipt-aware cleanup command below.

Install the existing requirements and model environments as described in the
main README. The clone-free publisher adds no paid services or extra packages.
Native poster generation uses Pillow and the documented fontTools layout helper;
PowerShell/ImageMagick are required only for `POSTER_ENGINE=powershell` or the
comparison utility's reference run. See [native rendering](POSTER_RENDERER.md).
DDColor/BiRefNet inference and poster designs are unchanged.

Legacy full clones, including their Git history, can require hundreds of
gigabytes. API mode stores tree metadata instead of those image libraries, but
model downloads, Python environments, source photos and active/retryable batches
still require local storage. The measured production jobs below used about
46-52 MiB each, excluding models, dependencies and shared metadata; this is not
a total installation size or a per-person guarantee. The 20 GiB job budget is an
admission guard, not a hard disk quota. Existing clones and legacy
`config/people_dirs` are never removed by the new job cleanup.

### Windows PowerShell

Run from `create_people_posters`:

```powershell
.\venv\Scripts\Activate.ps1
gh auth login
python people_remote_inventory.py --refresh
python orchestrator.py --new-batch --people-list .\config\people_list.txt --stop-after poster_ps1
python orchestrator.py --redo sync_images --dry-run
python orchestrator.py --redo push
```

### Linux/macOS

```bash
source venv/bin/activate
gh auth login
python people_remote_inventory.py --refresh
python orchestrator.py --new-batch --people-list ./config/people_list.txt --stop-after poster_ps1
python orchestrator.py --redo sync_images --dry-run
python orchestrator.py --redo push
```

Inspect generated images before the final command: **`--redo push` publishes**.
Do not use production destinations for experimental publication tests.
`--dry-run` suppresses all GitHub mutations, success receipts and cleanup; it
can still generate local images and prepare pending plans. For a publication-only
preview use `publish_people_github.py --op push --batch-id ID --config JOB --dry-run`.

The named steps retain their order: `ensure_repo` validates remotes, `update`
refreshes metadata, `sync_images` validates/prepares canonical files, and `push`
publishes them. `--redo tmdb` and `--redo remove_bg` still mean rerun that step
and its downstream steps. In batch mode the current unfinished job is resumed;
use `--new-batch` to start a different input set. `--batch-id ID` selects a
specific unfinished job. `--people-list` explicitly bypasses log discovery;
without it the normal log-based discovery steps remain. An explicit batch list
does not also import the global people_overrides.txt; include desired aliases
in the supplied list. Normal batches snapshot both legacy input files. Names, TMDb IDs and
aliases retain their existing input formats. Once files are validated, changing
their sources requires a new batch, not reusing an old publication receipt.

To return to legacy behavior, select `local_git` and `persistent`, restore your
`PEOPLE_IMAGES_DIR` setting and use the existing commands/checkpoints. These
settings do not change or delete retained API jobs. Batch mode also works with
local_git; cleanup verification conservatively requires the remote head to match
the local committed tree. If README generation advances it, refresh the clone
and retry `--redo push` before cleanup can become eligible.

## Authentication and publication

Authentication priority is process `GITHUB_TOKEN`, process `GH_TOKEN`, then
`gh auth token`. For unattended execution use a fine-grained PAT or GitHub App
installation token scoped to all seven destination repositories, with
**Contents: read/write**, **Metadata: read**, and **Actions: write** for README
dispatch. Installation tokens are supplied/renewed by the operator; token minting
is not implemented here. Never commit credentials. A default Actions
`GITHUB_TOKEN` for this code repository does not automatically have cross-repo
write access. Community contributors without permission need an authorized
fork/PR workflow; automatic fork creation is not implemented.

The configured branch must exist. There is no fallback branch or force update.
Branch protection/rulesets may reject publication even with Contents permission;
configure an approved identity rather than disabling protection. A branch rename
also requires updating destination workflows, which currently target master.

Each changed image needs a blob request; up to 100 files / 256 MiB share a commit.
Existing files are compared using Git blob hashes, not timestamps. New trees
always retain the remote base tree. Unrelated concurrent changes are rebased;
conflicting edits to the same path block instead of being overwritten. The
original baseline persists across crashes. Unicode/case collisions, ambiguous
TMDb identities, missing styles, unsupported paths and invalid images block
publication. Grayscale remains a warning under the existing quality policy.

Requests are sequential, mutations are spaced by one second by default, and
network/5xx/rate failures receive bounded exponential retries. Rate resets over
five minutes stop with a retryable error. Authentication failures do not retry
indefinitely. Files over 100 MiB are rejected. Inventory caches store metadata
only; branch heads are checked on refresh, and truncated recursive responses
are discarded and replaced with explicit subtree traversal. Failed refreshes
do not replace a previously complete cache. GitHub remains authoritative.

Publication is not atomic across seven repositories. SQLite and exported JSON
record batch, person/TMDb identity, repo, path, source SHA-256, canonical SHA-256,
Git blob SHA, branch, commit, attempts, status and sanitized errors. A successful
ref response and matching destination tree are required before a published
receipt. On resume, confirmed destinations are checked without uploading again;
only outstanding content creates commits. A lost ref-update response is
reconciled against the current tree. Previously confirmed images that change
remotely block the batch for review.

README dispatch happens only after every image destination succeeds, preserving
`[skip readme]`. `UPDATE_TRIGGER_READMES`, `UPDATE_REQUIRE_README_DISPATCH` and
`UPDATE_README_SKIP_MARKER` retain their meanings. Required dispatch failures
retain the batch; optional failures are recorded warnings. Dispatch confirmation
means GitHub accepted the workflow, not that the asynchronous run finished.

## Jobs, retention and recovery

The compatibility layout is:

```text
config/state/people_inventory.db
config/state/publication_state.db
config/state/manifests/ID.json
config/models/...
config/jobs/ID/
  input/people_list.txt
  people_list.txt
  posters/
  Downloads/{color,other}/
  people_dirs/{Downloads,original,transparent,bw,diiivoy,diiivoycolor,rainier,signature}/
  .publish/ID/...
  .orch/...
  logs/
  manifest.json
```

Original normalization still creates a presentation copy, not an exact archival
backup of the source photo. Completed-job cleanup removes native intermediate
sources too. Keep irreplaceable source archives outside managed jobs; supplied
lists and sources outside them are not deleted. No images from old clones or
legacy people_dirs are copied into new jobs automatically.

Job state distinguishes pending, processing, generated, validated, partially
published, published, cleanup eligible, complete and failed. Image receipts
separately distinguish pending/attempted/failed/conflict/published. Checkpoints
are per job, so a restart reuses validated output rather than running models
again. SQLite transactions and atomic JSON replacement make interrupted writes
retryable. Dead-process locks can be recovered; malformed locks require manual
inspection. Never remove a live run's lock.

After all mandatory publication checks, successful files are retained for three
days by default. Each batch-mode orchestrator launch, including resume, checks
for eligible cleanup once under `config/state/orchestrator.lock` (or the configured
state directory). Explicitly resumed jobs are protected before cleanup; new jobs
are admitted after cleanup so reclaimed space counts toward the budget.
`PEOPLE_AUTO_CLEANUP=false`, `--dry-run` and `--list` skip launch cleanup. No
scheduler or background service is needed. Manual maintenance remains available:

```bash
python people_workspaces.py          # cleanup dry-run
python people_workspaces.py --apply  # apply only eligible completed publications
```

Cleanup preserves manifests, SQLite metadata, models and compact logs. It accepts
only known job IDs with matching managed manifests and verified receipts, and
rejects traversal, symlinks and Windows reparse points. Interrupted cleanup can
be retried. Active jobs are excluded.

The launch summary logs `eligible`, `deleted` and `retained` batch counts.
Eligible means the retention and existing receipt/hash checks passed; deleted
means payload cleanup completed, not that durable manifests were removed.
Retained counts jobs not marked complete, including active, young and incomplete
jobs. Cleanup errors produce a visible warning and counts without marking the
current recoverable batch failed; retry cleanup after resolving the problem.
Historical `config/people_dirs`, Git clones, model caches and sources outside
managed jobs are never part of this cleanup.

**Unpublished files are never automatically expired**, even after the default
14-day failed-job retention threshold. Old failures are reported for recovery,
not deleted. The default 20 GiB managed-job admission/step guard prevents
indefinite acceptance of new jobs while failures accumulate. It is not a hard
filesystem quota and a single processing step may exceed it; size batches and
configure disk space accordingly. No service, scheduler or Logscan queue is added.

For an interrupted or partially published job:

1. Run `python orchestrator.py --workspace-mode batch --list` to list jobs.
2. Inspect `config/state/manifests/ID.json` and the job logs.
3. Fix authentication/network/model/input problems without deleting job images.
4. Resume `python orchestrator.py --batch-id ID`, or `--batch-id ID --redo push`
   when generation/preparation already succeeded.

For 401/403 check token expiry/permissions and branch rules. For 404 check the
exact repository, branch and token scope. For rate limits retry later. For a
same-path conflict, review the community edit and preserve the old job before
creating an explicitly approved replacement batch. Do not change the branch or
receipt database to force an upload. Restore missing validated files from retained
sources; a corrupt/missing prepared output blocks upload rather than guessing.

## Selective pixel maintenance

Fetch only selected people's existing outputs when recovery or original resolution
needs pixels, then point the existing maintenance tool at that temporary tree:

```bash
python people_remote_inventory.py --names "Tom Hanks" --output ./config/remote-review
python recover_edge_chops.py --people-root ./config/remote-review --transparent-root ./config/remote-review/transparent --audit-only
```

Downloads are blob-hash verified. This explicit review tree is not an automatic
batch; remove it after the review yourself. Whole-library tools still need local
trees and may consume substantial disk and time. They do not run implicitly
during a small API batch.

## Isolated live sandbox

`sandbox_people_github.py` is an explicitly invoked live test runner. It does not
commit or push this code repository. With `--create-repos`, it creates seven
**private personal repositories** named `OWNER/kometa-people-sandbox-STYLE`.
Never supply production repositories as sandbox destinations.

```powershell
python sandbox_people_github.py --owner YOUR_LOGIN --run UNIQUE_RUN_NAME --create-repos --source-job config/jobs/VALIDATION_JOB_ID
```

The source must be an existing `validation_only` job with seven generated styles.
The runner copies its outputs into a new isolated job; it never repurposes the
source job or its publication receipts. It performs intentional sandbox-only
partial failure, disk-state reopening, remaining uploads, actual README workflow
completion checks, byte-verified downloads, unchanged reruns and retention cleanup.
Only test jobs are cleaned, with zero-day retention scoped to the runner process.
The original source images and model caches remain outside that cleanup.

Run reports and receipt databases remain under `config/sandboxes/RUN/`.
Remote sandbox images, workflows and commits are retained for inspection; the
runner does not delete test repositories or modify existing unrelated repos.
It refuses to overwrite an existing repo without its recognized sandbox marker.
Creating private repositories requires the appropriate GitHub account permissions;
installing the copied workflow also requires workflow scope for classic tokens.
Actions must be available on the account. No billing settings are changed.

The workflow is a structured copy of each destination's real README workflow,
without Discord notifications. Its repository-scoped GitHub token cannot publish
to the community repositories. The existing README generator's community image
URL conventions are unchanged; this tests generation and commit behavior, not
using private sandbox README links as production assets.

For manual inspection/recovery, select the generated profile in the process
environment (PowerShell shown; use `export NAME=value` on Linux/macOS):

```powershell
$env:PEOPLE_GITHUB_TARGET = 'sandbox'
$env:PEOPLE_SANDBOX_CONFIG = (Resolve-Path 'config/sandboxes/RUN/targets.json').Path
python orchestrator.py --publish-mode github_api --workspace-mode batch --list
```

Sandbox mode requires an exact seven-repo mapping, `master`, private non-fork
repositories and separate jobs/state paths. The HTTP transport rejects every
request outside its allowlist, including reads and encoded/traversal paths.
Leaving a sandbox config set while selecting production is an error, not a
fallback. Existing receipts cannot be retargeted between profiles. Local Git
and persistent-workspace orchestration are blocked in sandbox mode.

Before returning to production, unset `PEOPLE_SANDBOX_CONFIG` and sandbox-specific
`PEOPLE_STATE_DIR`/`PEOPLE_JOBS_DIR`, and choose `PEOPLE_GITHUB_TARGET=production`.
The public example defaults to production targeting with **github_api + batch**.
An ordinary run includes publication; use `--dry-run` or `--stop-after poster_ps1`
to review first. Private `.env` files are never included in the release.

## Verification boundary

Clone-free-default follow-up on 2026-10-14: **476 passed, 4 skipped**, with
20 existing Pillow deprecation warnings. Regression coverage verifies the
no-settings API/batch defaults, explicit CLI/environment full-clone fallback,
CLI override of old configuration, matching public-example defaults, and no
automatic cloning after an API access failure.

Initial release preflight on 2026-10-14: **472 passed, 4 skipped**, with 20 existing
Pillow deprecation warnings. Run from the repository root:

```powershell
.\create_people_posters\.venv-rembg\Scripts\python.exe -m pytest create_people_posters/tests tests -q -p no:cacheprovider
```

### Production trials on 2026-10-14

After the private sandbox passed, the maintainer explicitly approved two
production trials against all seven image repositories on `master`:

- Chae Soo-bin (`1466233`): all seven missing styles were generated with
  BiRefNet Portrait and published. All seven README workflows succeeded, all
  seven downloaded images matched the prepared SHA-256 hashes, and each image
  commit added only the expected file. Replaying publication made zero writes.
  The retained job used about 52.08 MiB, including verification downloads.
- Mixed batch: Andrew Fung Chih-Chiang (`52569`), BoA (`1138821`), and
  Chae Soo-bin (`1466233`) were complete and skipped. Naravit Lertratkosum
  (`3028903`) was missing, so only his seven styles were generated and published.
  All 21 pre-existing image blob hashes stayed unchanged. The seven new image
  hashes, single-file commit scopes and successful README workflows were verified.
  Publication replay made zero writes. A fresh run of the same four-person list
  skipped everyone, downloaded zero images and stopped before rendering/publishing.
  The retained publication job used about 46.30 MiB.
- Both published jobs passed a future-retention cleanup preview without deleting
  images. Verification downloads are included in their cleanup catalogs. Durable
  reports remain outside disposable jobs under `config/state/trials/`.
- Existing clones and legacy staging were untouched. Generation, publication,
  partial-failure recovery, idempotency and retention have now been exercised
  live; Linux/macOS model execution and new grayscale DDColor inference still
  require deployment-specific validation.

The community and maintainer defaults now use `github_api` / `batch`.
To select the full-clone fallback, set
`PEOPLE_PUBLISH_MODE=local_git` and `PEOPLE_WORKSPACE_MODE=persistent`; existing
clones and legacy checkpoints remain available. The equivalent one-run override
is `python orchestrator.py --publish-mode local_git --workspace-mode persistent`.
Full clones can consume hundreds of gigabytes; this fallback is not selected
automatically. The separate online
[Adobe rollback snapshot](https://github.com/Kometa-Team/Defaults-Image-Creation/tree/adobe-express-snapshot-2026-10-14)
is preserved.

### Live sandbox validation on 2026-10-14

The explicit `live-20261014` run **passed** against seven newly created private
`bullmoose20/kometa-people-sandbox-STYLE` repositories. Their branch is `master`;
the code repository remained on `main` at `b6918cd`, with no new code commit/push.

- First attempt: four actual image commits succeeded, three styles failed at
  the intentional sandbox-only fault, and no README workflow was dispatched.
  All unpublished files were retained.
- After closing/reopening SQLite and inventory state: exactly three additional
  image commits completed the batch; the first four confirmed image commits
  were not recreated. All seven README dispatches were accepted.
- All seven actual GitHub README workflow runs completed successfully, and each
  generated README included the published person. Unrelated sentinel files
  survived both image and README commits.
- Re-running the identical batch made **zero GitHub mutations**, including zero
  commits and zero README dispatches.
- Downloading all seven published images verified exact SHA-256 equality with
  their prepared local bytes.
- Cleanup dry-run retained the files; applying zero-day retention **inside this
  sandbox process only** removed completed job images. Models, original validation
  sources outside the sandbox job, receipts, SQLite and manifests survived.
- All seven production branch heads were identical before and after the test.
  Private test repositories and their image/workflow commits remain online for
  inspection. No production repo, existing clone or legacy staging was changed.
- Updated full automated suite: **472 passed, 4 skipped**, with 20 existing Pillow
  deprecation warnings. The original platform limitations below still apply;
  at this stage, actual API publication and README dispatch had been proven in
  the private sandbox. The later production trials are recorded above.

The durable local report is `config/sandboxes/live-20261014/report.json`, with
workflow-run links, hashes, mutation counts, cleanup results and before/after
production refs. `provisioning.json` lists the seven created private repos.
At the sandbox stage the private `.env` still selected `local_git` / `persistent`;
the later production trials and community default change are recorded above.

### Local validation on 2026-10-14

- Full suite: **433 passed, 4 skipped**, with 20 pre-existing Pillow getdata
  deprecation warnings. Command from the repository root:
  `create_people_posters/.venv-rembg/Scripts/python.exe -m pytest create_people_posters/tests tests -q -p no:cacheprovider`.
- Windows live generation: one TMDb person, using a validation-only alias, ran
  through download, classification, BiRefNet Portrait CPU and the existing
  PowerShell 7.6.6 / ImageMagick renderer. The renderer reported zero quality
  issues. All seven canonical outputs were verified as 2000x3000; transparent
  was RGBA, original was RGB JPEG, and the remaining styles retained their
  existing image modes and bytes.
- The real GitHub read-only publication preview reported one changed image
  for each of the seven `master` repositories. All receipts remained pending;
  no image publication or README workflow dispatch was performed.
- This job used about 37.22 MiB including canonical retry copies and logs;
  shared metadata/receipts for the seven libraries used about 34.51 MiB.
  Models, installed packages and pre-existing legacy staging/clones are excluded.
  These are measurements for this one-person test, not a general disk quota.
- The retained test job is `20261015T012302-8dd3a8a196b5` (UTC identifier), marked
  `validation_only`. It cannot be automatically resumed or published.
- The test photograph was already color: DDColor's no-input path ran, not new
  grayscale model inference. Real alternate-image recovery, Linux/macOS execution
  and production commit/README-dispatch behavior were not exercised at this stage.
  Subsequent live trials are recorded above. Their API/control paths are also
  covered by mocked tests. Windows junction cleanup protection passed;
  the ordinary symlink test was skipped because this account lacks that privilege.
- No production image repository was modified. No code commit, push, new branch,
  history rewrite, clone removal or legacy staging cleanup was performed.

Automated tests use mocked GitHub operations, including partial success, lost
responses, concurrent edits, Unicode, truncated trees, permissions and cleanup
faults. Normalizer parity tests compare exact bytes with the existing pipeline.
No production repository is modified by these tests. Normal pytest runs never
live-publish; the explicitly approved sandbox runner above exercises private
test repositories separately.
Cross-platform filesystem behavior and model/PowerShell execution must be
validated on each deployment platform; mocked tests do not prove those systems.

GitHub API references: [trees](https://docs.github.com/en/rest/git/trees),
[blobs](https://docs.github.com/en/rest/git/blobs),
[refs](https://docs.github.com/en/rest/git/refs), and
[rate-limit practices](https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api).

## Changed files

New implementation: `people_github.py`, `people_remote_inventory.py`,
`people_publication_state.py`, `publish_people_github.py`, `people_workspaces.py`.
The subsequent isolated live test adds `sandbox_people_github.py` and
`tests/test_people_sandbox.py`.

Integration: `orchestrator.py`, `tmdb_people.py`, `truncate_tmdb_people_names.py`,
`audit_people_images.py`, `find_and_download_missing_people.py`,
`scan_kometa_logs.py`, `prep_people_dirs.py`, `colorize_noncolor_ddcolor.py`,
`remove_bg_birefnet.py`, `sel_remove_bg.py`, `recover_edge_chops.py`,
`sync_people_images.py`, `create_people_poster.ps1`, `clean_people_config.py`.

Configuration/documentation: `.env.example` (clone-free batch defaults), private
ignored `config/.env`, `README.md`, `CLONE_FREE.md`, and the root
`../README.md` quick-start links/commands.

New tests: `tests/test_people_github.py`, `tests/test_people_workspaces.py`,
`tests/test_people_api_orchestrator.py`.

Ignored local validation inputs and jobs are not community input lists and are
not committed. Completed smoke-test jobs are marked `validation_only`, which
excludes them from ordinary resume selection and blocks accidental publication.
