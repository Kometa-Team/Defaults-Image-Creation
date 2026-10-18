# English canary staging infrastructure — review only

**Prepared, not installed or activated.** All staging gates are disabled. No
Default-Images request, ref/PR creation, credential enabling, App installation,
workflow installation, image publication or merge was performed in this task.
PR #12 remains draft. This is implementation preparation, not staging authority.

## Reviewable files and fixed identities

- [Workflow template](english-poster-canary.yml): actual Actions YAML stored here,
  outside `.github/workflows`. Manual `verify`/`stage` modes only, default `verify`;
  there is no publish, merge or rollback mode.
- [Staging helper](../bulk/canary_staging.py): verifies the accepted archive and
  individual decisions, performs guarded staging only, supports a real local Git
  dry-run, and writes immutable SQLite events plus hash-chained exclusive JSON files.
- [Disabled policy](staging-policy.json): `staging_enabled: false`;
  `bullmoose20` is the **proposed** primary reviewer and rollback owner. Both
  confirmations remain false pending explicit maintainer confirmation.
- [Unauthorized template](staging-authorization.json): `authorized: false`.
  Unknown implementation/workflow hashes, asset ID and expiry are null, not invented.
- [Deployment manifest](deployment-files.json): exact source/target files and hashes
  needed for a later separately reviewed infrastructure-only installation.
- [Separate staging-authorization checklist](STAGING_AUTHORIZATION_CHECKLIST.md).

The existing archive remains unchanged:

| Binding | Exact identity |
| --- | --- |
| ZIP | `english-canary-review-bundle.zip`, 7,256,318 bytes |
| ZIP SHA-256 | `97d82b19eb237908cbd4657c67ca16eefe089b5a6d6a5f9e1690fda6cdb597c5` |
| Preparation envelope | `bc7657363fb253bb41965b56bd73ef650be5dc9606bfff486ac8aa76eb2d77be` |
| Seven-image acceptance envelope | `139ed5b73c5ee555488163e024c85e33850207a401aa65b546d87c6b1a7f3919` |
| Reviewed artifacts/CI | `a4c48f003f11b8a36928b3d764a69da932debc2b` |
| Pinned comparison target HEAD | `59e49ede8d41ac5991f971e66e93af596402329a` |

Full proposed/old image SHA-256 hashes and exact destinations are in the unchanged
[preparation](../bulk/evidence/english-canary/preparation-20261017.json) and
[individual acceptance](../bulk/evidence/english-canary/visual-acceptance-20261017.json).
`genre/Action & Adventure.jpg` must keep exactly that spelling/case. No rerendering,
repacking, translated layout activation, overlays or private intermediates.

## Safeguards implemented

1. Archive SHA/size before parsing; exact member inventory, 64 MiB decompression
   bound, duplicate/path/link rejection and checksum verification; decode all seven
   existing JPEGs without re-encoding. Check exact individual approval/context binds.
2. Disabled policy and unconfirmed roles stop the CLI **before any network/token
   access**. The transport independently rejects disabled, changed or expired
   authorizations before constructing its session and before every POST.
3. Separate authorization must name exact bundle/preparation/acceptance, source
   implementation commit, helper/workflow hashes, integer source asset ID, base HEAD,
   all seven paths, reviewer/owner confirmation, reservation, durable backup and
   an expiry no more than 24 hours away. Publishing/merging must remain false.
4. The workflow stays on trusted source `main`, with no persisted checkout
   credentials. Only the policy/authorization JSON files may change between the
   reviewed infrastructure commit and its separately approved activation commit.
   No helper, requirement, workflow or shared runtime change is silently adopted.
5. Source token remains `contents: read`, `actions: read`. Actual live environment
   checks require only `bullmoose20` as reviewer, prevent-self-review enabled and
   only `main` deployment branch. Admin-bypass disabling is separately attested:
   the environment response does not reliably expose that setting.
6. Target App token is requested only after the protected environment and complete
   preflight, restricted to Default-Images and Contents/Pull requests write. The
   helper confirms its installation token can access only that one repository.
7. Fresh target HEAD/tree and old blob IDs/modes must match the accepted baseline.
   Case-insensitive aliases stop. Recheck HEAD before first write, before creating
   the staging ref, after that ref, and after the draft PR. Incomplete trees stop.
8. Seven blobs only; a tree based on the pinned tree; verify the complete resulting
   file map has exactly those seven replacements and preserves every other entry.
   The candidate commit has the approved HEAD as its sole parent.
9. Only **POST-create** of a new `refs/heads/canary/english-<authorization-hash-prefix>`
   is implemented. An existing ref stops; it is never overwritten. No force flag,
   PATCH/PUT/DELETE, master-ref update, PR merge, tag change or automatic cleanup
   route exists. A separate draft target PR is the only PR operation.
10. No automatic write retry or rollback. Partial failure can leave unreachable Git
    objects or a staging branch/draft PR; preserve them for reconciliation. If HEAD
    changes just after a read, staging can be stale: the next check stops. This
    cannot atomically prevent a new staging ref racing master, but no production
    ref is writable through this implementation. Do not interpret it as cutover.

Audit files are append-only by construction and tamper-evident through SHA-256
chains; existing SQLite triggers reject UPDATE/DELETE. `audit-verify` compares
portable records with the database. The official upload-artifact action creates a
new immutable-at-upload artifact per run/attempt, including failure evidence.
Administrators can still delete artifacts; retain an additional verified copy.
No token, private key or Authorization header is written to audit evidence.

## Exact future setup steps — do not perform under preparation approval

These steps change GitHub configuration and require **separate setup authorization**.
Nothing below has been applied.

### 1. Confirm people and operating window

Confirm `bullmoose20` as primary staging reviewer and rollback owner. Verify that
account has source-repository read access for environment review and the operational
access needed to coordinate rollback. Name a **different authorized source-repository
writer** to dispatch runs: prevent-self-review means `bullmoose20` cannot approve a
run they started. If no second operator is available, remain blocked; do not silently
relax self-review protection. Confirm the 30-minute observation/writer-reservation
window and the existing PowerShell launcher/configuration/owner. Do not alter it.

### 2. Register the target-only GitHub App

A Kometa-Team organization owner/app manager must perform these future steps:

1. Organization Settings → Developer settings → GitHub Apps → New GitHub App.
2. Proposed unique name: `Kometa English Canary Stager` (choose an available name).
   Homepage: `https://github.com/Kometa-Team/Defaults-Image-Creation`.
3. Do not request user OAuth authorization, callback/device flow or user tokens.
   Deselect webhook Active; select **Only on this account**.
4. Repository permissions: Metadata read-only, Contents read/write,
   Pull requests read/write. All other repository/organization/account permissions
   remain No access. No Administration or Workflows write permission.
5. Create the App. Record App ID; generate/download one private key into the
   administrator's secure storage. Never paste the key in Git, logs or this report.
6. Install App → Kometa-Team → **Only select repositories** → **Default-Images only**.
   Record installation ID and selected-repository/permission evidence.
7. Do not install it on Defaults-Image-Creation or grant access to all repositories.

App Contents write is repository-wide; the seven-path restriction is enforced by
reviewed code, not by GitHub's permission model. No Workflows write permission is requested. The token can technically perform
broader content/PR operations; merges and production writes are prohibited by the
reviewed implementation and authorization, not magically excluded by token scope. See official
[App registration](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/registering-a-github-app).

### 3. Configure the source protected environment

In **Defaults-Image-Creation**, not Default-Images:

1. Settings → Environments → New environment → `english-canary-stage`.
2. Required reviewers: **only `bullmoose20`**, after confirmation. GitHub accepts
   any one listed reviewer, so do not add a fallback that weakens this requirement.
3. Enable **Prevent self-review**. Deselect **Allow administrators to bypass
   configured protection rules**. Save and retain settings evidence.
4. Deployment branches/tags: Selected branches and tags → Branch → exactly `main`.
   Add no tag or wildcard rule. The helper verifies the live reviewer/branch rules.
5. Environment variable `ENGLISH_CANARY_APP_ID`: the confirmed App ID.
6. Environment secret `ENGLISH_CANARY_APP_PRIVATE_KEY`: the downloaded PEM.
   Do not create any source/target write-token secret or personal-token fallback.
7. Source repository variable `ENGLISH_CANARY_STAGING_ENABLED`: keep absent or
   `false` until a distinct exact staging authorization is approved.

Environment setup needs repository admin access. Required reviewers gate secret
release. See official [environment setup](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments).
The token action is pinned to `fee1f7d63c2ff003460e3d139729b119787bc349`;
its post step revokes the installation token (`skip-token-revoke: false`). See
[official action](https://github.com/actions/create-github-app-token/tree/fee1f7d63c2ff003460e3d139729b119787bc349).
If post-job revocation fails, stop and have the administrator reconcile/revoke access.

### 4. Install only reviewed infrastructure, without merging PR #12

Source `main` does not currently contain the required bulk runtime. Copying just
YAML would fail. A **separate, explicitly authorized infrastructure-only PR** must
install the exact files in `deployment-files.json`: neutral shared utilities/state,
staging helper, narrow requirements, accepted metadata, disabled policy/templates,
and the template copied to `.github/workflows/english-poster-canary.yml`.
No compositor, fonts, catalog, PowerShell generator, artwork or unrelated Package E
implementation is deployed by that subset. Preserve PR #12 draft/unmerged.

Review that independent PR, its file hashes, action pins and tests. Only a later
explicit installation/merge authorization may deploy it. Record the resulting full
source infrastructure commit **A**. Policy remains disabled and authorization false.
The template uses only manual dispatch and no publication/rollback mode.

### 5. Approve the artifact intake explicitly

The prepared implementation uses the **read-only source prerelease asset** backend,
not an arbitrary URL. GitHub draft releases require push access to view, so silently
using a draft would not work with the source read-only workflow token. This template
therefore requires a **published prerelease** in the source repository, not a draft.
See [release visibility](https://docs.github.com/en/rest/releases/releases?apiVersion=2022-11-28).

**This would make the review ZIP publicly downloadable in the public source repo.**
It is an additional publication action requiring explicit artifact-sharing approval,
separate from visual acceptance or staging permission. It has NOT occurred. If a
public source artifact is unacceptable, do not enable this template: approve and
review a private Actions-artifact intake adapter first. Do not widen source token
permissions or use a personal token just to bypass draft-release restrictions.

Only after artifact-sharing authorization, a source repository writer could run:

```powershell
$bundlePath = 'C:\Users\bullmoose20\Defaults-Image-Creation\config\english-canary\preparation-20261017-v1\english-canary-review-bundle.zip'
(Get-FileHash -LiteralPath $bundlePath -Algorithm SHA256).Hash
# Must equal 97d82b19eb237908cbd4657c67ca16eefe089b5a6d6a5f9e1690fda6cdb597c5
# FUTURE AUTHORIZED ACTION ONLY; do not run under preparation/visual approval:
$sourceImplementationCommit = '<approved full source infrastructure commit A>'
# Require the source release/tag name to be absent; stop if either already exists.
# This creates a new source tag at exactly A as well as the prerelease and asset.
gh release create english-canary-approved-v1 $bundlePath --repo Kometa-Team/Defaults-Image-Creation --target $sourceImplementationCommit --prerelease --title 'English canary reviewed bundle — not production' --notes 'Immutable accepted review archive; no Default-Images publication authorization.'
gh api repos/Kometa-Team/Defaults-Image-Creation/releases/tags/english-canary-approved-v1 --jq '.assets[] | {id,name,size,digest}'
```

Record integer asset ID, exactly 7,256,318 bytes and digest `sha256:<ZIP SHA above>`.
Never use `--clobber`, replace or repack it. Preserve a second verified offline copy
and the separate acceptance/audit records. Future `verify` dispatch uses the asset
ID, `mode=verify`, `confirm_staging=false`; it makes no Default-Images request or write.
Creating a source release may notify watchers; this too is included in the checklist.

### 6. Prepare a distinct staging-authorization change

After setup and intake are separately approved and tested, prepare **commit B**
on source `main` changing only the policy/authorization JSON relative to A.
No other source change is permitted by preflight. This is a separately approved
activation/configuration change, not part of this task.

- Policy: enable staging and confirm both proposed roles only after confirmation.
- Authorization: `authorized=true`, action `stage_seven_english_images_only`;
  record implementation commit A, full helper and installed-workflow SHA-256 values
  (hash normalized LF text), integer source asset ID, all seven exact destinations,
  exact ZIP/preparation/acceptance identities, pinned target HEAD, reviewer/rollback
  owner `bullmoose20`, owner/window/durable-backup/bypass confirmations, and UTC
  expiry no more than 24 hours ahead. `publish_authorized` and `merge_authorized`
  remain false. Recompute canonical envelope SHA after finalizing fields.
- Re-read target HEAD/tree and seven old blob identities using read-only access.
  Any drift from `59e49ede8d41ac5991f971e66e93af596402329a` stops; do not substitute
  a new base into the old acceptance or weaken checks. Prepare an additive,
  separately reviewed baseline update if needed while keeping images/archive intact.
- Obtain explicit staging approval naming A, B, installed workflow/helper hashes,
  asset ID, bundle/preparation/acceptance hashes, target base, seven paths, dispatcher,
  reviewer/owner and expiry. Only then may a maintainer deploy B and set the source
  repository variable to `true`. No target operation is authorized before this.

This two-commit scheme avoids inventing a self-referential commit SHA inside its
own authorization: A pins code, B only contains approved activation/authorization data.

### 7. Future staging execution — separately authorized only

The named independent operator selects source Actions → English Poster Canary
Staging → Run workflow → `main`, mode `stage`, exact asset ID and confirm true.
`bullmoose20` reviews the exact run/ref/artifacts and approves `english-canary-stage`.
The preflight completes before a target write token is minted, then is repeated.
Only a new seven-file candidate branch and a **draft** PR in Default-Images may be
created. Master stays unchanged; the resulting PR must remain unmerged.

The complete future action list is in the separate checklist. End the run after
retaining audit evidence. Disable the repository variable afterward under the
approved procedure. Nothing automatically publishes, merges, deletes the branch,
rolls back or begins a subsequent phase.

## Local verification and current readiness

```powershell
# Local only. Existing accepted ZIP; no remote access or branch creation:
& 'config/package-e/dependency-trial/venv/Scripts/python.exe' -m create_defaults.bulk.canary_staging dry-run --bundle config/english-canary/preparation-20261017-v1/english-canary-review-bundle.zip --root config/canary-staging/a-new-local-review
```

The dry-run creates real local blobs/tree/commit from the seven existing images.
It verifies every candidate hash and full diff while leaving local refs/worktree
unchanged; no remote is configured and no staging ref/PR is created. Logical audit
write intents describe what future staging would do, not remote actions performed.
Unit tests use fake transports for disabled guards, stale HEAD before and after ref/PR,
extra paths, case conflicts, bad approval/artifact pins, unsafe ZIPs, environment
review, forbidden force/update/merge routes and immutable audit verification.

**Ready for implementation/configuration review; NOT authorized or configured to stage.**
App/env/installation/intake/authorization/role confirmations remain outstanding.
Real App access, token revocation and GitHub staging have deliberately not been tested.
No production-changing action may proceed on the basis of this report.

Focused validation: **57 checks passed** locally, including the isolated minimal
runtime deployment fixture and all earlier image acceptance/scope checks. The
recorded pre-collection suite had 55 checks; two later deployment/transport
integrity checks also pass. Full PR CI is run separately before handoff.
