# English canary infrastructure readiness - installation not authorized

Implementation and local tests only. PR #12 remains draft. No App, environment,
permission, private repository, artifact upload, active workflow or target ref/PR
was created. Production publication, merging and PowerShell replacement remain
unauthorized. The [setup checklist](STAGING_AUTHORIZATION_CHECKLIST.md) is the
concrete request for later external-action authorization.

## Immutable scope and selected approval model

Option A remains accepted by the [model decision](../bulk/evidence/english-canary/explicit-user-model-decision-20261018.json):
exactly bullmoose20 (12549033), YozoraXCII (96386153), chazlarson (3865541),
meisnate12 (1631064), badja-dev (180163201). One explicit native approval per fresh
deployment, including self-approval; any authorized reviewer may approve another
eligible initiator. Outsiders cannot approve merely because they have write access,
authored a PR or supplied inputs. No team mode or organization Members lookup.
Actual dispatch rights are GitHub's source repository permissions, not granted here.

| Binding | Identity |
| --- | --- |
| Original ZIP | 7,256,318 bytes; `97d82b19eb237908cbd4657c67ca16eefe089b5a6d6a5f9e1690fda6cdb597c5` |
| Preparation | `bc7657363fb253bb41965b56bd73ef650be5dc9606bfff486ac8aa76eb2d77be` |
| Individual seven-image acceptance | `139ed5b73c5ee555488163e024c85e33850207a401aa65b546d87c6b1a7f3919` |
| Accepted target master | `59e49ede8d41ac5991f971e66e93af596402329a` |

No image is regenerated/re-encoded/repacked. Existing Gate E/D evidence, renderer,
font/layout/validation identities, individual decisions, old-image backups and
published difference metrics remain immutable. Exact destinations:
`based/Book.jpg`, `decade/2020.jpg`, `franchise/Death in Paradise (2011).jpg`,
`genre/Action & Adventure.jpg`, `genre/Splatter.jpg`, `year/2020.jpg`,
`year/best/2020.jpg`. Parent Year output remains the accepted child's dependency.

## Supported environment verification, with explicit evidence limits

The documented environment GET exposes reviewer IDs, prevent-self-review and branch
selection; it does not expose the UI administrator-bypass checkbox. The old helper
incorrectly required a nonexistent readback field. The current code does **not**
invent an API field or interpret absence as false.

Two complementary gates are now required before either App token:

1. Machine checks: exact five User identities, prevent-self-review false, main branch
   only, exact live environment snapshot, protected and unchanged source main,
   reviewed implementation A/current authorization B, expiry, actual native approval
   history and exact run/attempt. Reruns are refused.
2. Auditable setup process: a source administrator inspects GitHub's documented UI,
   confirms bypass disabled and trusted source code protection, retains a redacted
   private screenshot/settings record, hashes it, and finalizes a setup receipt.
   The receipt must identify that admin/account ID, environment ID, API snapshot,
   implementation A, checks/time/expiry (<=24 hours) and retained hosted-test report.
   Source API rechecks the inspector's actual admin role. Missing, changed, false or
   stale evidence stops. Its expiry bounds the staging authorization and is rechecked
   before each write. `hidden_setting_machine_verified` must remain **false**.

This is a manual attestation for the hidden setting, not machine proof or a GitHub
signature. Hashes make the record tamper-evident, not truthful by themselves. Native
GitHub enforces the configured setting; a trusted admin/operator must inspect it.
No software claim is made that a later unexposed checkbox change can be detected.
Observable drift stops; administrators remain able to change repository settings.
Fresh per-run reviewer acknowledgement is therefore required, with exact comment:

`english-canary-stage authorization=<auth SHA> setup=<receipt SHA> run=<run ID> attempt=1 setup-reviewed`

The read-only verify job displays it. An authorized reviewer reads the receipt and
scope, uses **Review deployments**, selects only `english-canary-stage`, supplies
that exact comment and clicks **Approve and deploy**. A run released by bypass,
missing approval, wrong reviewer or unbound comment cannot mint either App token.
This secondary check does not substitute for configuring native no-bypass protection.

Supported references: [environment configuration](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments),
[review and bypass behavior](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/review-deployments),
[read-only approval history](https://docs.github.com/en/rest/actions/workflow-runs).

## Hosted verification procedure - not executed

Install the separate `english-canary-approval-check.yml` template only after explicit
infrastructure authorization. It uses the same protected environment and a harmless
environment-only sentinel secret `ENGLISH_CANARY_APPROVAL_PROBE`; it references no
artifact or writer App key/token. Run this exercise **before configuring App keys**.

- For each of the five maintainers, dispatch a fresh run on main and explicitly
  approve their own pending deployment; comment `english-canary-approval-check`.
- Dispatch another fresh run and have a different maintainer approve it.
- If an existing eligible outside writer exists, let that writer dispatch and a
  maintainer approve. Never grant new dispatch access just to manufacture this test.
  If none exists, record not-applicable and recheck the complete source collaborator
  inventory; the helper rejects that exception if an outside writer actually exists.
- While a probe is pending, use an outside-roster read-access account to attempt
  approval through native UI/API; retain GitHub's denial/no-approval-rights evidence.
  This negative outcome is an administrator-reviewed hosted report, not a local mock.
- Verify the admin UI has bypass disabled and offers no permitted bypass path.
  Do not enable bypass merely to test it. Verify only main can deploy; record a
  rejected non-main probe under separately authorized test setup if needed.
- The sentinel must be absent before the protected job and available after explicit
  review; never print its value. Probe reports bind actual native approval history,
  source SHA/environment snapshot and zero target credentials/writes.
- Retain probe run IDs, reports, negative-test/settings evidence privately plus a
  verified offline copy. A source admin signs off the hash of the aggregate report.

The helper re-fetches actual successful probe runs and approval histories, requires
all five self approvals plus cross approval at implementation A, and verifies source
repository, path, main, attempt and exact reviewer IDs/comments. Outside-positive
coverage is conditional as above. Negative UI outcomes and hidden bypass remain
explicitly human-reviewed evidence. Local tests simulate these APIs; CI is **not**
a successful GitHub-hosted environment approval exercise. No such exercise has run.

## Private artifact delivery implemented

Selected mechanism: original ZIP committed unchanged as a regular Git blob at
`canary/english-canary-review-bundle.zip` in proposed private repository
`Kometa-Team/english-canary-artifacts`. No repository or upload exists yet. This
supersedes the earlier Actions-artifact recommendation: a 7.26 MB plain Git blob
avoids an extra ZIP wrapper, producer workflow, automatic artifact expiry and storage
adapter complexity. Public prerelease transport is removed from executable code.

A distinct artifact-reader App gets **Metadata read + Contents read**, installed only
on that holding repository. Its short-lived installation token is minted after native
approval and setup preflight, then revoked by the pinned token action. The target
writer App is unchanged and never reads the private repository. No PAT fallback.

The adapter is GET-only at fixed api.github.com routes, with redirects and proxy/env
credential fallback disabled, bounded JSON/base64 decoding and no token/URL logging.
It checks token repository scope, numeric repository ID/privacy, pinned commit/tree,
exact path/mode/blob, original ZIP size/SHA-256 and Git blob identity; then independently
validates the unchanged archive inventory, seven JPEGs, accepted renderer/context and
individual decisions. Missing/stale/renamed/unavailable data stops before writer mint.

Private Git hosting fits GitHub Free's private repositories; this does not require
paid private-environment reviewer features because approval stays in the public source
repo. The ZIP is below GitHub's 100 MiB regular-file limit; no LFS or Actions-artifact
storage service is needed for it. No paid-plan upgrade is assumed. Normal account
API/runner/hosting policies still apply; private organization creation restrictions
must be checked by an owner. See [plans](https://docs.github.com/en/get-started/learning-about-github/githubs-plans),
[large-file limits](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github),
[blob API/read permissions](https://docs.github.com/en/rest/git/blobs).

Require at least 90 days of remaining retention at staging, a verified access-controlled
offline backup and a separately approved deletion policy. No automatic deletion or
expiry is implemented. Deleting a file commit does not purge Git history; after all
rollback/audit obligations end, an owner may separately authorize deleting the dedicated
holding repository and securely retiring copies/credentials. Never publish it, change
visibility, use LFS, or put the private ZIP/UI screenshots in public source artifacts.

## Exact future setup and permission boundaries

All actions below require **separate external-action authorization**.
`bullmoose20` was verified source write/target maintain, not source admin. YozoraXCII,
chazlarson, meisnate12 and badja-dev were verified source admins/organization owners.

1. **Organization owner / source admin:** protect source main and establish reviewed
   workflow/runtime changes (reviewed PRs, no force/deletion, controlled bypass).
   Source main currently reports `protected:false`; preflight now stops on that state.
   No source rules or target permissions were changed. Record exact adopted controls.
2. **Source admin:** Settings > Environments > New environment > english-canary-stage.
   Enable Required reviewers; select exactly the five User entries. Leave Prevent
   self-review unchecked; uncheck Allow administrators to bypass configured protection
   rules; Save protection rules. Selected branches and tags > Branch > main only;
   no tag/wildcard. Add only the harmless probe sentinel for the first exercise.
3. **Source writer and authorized merger:** prepare a separately reviewed minimal
   infrastructure-only PR using `deployment-files.json`. It maps two inactive templates
   into .github/workflows, includes required shared runtime, both adapters, exact accepted
   metadata and disabled configs. Copying only YAML is insufficient. Do not merge PR #12.
   Record the installed full implementation commit **A**, manifest and normalized-LF
   file hashes. All staging/intake/authorization gates remain false.
4. **Five reviewers / source admin:** perform hosted verification above at A. Retain
   evidence and prepare a fresh setup-verification receipt; no false hosted success.
5. **Organization owner:** separately create the dedicated private holding repository,
   confirm access/visibility and retention, then authorize copying/committing the exact
   local ZIP using an owner's existing narrow repository access. Verify original SHA
   before/after and record actual repository ID, commit and blob. This task uploads none.
6. **Organization owner or authorized App manager:** Organization Settings > Developer
   settings > GitHub Apps > New GitHub App. Proposed writer name Kometa English Canary
   Stager; homepage source repository; no OAuth/device/user access flow; webhook inactive;
   Only on this account. Metadata read, Contents write, Pull requests write; all other
   repository/organization/account permissions No access. Generate/store private key
   securely. **Owner** approves installation: Only select repositories > Default-Images.
7. Register a separate reader App (proposed Kometa Canary Artifact Reader) the same way,
   but only Metadata read and Contents read; owner installs on english-canary-artifacts
   only. No Actions, Administration, Workflows or organization Members permission.
8. **Source admin:** environment Variables > ENGLISH_CANARY_APP_ID and
   ENGLISH_CANARY_ARTIFACT_APP_ID; environment Secrets > ENGLISH_CANARY_APP_PRIVATE_KEY
   and ENGLISH_CANARY_ARTIFACT_APP_PRIVATE_KEY. Never use repository-wide key secrets.
   Keep repository ENGLISH_CANARY_STAGING_ENABLED absent/false. Source job token stays
   Contents read + Actions read. The pinned App action attenuates token permissions and
   revokes tokens in post steps; revocation failures require owner reconciliation.

App registration/installation privileges differ from source environment admin and
ordinary writer/reviewer privileges. A maintainer does not need admin to approve a
configured deployment. [App setup reference](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/registering-a-github-app).

## First staging authorization proposal - not granted

After setup, prepare **B** on main changing only staging-policy.json,
staging-authorization.json, private-artifact.json and environment-setup-verification.json
relative to reviewed A. No source/helper/workflow/requirements change is allowed.
Pin A/helper/workflow hashes, model decision, exact artifact-config/setup-receipt hashes,
environment snapshot, all seven paths, target baseline, ownership/writer reservation,
backups and <=24-hour expiry within setup inspection validity. The private config pins
real repository ID, original blob/commit/archive and >=90-day retention; no IDs invented.

Recheck target master/tree and seven old blobs immediately before staging. The
[read-only baseline](../bulk/evidence/english-canary/readiness-target-baseline-20261018.json)
currently agrees with accepted `59e49ede8d41ac5991f971e66e93af596402329a` and all seven
old Git identities. A large recursive read failed; scoped nonrecursive metadata reads
recovered seven-path evidence. Full complete-tree comparison is still mandatory during
staging; API errors/truncation/HEAD drift stop. No fresh image download is claimed.

A separate maintainer authorization must identify A, B, hashes, receipt, artifact pins,
base, seven paths, owner, reservation/observation window and expiry, and allow only a
new canary branch plus one draft PR. Only then may an admin enable the repository gate.
A permitted writer selects Actions > English Poster Canary Staging > Run workflow >
main, stage, confirm true. Verify job displays the exact approval comment. One of five
reviews scope/setup, approves natively with that comment, then the protected job:

- Rechecks source/settings/setup/native evidence before minting the reader token.
- Privately retrieves/verifies the ZIP and individual approvals; checks again before
  minting the target-only writer token.
- Freshly checks complete target HEAD/tree/old identities, constructs exactly seven
  accepted replacements, verifies full diff and sole-parent commit, then POST-creates
  a new authorization-bound branch and one draft PR. Master remains unchanged.

No PATCH/PUT/DELETE/ref-update/merge endpoint or production publisher exists. No forced
update, overwrite, deletion, extra path, automatic retry/cleanup or wider migration.
Partial failures may leave objects/branch/PR; stop and preserve forensic evidence.
Immutable SQLite/hash-chain audit plus safe source run artifacts/logs are retained,
including failure paths; UI evidence and ZIP stay private. Artifact upload failure or
post-token revocation failure requires manual reconciliation, not automatic rollback.
Confirm bullmoose20 coordinator/rollback owner, actual legacy launcher, observation
window and verified backups separately. Existing local rollback rehearsal remains
unchanged; no production rollback is executed here. Production requires another
protected environment approval, reviewed exact candidate PR/commit and separate authority.

**Engineering prepared; real staging NOT ready.** External setup, protected source main,
actual hosted evidence, private storage/upload, credentials, ownership and exact staging
authorization remain mandatory. Local tests never establish live native enforcement.
