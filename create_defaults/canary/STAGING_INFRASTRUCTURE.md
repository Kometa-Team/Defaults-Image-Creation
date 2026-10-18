# English canary staging infrastructure — review only

**Prepared, not installed or activated.** All staging gates are disabled. Read-only
GitHub identity/permission inspection was performed; no ref/PR creation, credential
enabling, App installation, workflow installation, image publication or merge occurred.
PR #12 remains draft. **Option A is approved for the reviewer model only.** The
[maintainer decision](../bulk/evidence/english-canary/explicit-user-model-decision-20261018.json)
binds exactly five explicit accounts; it grants no setup or staging authority.

## Reviewable files and fixed identities

- [Workflow template](english-poster-canary.yml): actual Actions YAML stored here,
  outside `.github/workflows`. Manual `verify`/`stage` modes only, default `verify`;
  there is no publish, merge or rollback mode.
- [Staging helper](../bulk/canary_staging.py): verifies the accepted archive and
  individual decisions, performs guarded staging only, supports a real local Git
  dry-run, and writes immutable SQLite events plus hash-chained exclusive JSON files.
- [Disabled policy](staging-policy.json): `staging_enabled: false`;
  `bullmoose20` is the **proposed** primary reviewer and rollback owner. Both
  rollback-owner confirmation remains false. `reviewer_confirmed: true` records
  only the approved five-user reviewer model, not GitHub setup or staging authority.
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
   checks require the five exact verified maintainer identities, self-review allowed,
   only `main` deployment branch and an exact authorized live-settings fingerprint.
   Missing/true native admin-bypass readback stops. See the open blocker below.
   An explicit native approval record is required; actor identity grants no approval.
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

### Permission boundaries for future setup

| Action | Required operator/access | Current recorded finding |
| --- | --- | --- |
| Register/manage organization-owned App and private key | Organization owner or authorized GitHub App manager | YozoraXCII, chazlarson, meisnate12 and badja-dev were verified active owners. |
| Approve/install App on the organization and selected repository | Organization owner under organization installation policy | App management alone must not be assumed to grant installation authority. |
| Create/configure protected environment, reviewer/no-bypass/branch rules and its secrets | **Defaults-Image-Creation repository admin** | Those four were verified source admins; bullmoose20 has source write, which does not permit environment configuration. |
| Prepare infrastructure-only source PR | Source writer; eventual merge follows protected-branch rules and separate authorization | No installation/merge is authorized here. |
| Dispatch trusted workflow manually | Source write access and enabled workflow | All five had at least source write; no access is granted to other users. |
| Approve pending protected deployment | One configured reviewer with source read access | Any one of the five, including the initiator; repository-admin access is not needed to approve. |

These findings refer to the retained permission audit, not a new access grant. An
administrator must verify access at setup. The target App requests no repository
Administration or organization Members permission. GitHub's [environment requirements](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments)
and [App registration](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/registering-a-github-app)
describe these distinct responsibilities.

### 1. Confirm people and operating window

The intended approval roster is `bullmoose20`, `YozoraXCII`, `chazlarson`,
`meisnate12`, `badja-dev`. Each may initiate and explicitly approve their own run or approve
another permitted initiator's run. One approval suffices; every fresh staging run
must pause. There is no independent-dispatcher requirement. Actual workflow dispatch
permission is governed by GitHub (write access for manual runs), not granted by this
proposal. An outside writer may initiate but cannot approve merely because of their
write role, PR authorship, workflow inputs or configuration submitted in a PR.

| Initiator (if GitHub permits dispatch) | Permitted explicit approver | Self-approval |
| --- | --- | --- |
| bullmoose20 | Any one of the five authorized maintainers | Allowed |
| YozoraXCII | Any one of the five authorized maintainers | Allowed |
| chazlarson | Any one of the five authorized maintainers | Allowed |
| meisnate12 | Any one of the five authorized maintainers | Allowed |
| badja-dev | Any one of the five authorized maintainers | Allowed |
| Other eligible workflow writer | Any one of the five authorized maintainers | Outside initiator cannot approve |

`bullmoose20` remains proposed primary coordinator and rollback owner, subject to
separate confirmation. This coordination role does not restrict deployment approval
to that account. Confirm the 30-minute observation/writer-reservation window and
existing PowerShell launcher/configuration/owner; do not alter the generator.

### Verified identities, roles and reviewer representation

Read-only GitHub observations are retained in the [permission audit](../bulk/evidence/english-canary/trusted-maintainer-permissions-20261018-v2.json) and its unchanged earlier snapshot.
The authenticated account was `bullmoose20`.

| Account | Account ID | Organization membership | Defaults-Image-Creation effective role | Default-Images effective role |
| --- | --- | --- | --- | --- |
| bullmoose20 | 12549033 | active member | write | maintain |
| YozoraXCII | 96386153 | active owner (`admin`) | admin | admin |
| chazlarson | 3865541 | active owner (`admin`) | admin | admin |
| meisnate12 | 1631064 | active owner (`admin`) | admin | admin |
| badja-dev | 180163201 | active owner (`admin`) | admin | admin |

GitHub's collaborator endpoint reports permission `write` for `maintain`, so the
record includes both `permission` and `role_name`; the table uses the effective role.
The visible `developers` team (ID 13883129, organization Kometa-Team, no parent)
contains **exactly all five authorized accounts** after the user's addendum.
It is a matching team candidate; no new dedicated team is necessary. The source
team repository listing exposed write access, and its permission-check request
succeeded with an empty response. The target team permission check returned 404
and a missing `admin:org` scope diagnostic; it establishes no target team role.
Each user's effective target role was independently verified as shown above.
Repository-level team-list GETs returned 404 on both repositories; hidden team
access remains an organization-admin verification item, not an invented absence.

**Selected and approved: Option A, five explicit GitHub users.** Both policy and
authorization templates use `reviewer_representation: explicit_users`, bind the
immutable model-decision SHA-256 and include the five verified numeric account IDs.
The policy now records reviewer-model confirmation. Staging remains false;
authorization, rollback-owner confirmation and infrastructure permissions remain false.
There is no reviewer-team field, supported team mode or runtime organization/team
lookup. A team entry or mode substitution is rejected. Historical Developers-team
observations above remain evidence only; their API access limitations are **not
blockers or prerequisites for the selected configuration**. No organization Members
credential, team creation, permission grant or renewed membership check is needed.

GitHub supports up to six user/team reviewer entries and requires any one listed
reviewer; the approved configuration uses exactly five User entries. Reviewers need
source read access, and manual workflow dispatch follows actual source write access.
Both repositories were observed public on Free, where native required reviewers
are supported. See [native reviewer controls and plan availability](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments).
No native team configuration is part of the selected implementation.

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
2. Enable **Required reviewers** and add exactly `bullmoose20`, `YozoraXCII`,
   `chazlarson`, `meisnate12`, `badja-dev`, checking the account IDs above. One of five approves.
   Select **User** entries, not Developers or any team. Native GitHub requires
   one of these reviewers; no second reviewer or independent dispatcher is needed.
3. Leave **Prevent self-review unchecked**. Deselect **Allow administrators to bypass
   configured protection rules**. Save protection rules and retain settings evidence.
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

### 5. Decide artifact intake and retention separately

See [private artifact-delivery assessment](ARTIFACT_DELIVERY_ASSESSMENT.md).
**Recommend a separately authorized private holding repository with pinned Actions
artifact delivery**, subject to access/retention verification and adapter review.
No holding repository, upload, credential or adapter is created by this task.

The existing inactive template still implements a source **public prerelease** GET
backend. This is not the recommended privacy-preserving choice and is not activated.
No prerelease, source tag or ZIP upload has occurred. Do not dispatch this backend
unless public sharing is separately explicitly approved. Otherwise replace it only
through a separately authorized private adapter change; do not repack the ZIP or
reuse a target write token to read a source draft release. The earlier public-backend
implementation and immutable preparation record remain historical evidence.

### 6. Prepare a distinct staging-authorization change

After setup and intake are separately approved and tested, prepare **commit B**
on source `main` changing only the policy/authorization JSON relative to A.
No other source change is permitted by preflight. This is a separately approved
activation/configuration change, not part of this task.

- Policy: keep the approved explicit-user roster/model binding; enable staging and
  confirm the proposed rollback owner only under separate staging/owner approval.
- Authorization: `authorized=true`, action `stage_seven_english_images_only`;
  record implementation commit A, full helper and installed-workflow SHA-256 values
  (hash normalized LF text), integer source asset ID, all seven exact destinations,
  exact ZIP/preparation/acceptance identities, pinned target HEAD, five-person reviewer
  roster with verified IDs, rollback owner `bullmoose20`, exact live environment
  snapshot SHA-256, owner/window/durable-backup/bypass confirmations, and UTC
  expiry no more than 24 hours ahead. `publish_authorized` and `merge_authorized`
  remain false. Recompute canonical envelope SHA after finalizing fields.
- Re-read target HEAD/tree and seven old blob identities using read-only access.
  Any drift from `59e49ede8d41ac5991f971e66e93af596402329a` stops; do not substitute
  a new base into the old acceptance or weaken checks. Prepare an additive,
  separately reviewed baseline update if needed while keeping images/archive intact.
- Obtain explicit staging approval naming A, B, installed workflow/helper hashes,
  asset ID, bundle/preparation/acceptance hashes, target base, seven paths, permitted
  initiator, reviewer roster/rollback owner, environment snapshot and expiry. Only then may a maintainer deploy B and set the source
  repository variable to `true`. No target operation is authorized before this.

This two-commit scheme avoids inventing a self-referential commit SHA inside its
own authorization: A pins code, B only contains approved activation/authorization data.

### 7. Future staging execution — separately authorized only

Only after separate setup and exact staging authorization, `bullmoose20` can:

1. Open **Defaults-Image-Creation > Actions > English Poster Canary Staging**.
2. Select **Run workflow**, trusted branch **main**, mode **stage**, exact separately
   approved asset ID, and confirm staging. Click **Run workflow** once.
3. Open that run. Its read-only verify job checks the sealed archive and policy.
4. Wait for the protected `english-canary-stage` job to show **Review deployments**.
   It must pause even when the initiator is a designated reviewer.
5. Inspect the run SHA, exact seven image/hash bindings, authorization expiry, target
   base, settings and write scope. Select **Review deployments**, check only
   **english-canary-stage**, optionally record the authorization reference, and
   explicitly click **Approve and deploy** (or Reject).
6. After native approval, read-only preflight checks live protection, exact source,
   run/attempt and GitHub's approval history **before** minting the target App token.
   An unobservable/changed native control stops here; do not override the helper.
7. If all checks pass, only a new seven-file branch and **draft** target PR are
   created. Verify the seven paths/hashes and retain audit evidence; master stays
   unchanged. The target PR remains unmerged.

The same sequence applies to any of the five maintainers approving their own run.
To approve another maintainer's (or an outside permitted writer's) run, open that
pending run and perform steps 4-5 as one of the five designated reviewers. The
outside initiator has no approval right. GitHub determines who can dispatch;
this workflow grants no new access. A new dispatch is required for each attempt:
reruns are refused because review history is per run and could reuse old approval.

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
App/env/installation/intake/staging authorization and rollback-owner confirmation
remain outstanding. The reviewer model is approved; team membership is not a dependency.
Real App access, token revocation and GitHub staging have deliberately not been tested.
No production-changing action may proceed on the basis of this report.

### Native-control verification blocker and test boundary

The documented REST environment response does **not** expose `can_admins_bypass`,
and GraphQL Environment introspection exposed no bypass field. No source staging
environment exists yet. The helper requires authoritative readback equal to false;
missing/true state fails closed before App token minting. The API's lack of a field
must not be treated as proof that native no-bypass protection is unavailable, or
that it is disabled. A manually checked box/authorization boolean is not substituted
for machine readback. A supported authoritative readback/evidence verification
method must be separately reviewed before staging can run; no extra Administration
permission or undocumented endpoint is silently requested. Until resolved, this is
**an explicit staging blocker**, even after a trusted maintainer clicks approval.

An admin must verify in GitHub UI: reviewer names/IDs, self-review unchecked, bypass
unchecked and only main branch; retain evidence. If native required-reviewer controls
are unavailable for the actual repository/plan, stop; do not replace them with an
actor YAML condition. Once setup is separately authorized, prove the pause, trusted
self-review, cross-review, outsider rejection, secret isolation and no-bypass behavior
with a GitHub-hosted **no-target-token/no-target-write** approval exercise before
activating staging. No such hosted approval exercise occurred in this task.

Local fixtures cover all five self-review identities, cross-review and outside-writer
initiation followed by trusted approval, denial without explicit review, outsider
reviews, roster/ID drift and team substitution, wrong source/attempt, missing/changed native controls,
artifact and seven-path safeguards. They validate parsing/policy logic, **not GitHub's
server-side authorization or UI behavior**. Existing immutable evidence is preserved;
new implementation and dry-run evidence are additive.

Roster changes require disabling staging, verifying account IDs/membership/access,
reviewing a new pinned explicit-user implementation/environment configuration and exact staging
authorization, and repeating the no-write hosted checks. PR content/inputs cannot
amend the roster. Repository/organization administrators can edit settings or trusted
source code; native reviewers do not remove that administrative authority. The helper
rejects observable drift, and fresh settings evidence is required before activation.

### Production remains separate

No production environment/publisher is created, configured or activated. Future
production uses a **different** protected environment and another explicit approval
by one of the same authorized maintainers; staging review/history never satisfies
it. A reviewed target canary PR, exact candidate commit, verified backups, observation
window and separately authorized production execution remain required. No automatic
merge, cutover, PowerShell replacement or next migration phase follows staging.
