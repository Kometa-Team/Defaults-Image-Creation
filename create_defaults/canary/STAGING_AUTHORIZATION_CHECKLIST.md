# Separate English canary staging-authorization checklist

**Reviewer model approved; infrastructure setup checklist remains unchecked.** Setup, staging,
publication and merge are not authorized. `bullmoose20` remains proposed primary
coordinator/rollback owner pending separate confirmation. Follow the exact conditional
[setup guide and operator UI walkthrough](STAGING_INFRASTRUCTURE.md).

## Decision recorded - no setup authorization

- [x] Maintainer approved **Option A**: `reviewer_representation: explicit_users`;
      exactly bullmoose20, YozoraXCII, chazlarson, meisnate12 and badja-dev; one
      explicit approval per deployment, self-review allowed, administrator bypass
      disabled, trusted main restriction and separate production approval retained.
      [Immutable model decision](../bulk/evidence/english-canary/explicit-user-model-decision-20261018.json).
- [x] Removed supported team mode, team ID/configuration and organization lookup
      dependency. Team substitution is rejected; no Members credential is required.

## Setup changes requiring explicit setup approval

- [ ] **Maintainer/rollback owner:** confirm bullmoose20 as coordinator/rollback
      owner, actual legacy launcher, competing-writer reservation and observation
      window. Reviewer-model approval does not confirm operational ownership.
- [ ] **Source repository admin:** Settings > Environments > New environment >
      `english-canary-stage` > Configure environment. Enable Required reviewers;
      add exactly the five **User** accounts above. Leave Prevent self-review
      unchecked; uncheck Allow administrators to bypass configured protection rules;
      Save protection rules. One listed reviewer suffices. Selected branches and tags
      > Add deployment branch or tag rule > Branch > `main`; no tags/wildcards.
- [ ] Establish authoritative no-bypass readback. Current documented REST data omits
      the setting; the helper intentionally blocks on missing state. A settings
      checkbox/manual boolean alone does not satisfy the runtime check. Resolve
      this blocker by a separately reviewed supported verification mechanism.
- [ ] **Organization owner / authorized App manager:** register `Kometa English
      Canary Stager`, disable webhook/OAuth/device flow, select Only on this account
      and generate/download its private key. **Organization owner:** approve/install
      with Only select repositories > **Default-Images only**. Metadata read, Contents write, Pull requests write;
      no Administration, Workflows, source or organization access.
- [ ] **Source repository admin:** environment Variables > Add variable >
      `ENGLISH_CANARY_APP_ID`; environment Secrets > Add secret >
      `ENGLISH_CANARY_APP_PRIVATE_KEY` (PEM). Never commit/log the private key.
      Keep repository `ENGLISH_CANARY_STAGING_ENABLED` absent/false. App-ID is a
      variable; the private key is an environment secret, never a repository-wide
      secret. Source token remains Contents read + Actions read.
- [ ] **Source writer + authorized reviewer/merger:** separately authorize infrastructure-only source deployment using the exact
      deployment manifest and reviewed installed implementation commit A. Do not
      merge PR #12 or replace PowerShell. Installing YAML alone is insufficient.
- [ ] Run a separately approved GitHub-hosted approval exercise with **no target App
      token or write operation**: verify every run pauses; self/cross review works;
      outside initiators cannot approve; no bypass; branch/secret isolation holds.
      Local fixtures and normal validation CI do not prove these server behaviors.
- [ ] Preserve settings/hosted-test evidence and pin the live environment snapshot.
      Leave all policy/authorization gates off pending exact staging permission.

## Artifact transfer decision requiring separate approval

- [ ] Review [delivery options](ARTIFACT_DELIVERY_ASSESSMENT.md). Recommended private
      holding-repository Actions intake needs separate repository/access/adapter
      approval; none is implemented or created here.
- [ ] Do not assume a public repository's Actions artifacts are private. The existing
      inactive public prerelease intake remains unapproved; no tag/release/upload.
- [ ] If public intake is separately selected, explicitly authorize the new source
      tag/release and exact ZIP upload, recognizing public disclosure/notifications.
      Otherwise review a private adapter before installation; no credential fallback.
- [ ] Preserve the exact 7,256,318-byte ZIP and SHA-256
      `97d82b19eb237908cbd4657c67ca16eefe089b5a6d6a5f9e1690fda6cdb597c5`,
      separate artwork acceptance, producer identity, retention and verified backups.

## Exact one-run staging permission required after setup

- [ ] Fresh read-only target master/tree/seven old-blob verification. Pinned base:
      `59e49ede8d41ac5991f971e66e93af596402329a`. Drift requires additive review.
- [ ] Reserve competing writers/legacy job for the observation window.
- [ ] Approve commit B changing only disabled policy/authorization JSON relative to A:
      exact A/helper/workflow, approved five-user roster/model-decision hash, live
      environment snapshot, seven paths and archive/preparation/acceptance hashes,
      immutable asset identity, target base, owner/window/retention/bypass confirmations
      and <=24-hour UTC expiry. Publishing/merging remain false.
- [ ] Separately authorize deploying B and setting the source repository variable true.
- [ ] A GitHub-permitted writer dispatches main/stage once with the exact asset ID and
      confirm true. Any one of the five reviewers, including that initiator, explicitly
      selects Review deployments > english-canary-stage > Approve and deploy.
      An eligible outside writer may dispatch; only a designated maintainer approves.
      No actor automatically approves, and reruns cannot reuse earlier approval.

## Complete future staging action inventory (not executed)

After native approval and preflight, the exact authorized staging run may:

1. Read source artifact/authorization/environment/run/approval evidence; no
   organization/team lookup. Write source run logs/local audit.
2. Mint one short-lived target-only installation token after all checks pass.
3. Read target installation scope, master HEAD, complete tree and old blobs.
4. POST seven already accepted image blobs, one candidate tree and one sole-parent
   commit; verify exact seven replacements and unchanged unrelated content.
5. POST-create one new `canary/english-<authorization-hash-prefix>` ref, never update
   an existing ref; stop on concurrent HEAD changes and preserve forensic evidence.
6. POST one **draft** PR into Default-Images/master. This is a separate future target
   PR, not a change to PR #12. Never merge or update master.
7. Upload unique immutable-at-upload source audit artifacts, preserve a second verified
   copy and revoke the installation token in the pinned action's post step.
8. Disable the repository staging variable afterward under the approved procedure.

No automatic cleanup, ref overwrite, force, deletion, production publisher or rollback
API is implemented. Failures stop without write retries; partial objects/refs/PRs may
remain for owner reconciliation. Audit any failure or manual follow-up separately.

## Production remains a separate decision

A future distinct production environment requires another explicit trusted-maintainer
approval, reviewed target PR/exact candidate commit, verified backups and separately
authorized execution. Staging approval/history cannot authorize publication. No
production environment, credential or publisher is configured by this task.

The [full setup guide](STAGING_INFRASTRUCTURE.md) contains exact App form values,
permission boundaries and the conditional operator walkthrough. These unchecked
steps are the requested **setup checklist for separate authorization**; do not
execute them based on reviewer-model approval.
