# Diiivoy Jost migration

This standalone maintenance tool renders only `diiivoy` and `diiivoycolor`, using
the existing local transparent collection as a strictly read-only source. Normal
orchestrator runs are unchanged. No original photographs, source downloads, AI
inference, browser, PowerShell renderer, ImageMagick or destination clones are
used. The code stays on `main`; destination writes are fixed to these two targets:

- `Kometa-Team/People-Images-diiivoy@master`
- `Kometa-Team/People-Images-diiivoycolor@master`

The five other production image repositories are outside the migration transport
allowlist, even if ordinary publishing configuration names them. It cannot rename
branches, force-push, edit source PNGs or clean the source directory. Do not commit
private `.env`, inventories, generated images or credentials.

## Implementation audit

- `Renderer.render_styles()` shares `prepare_cutout()` and `diiivoy_styles()` with
  the normal renderer. It never calls `render_batch()` or requires an original
  JPEG. The ordinary seven-style API retains its other style code.
- `normalize_cutout()`, `shifted_cutout()`, `label_name()` and `output_path()` retain
  the approved normalization, placement, display-name and filename rules.
- Jost is the exact bundled static weight 260, preferred size 190px, with existing
  uppercase labels and long-name fitting. Migration rejects custom asset/font
  directory overrides and a changed approved font binary.
- JPEG encoding remains quality 100, chroma subsampling 0, RGB, 2000x3000. Existing
  `image_quality_findings()` is reused; no second quality-policy implementation.
- `RemoteInventory` supplies authoritative tree metadata and truncated-tree
  handling. Only the two target inventories are refreshed. Destination JPEGs are
  fetched only by `--compare`, capped at 100 sampled people.
- `PublicationState` supplies immutable prepared plans, baseline hashes, per-file
  receipts and README records. `Publisher` supplies Git Data API commits, bounded
  retries, non-forced ref updates, concurrent-edit detection and verification.
  Its seven-style `prepare()` is deliberately not used.
- `MigrationTransport` restricts repository, branch, API operation and every tree
  update to the immutable manifest's validated paths and blobs. Its default mode
  rejects all mutations. Normal publisher/inventory modules are not rewritten.
- `reject_links()`, atomic JSON and process-liveness helpers are reused from Phase
  2. Migration workspaces and state are separate from ordinary jobs and receipts;
  existing `Workspaces` seven-style completion semantics are not weakened.

## Configuration

Install the normal People Posters Python requirements. No new dependency is
required. Set the existing local source folder in private `config/.env`:

```dotenv
JOST_MIGRATION_TRANSPARENT_DIR=C:/Users/YOU/Kometa-People-Images/transparent
JOST_MIGRATION_BATCH_SIZE=50
JOST_MIGRATION_AUTO_CLEANUP=true
JOST_MIGRATION_RETENTION_DAYS=3
JOST_MIGRATION_MAX_GIB=10
```

Unix paths such as `/srv/people/transparent` are supported. The source can be an
ordinary directory, not a Git checkout, with `INITIAL/Images/NAME.png` files.
Symlinks/reparse points, traversal, overlapping source/workspace roots and
ambiguous NFC/case filenames are rejected. Repeated spaces are preserved as
distinct historical filenames, not collapsed into a person-name alias. Non-PNG files are
listed as ignored; mislabeled or corrupt PNGs fail validation without changing
the source. Source hashes are checked again before rendering, review and publish.

Authentication uses the existing `GITHUB_TOKEN`/`GH_TOKEN` or `gh auth token`
mechanism. Read-only inventory/comparison needs access to the two repositories;
publication needs Contents:write and README dispatch needs Actions:write. Ordinary
`PEOPLE_BRANCH`, repository mapping and sandbox overrides cannot retarget this
maintenance command.

## Inventory and sample

Run commands from `create_people_posters/`, using your activated Python venv.
PowerShell shell example (it launches Python, not the legacy renderer):

```powershell
python migrate_diiivoy_jost.py --scan --sample 25 --transparent-dir 'C:/Kometa-People-Images/transparent'
```

Unix shell example:

```bash
python migrate_diiivoy_jost.py --scan --sample 25 --transparent-dir /srv/people/transparent
```

This hashes every local PNG, inventories both remote trees without JPEG downloads,
and returns a migration ID. Its immutable manifest records the full collection,
selection, source hashes, exact target paths, initial blobs/heads, renderer and
font fingerprints. The deterministic sample favors short/long names, accents,
punctuation, trailing digits, mixed capitalization and letter distribution. Alpha,
edge and unusual-crop metrics are inspected after decoding the sample; do not
claim the source photographs' original light/dark backgrounds are known from
transparent PNGs alone. Add further reviewed samples if the report lacks a needed
visual case.

A strict scan stops at ambiguous source names. To explicitly retain an audit
record and exclude *all* colliding entries, without choosing one or renaming files:

```bash
python migrate_diiivoy_jost.py --scan --sample 25 --exclude-ambiguous
```

The resulting manifest marks those source conflicts and excludes them from
selection. Resolve the ambiguity explicitly in a later migration; the tool never
edits the source repository. Unknown flattened JPEG font provenance is not guessed
from filenames, timestamps or the code's Jost adoption date. Classifications are
`confirmed_pre_jost`, `confirmed_jost`, `unknown`; pre-Jost remains zero without
conclusive records. Current migration receipts or exact regenerated-blob equality
can prove Jost. Verified migrations are not repeatedly rebuilt on subsequent scans
when the source, remote blob and renderer fingerprint still match. A renderer
change makes a new scan select those images again; an old receipt cannot certify
the new renderer's output.

## Render and inspect

Substitute the actual ID printed by scan:

```powershell
$migration = 'MIGRATION_ID'
python migrate_diiivoy_jost.py --migration $migration --render --limit 25
python migrate_diiivoy_jost.py --migration $migration --compare --limit 25
python migrate_diiivoy_jost.py --migration $migration --dry-run --limit 25
python migrate_diiivoy_jost.py --migration $migration --status
```

```bash
migration='MIGRATION_ID'
python migrate_diiivoy_jost.py --migration "$migration" --render --limit 25
python migrate_diiivoy_jost.py --migration "$migration" --compare --limit 25
python migrate_diiivoy_jost.py --migration "$migration" --dry-run --limit 25
python migrate_diiivoy_jost.py --migration "$migration" --status
```

Only two JPEGs per valid person are written, one person in memory at a time.
The report under `config/migrations/jost/reports/ID/index.html` is local HTML,
not a hosted service. It includes checkerboard source previews, links to the
unchanged full-resolution local PNG, old/new posters, outlined text regions,
full-resolution text crops, image dimensions, hashes, renderer/font identity,
source/normalized/shifted alpha bounds and warnings. A flattened old JPEG has no
authoritative foreground mask; reported bounds come from the source PNG.

Each input is tested for normalization idempotence and pixel-identical selective
outputs from equivalent raw/normalized inputs. The documented high-margin gray
intermediate behavior is preserved, including for diiivoycolor-only calls.
Earlier raw-cutout linkage remains unverified for historical PNGs: visual review
is mandatory even when mathematical normalization equivalence passes. Entries
without exact equivalent-input results, or with noncanonical source dimensions,
need their own explicitly reviewed report
before publication. There is no automatic placement correction or extra shift.

Rendering and publication do not silently rescan. `--resume` means render the next
bounded pending group from the saved manifest; it never publishes. `--failed-only`
retries failed renders, not source/fingerprint conflicts. Source or renderer
changes require reconciliation with a new scan rather than overwriting receipts.
Published/verified work is retained in SQLite across restarts. Status exports
detailed `progress.json`, counts, disk use, timing and per-destination state.

## Controlled publication

Production publishing is a separate, explicit action. First inspect the HTML and
all warnings. The report prints the SHA-256 of its `review.json`; supplying that
token asserts visual approval. Approval binds the migration, renderer, source and
sample output hashes. A stale token cannot approve changed files.

```powershell
python migrate_diiivoy_jost.py --migration $migration --publish --limit 25 --batch-size 25 --confirm $migration --reviewed 'REVIEW_SHA256'
```

```bash
python migrate_diiivoy_jost.py --migration "$migration" --publish --limit 25 --batch-size 25 --confirm "$migration" --reviewed REVIEW_SHA256
```

These commands are **not executed by setup, scan, render, report or tests**.
Omit `--publish`/use `--dry-run` for a non-mutating preview. Default invocation is
status. Normal limit/batch default is 50 people, not a whole-library run. A full
collection needs a new scan without `--sample`, an initial representative render
and review for that migration, then explicit controlled invocations. Passing a
large `--limit` is a deliberate multi-batch action, not an automatic continuation.

Each repository is tracked independently; successful writes survive a failure in
the other repository. Re-run the same publish command to resume. Plans seed the
scan-time baseline before any write, recheck the remote tree, preserve unrelated
files/commits, and reject unexpected destination changes. Already matching blobs
need no commit. Missing destinations may be created only when the saved baseline
also says missing; a new remote file appearing meanwhile causes a conflict.
After verified commits, existing README workflows are dispatched per controlled
publication unit, not per image, using the normal README policy.

## Storage and cleanup

```text
config/migrations/jost/
  state/                 SQLite, inventory cache, publication receipts
  reports/ID/            progress, review JSON, permanent sampled images/crops
  jobs/ID/manifest.json   immutable worklist and initial rollback blobs/heads
  jobs/ID/diiivoy/        generated INITIAL/Images/*.jpg
  jobs/ID/diiivoycolor/   generated INITIAL/Images/*.jpg
```

The source root and migration root must be disjoint. There are no hard links or
symlinks. Work is serialized by a PID-aware lock. A disk budget/free-space check
stops further rendering instead of deleting unpublished images to make room.
The report sample is capped at 100 people; normal reports use 25. A continuous
low-disk run can explicitly set retention to zero to clean each fully verified
batch immediately. The default three-day retention can reach the disk budget;
the tool then stops and asks for cleanup/configuration review instead of deleting
unpublished data. Permanent sample
copies/crops consume disk independently of temporary jobs and are retained for
audit; they are never an implicit whole-library mirror.

```bash
python migrate_diiivoy_jost.py --migration MIGRATION_ID --cleanup
python migrate_diiivoy_jost.py --migration MIGRATION_ID --cleanup --apply
```

Cleanup defaults to dry-run, honors retention, requires verified receipts for both
destinations, and deletes only the exact catalogued generated JPEGs after checking
their hashes and paths again. It never recursively deletes a job/source directory.
Unpublished, failed and edited outputs are retained. Interrupted cleanup can
resume. Manifests, database, receipts, reports and unrelated files remain. Approval
can still be checked against permanent sampled copies after verified job cleanup.

## Rollback

Previous blob SHAs and remote commit baselines are retained before replacement.
Rollback constructs **new Git commits**, reusing those blobs directly without
downloading them or cloning repositories. A destination created by migration is
removed if its original baseline was absent. Only paths still equal to the
migration output are eligible; intervening content edits block rollback. Commit
intents and reachability distinguish images actually replaced by this migration
from pre-existing identical Jost files; unchanged matches are not rolled back.

```powershell
python migrate_diiivoy_jost.py --migration $migration --rollback --dry-run --limit 25
python migrate_diiivoy_jost.py --migration $migration --rollback --limit 25 --confirm "rollback:$migration"
```

```bash
python migrate_diiivoy_jost.py --migration "$migration" --rollback --dry-run --limit 25
python migrate_diiivoy_jost.py --migration "$migration" --rollback --limit 25 --confirm "rollback:$migration"
```

Rollback is explicitly approved, bounded, verified and resumable, including a
crash after a ref update and pending README dispatch. It never force-pushes or
automatically undoes successful work after an unrelated failure. A rolled-back
migration is not silently republished; reconcile with a new scan.

## Validation record

Ordinary automated tests mock GitHub and never mutate production. The selective
renderer is compared pixel-for-pixel to the normal renderer for raw, normalized,
high-margin and edge portraits. Source, path, collision, corruption, manifest,
approval, allowlist, partial publication, interruption, resume, rollback and
cleanup tests are in `tests/test_jost_migration.py`. Run the entire suite with:

```powershell
.\.venv-rembg\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
```

### Local validation, 2026-10-15

Initial non-destructive validation, migration `20261015T064830-9eff74aeaf00`:
at this stage no production writes, implementation commits or pushes had been
performed. The source collection was read in place; it
was not cloned, normalized, renamed or otherwise edited.

| Inventory | Result |
| --- | ---: |
| Local transparent PNGs hashed | 15,326 |
| Existing source bytes | 78,356,593,738 (72.98 GiB) |
| Matching destinations per style | 15,326 |
| Potential destination rebuilds | 30,652 |
| Confirmed pre-Jost / confirmed Jost / unknown at scan | 0 / 0 / 30,652 |
| Remote destinations without a local source | 4 paths, 2 people |
| Ambiguous source collisions | 0 |
| Sample selected / validated / failed | 25 / 24 / 1 |
| New validated JPEGs | 48 |
| Dry-run replacements / creates / conflicts | 48 / 0 / 0 |
| Production publications | 0 |

Final full-suite verification on this implementation: **574 passed, 5 skipped**
in **389.12 seconds**, with 20 existing Pillow deprecation warnings from
`edge_chop.py`. No production GitHub calls were used by the automated tests.
The current run includes the Windows Unicode-console regression and the
cross-migration renderer-fingerprint/receipt safeguard. Its log is retained at
`config/renderer-comparison/pytest-phase4-current.log`. No source-code edits were
made after that run; only this validation record was completed.

Chae Soo-bin and Naravit Lertratkosum are present in both destinations but missing
from this local transparent snapshot. They are recorded as missing sources and
remain untouched. Flattened existing JPEGs do not prove font provenance; none of
the 30,652 existing local-source destinations was labeled pre-Jost just by age.

The local-only report is
`config/migrations/jost/reports/20261015T064830-9eff74aeaf00/index.html`.
Its review JSON, old/new full-resolution posters, highlighted text previews and
five inspection contact sheets remain local and ignored by Git. All 504 relative
report links were checked and exist. The report includes the blocked sample.

All 24 valid sources were already 2000x3000 RGBA. Normalization was idempotent and
both selective outputs were pixel-identical from the source and its normalized
equivalent. A measured repeat run regenerated all 48 JPEGs with exactly matching
SHA-256 hashes, checking source hashes before and after. Visual inspection of all
24 old/new pairs found no unexpected subject-placement changes; the typography
change is intentional. Fine hair, boundary portraits, short/long names, accents,
punctuation and trailing disambiguation digits are represented. Adrian
Grunewald's existing top-edge/head-crop warning is retained rather than silently
corrected. Earlier raw-cutout linkage and the original photographic backgrounds
cannot be verified from these PNGs. The initial real sample has no high-margin
case; that legacy behavior is covered by synthetic pixel-parity fixtures.

The sample's Korean label (`\ubc15\uc9c0`) is blocked because bundled Jost lacks
the required glyphs. A whole-manifest filename/glyph audit found **10 affected
labels**, listed with exact Unicode names and characters in
`config/migrations/jost/validation/jost-glyph-coverage.json` (local only).
This includes some Vietnamese/Yoruba letters and a modifier apostrophe, not only
CJK names. There is no silent transliteration, fallback font, source rename or
placeholder glyph. These entries need a separately approved display-alias
solution before they can be migrated under the Jost-only policy. The other 15,316
labels pass this character-coverage check, not a full image validation. The
Windows CLI now configures UTF-8 output so an unsupported Unicode label reports
its real font error instead of a console-encoding exception.

Released-renderer comparison against commit
`c56145da4745c314c6698346d8cf8c61c799fbdb` checked raw, normalized and high-margin
inputs: all six generated styles matched pixel-for-pixel in all three cases
(18 comparisons); selective outputs also matched (6 comparisons). The seventh
style, original-photo passthrough, is not generated or changed here. Evidence is
in `config/migrations/jost/validation/shared-renderer-parity.json`.

The 24-person repeat-render benchmark took **40.86 seconds**, averaging **1.70
seconds/person** for both styles, equivalent-input checks, JPEG encoding and QA.
At that measured rate, 15,316 font-supported people represent roughly **7.24
hours** of render/encode/QA work. This benchmark reused cached input data, checked
existing validated files and encoded repeats in memory; it excludes initial
hashing/inventory, disk writes, startup, manual review and all publishing. It ran
alongside tests/report generation. It is **not an end-to-end completion ETA**.
Production publishing time remains unmeasured because it was not authorized.
The read-only publication preview itself took 3.05 seconds for 24 people.
Benchmark details are in
`config/migrations/jost/validation/sample-repeat-benchmark.json`.

The 48 generated JPEGs occupy 149,176,683 bytes (about 142 MiB). At the sample's
average, a 50-person batch is about 296 MiB and retaining every pair would be
about 89 GiB, in addition to the existing source collection. Temporary job data
currently uses about 158 MiB including its full manifest; permanent comparison
artifacts use about 413 MiB, plus roughly 15 MiB of state. For a streaming
low-disk rebuild, explicitly review setting `JOST_MIGRATION_RETENTION_DAYS=0`
before approved publication so verified batches become immediately eligible.
With the default three-day retention and 10 GiB budget the tool stops when full;
it does not discard unpublished work. Cleanup preview currently selects no files.
This one-off historical maintenance source is **not** an additional clone/download
requirement for the normal clone-free community orchestrator.

Replacing JPEGs adds new Git blobs while retaining historical ones for rollback.
The sample's roughly 89 GiB projection also signals substantial additional remote
Git storage if the entire collection is changed; actual compression/deduplication
will vary. Clone-free publishing avoids client clones, but does not shrink server
history. This migration is not online repository-size cleanup and performs no
history rewrite. Review that storage impact before approving a full rollout.

### Published reference batch

After visual approval, the operator ran the following historical command from
`create_people_posters/`. All 24 people (48 JPEGs) were published and verified,
and both README workflows were dispatched in 140.82 seconds:

- [Diiivoy commit a536895](https://github.com/Kometa-Team/People-Images-diiivoy/commit/a5368956fc4736a923ed4b1a432ffc8662b7cfbe)
- [Diiivoycolor commit a343bad](https://github.com/Kometa-Team/People-Images-diiivoycolor/commit/a343badc119e7dfd31dec55fc74b0209c2dad41e)

This is an audit example, not a command for fresh installations: its manifest,
review JSON and SQLite receipts exist only in the original local workspace.

```powershell
.\.venv-rembg\Scripts\python.exe migrate_diiivoy_jost.py --migration 20261015T064830-9eff74aeaf00 --publish --limit 24 --batch-size 24 --confirm 20261015T064830-9eff74aeaf00 --reviewed 7599c4a55ead56cd035c3f735c5106ea7e8c6a56c38e8504dcf8a08882a0f019
```

On Unix, substitute the activated environment's `python` for the Windows Python
path; the remaining arguments are identical. This sample manifest cannot expand
into a whole-collection migration on resume. After explicit sample approval and
successful controlled publication, a separate full scan without `--sample`, its
own reviewed report, and explicitly bounded render/publish commands are needed.
The reference batch's visual review is complete. Unsupported display labels and
missing local people remain outstanding; the approved unattended rollout below
holds those cases for its final report rather than requesting per-person input.

## Unattended approved rollout

After the sample was reviewed and published, the operator explicitly approved a
full rollout in 50-person batches with immediate verified-file cleanup. The
private `.env` now uses `JOST_MIGRATION_RETENTION_DAYS=0`; the public example keeps
the conservative three-day default. The initial image-rollout approval did not
include code commits or pushes. A later explicit request authorized publication
of this tooling to the code repository's `main` branch.

`run_jost_migration.py` is a standalone controller, not a Codex agent loop. It
uses no OpenAI API, model credits, background-removal inference or original photo
downloads. Local CPU, disk, network and GitHub API usage still apply. The machine
must remain running and awake. It does not need an active chat to process images.
The operator launches the job manually; setup and documentation commands do not
start a worker. Keep that PowerShell window open. To retain console output, append
`2>&1 | Tee-Object -FilePath .\config\migrations\jost\state\rollout.log` to the
start command below. On resume, use `Tee-Object -Append` to preserve that log.
The operator can return with confusing output or request review of the saved
final report; the full report need not be pasted into chat.

Controller verification: the migration test-file run passed **61 tests with 1
skipped**; a subsequent focused run passed both the expanded stop/resume check and
the newly added changed-source/continue check. Separate controller cases cover
verified-reference reuse, cleanup, unsupported glyphs, noncanonical holds and
remote-conflict quarantine without overwriting remote edits. The earlier
574-test project result predates the controller. Syntax checks and
`git diff --check` also passed; the publication verification record below tracks
the later full-suite run with the controller included.

### New installations and future migrations

Local manifests, review artifacts, image outputs, credentials and SQLite state
are deliberately not published with this code. Do not reuse the historical IDs
or approval hashes from the validation record on another installation. Configure
your own source folder and credentials, then follow **Inventory and sample**,
**Render and inspect** and **Controlled publication** above. Review and publish
your own representative sample before starting an unattended full run.

Back up an active run's `state/`, immutable `jobs/*/manifest.json` files and
approved report artifacts separately. Retain unpublished generated JPEGs for
retry. A fresh clone of the code alone does not contain the receipts and previous
blob mappings needed to resume or automatically roll back that historical run.
Do not put private credentials or the image collection into the code repository.

Substitute the sample migration ID from your scan and the review hash from your
approved comparison report:

```powershell
$sampleMigration = 'YOUR_PUBLISHED_SAMPLE_MIGRATION_ID'
$sampleReview = 'YOUR_APPROVED_REVIEW_SHA256'
python -u run_jost_migration.py --start --approved-sample $sampleMigration --reviewed $sampleReview --confirm-full-rollout --batch-size 50
```

```bash
sample_migration='YOUR_PUBLISHED_SAMPLE_MIGRATION_ID'
sample_review='YOUR_APPROVED_REVIEW_SHA256'
python -u run_jost_migration.py --start --approved-sample "$sample_migration" --reviewed "$sample_review" --confirm-full-rollout --batch-size 50
```

The unattended controller explicitly uses zero-day retention for verified job
JPEGs, independently of the conservative single-batch CLI default. Permanent
comparison artifacts, rollback records and all unpublished/held files remain.

This explicitly creates a **new full manifest**, excludes recorded ambiguous
sources, and skips proven already-published Jost images. Reuse of sample approval
is opt-in and requires identical renderer fingerprints, identical sampled source
hashes, both verified publication receipts, matching current scan baselines and
the original report hash. Sample row numbers are mapped by exact destination and
source hash, not assumed equal across scans. Approval cannot bypass the two-repo
allowlist or independently required review of a new noncanonical input.

The controller renders, validates, publishes, verifies and cleans each bounded
batch before proceeding. It does not repeatedly retry corrupt PNGs or unsupported
glyphs. Source changes detected during rendering, missing glyphs, corrupt inputs
and noncanonical compositions are held for review. A conflicting publication
unit, up to 50 people, is quarantined with its partial receipts and generated
files; subsequent independent units continue without overwriting that conflict.
README refreshes are attempted for partial successes. Only fully verified units
can be cleaned. Temporary failed/held images count toward the disk budget and are
never deleted merely to keep the job moving.

Transient publication failures get bounded backoff. Persistent authentication,
network, disk, renderer-integrity or approval failures stop the job with a saved
error. These are global safety constraints, not silently skipped images. A change
to an approved reference source invalidates inherited approval. No source PNGs,
Git history or other five image repositories are edited.

Status is readable without acquiring the worker's exclusive lock:

```powershell
.\.venv-rembg\Scripts\python.exe run_jost_migration.py --status
.\.venv-rembg\Scripts\python.exe run_jost_migration.py --stop
.\.venv-rembg\Scripts\python.exe -u run_jost_migration.py --resume --confirm-full-rollout --batch-size 50
```

`--stop` requests a stop between batches, not a forced interruption of a ref
update. Resume uses the saved full manifest and approval, never silently rescans
an existing worklist. If the very first scan was interrupted before a manifest
existed, an explicit `--start` is required again. Only one worker may run.

The compact job record is `config/migrations/jost/state/rollout.json`. Once the
manifest exists, the final review queue is
`config/migrations/jost/reports/FULL_ID/problems.html` and `problems.json`, covering
held/failed people, missing local sources, quarantined units, README problems and
nonblocking warnings on published images. Generated held JPEGs are linked in place
without copying the whole collection. Reports and rollback records persist.

### Future rebuild profiles

The same lifecycle is appropriate for later template, font and gradient rebuilds:
immutable worklist, approved visual reference, source/renderer/asset fingerprint,
bounded rendering and publishing, independent receipts, verified cleanup and an
end-of-run review queue. The existing renderer fingerprint already includes the
artwork files, so changing a Diiivoy gradient/template invalidates old receipts
instead of incorrectly skipping those outputs. A new visual reference must be
approved for the changed renderer.

The currently implemented maintenance profile remains **Diiivoy/Diiivoycolor with
approved Jost 260/190px**. Other styles are not silently supported or authorized:
they need explicit selective render/source contracts, because some use original
photographs rather than transparent PNGs. Do not broaden this profile's strict
repository allowlist to turn a two-style approval into seven production writes.

## Publication verification

Before publishing this tooling, the full People Posters test suite, including
the unattended controller, completed with **580 passed, 5 skipped** and 20 existing
Pillow deprecation warnings in **950.64 seconds**. The local log is
`config/renderer-comparison/pytest-migration-prepublish.log`. Only documentation
was edited after this run. Staged changes passed `git diff --cached --check`.

The publication contains source, tests, documentation and `.env.example`, not
private `.env`, credentials, source images, generated JPEGs, runtime manifests,
reports or databases. The operator's running migration is independent of this
code publication; its renderer/artwork fingerprint was unchanged by staging.
