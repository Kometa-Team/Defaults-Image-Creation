# Separate English canary staging-authorization checklist

**All unchecked; preparation and visual acceptance grant none of these permissions.**
Proposed primary reviewer/rollback owner: `bullmoose20`, pending explicit confirmation.
Use the [configuration instructions](STAGING_INFRASTRUCTURE.md). No action was executed.

## Setup changes requiring explicit setup approval

- [ ] Confirm `bullmoose20` roles/access and name a different writer to dispatch.
- [ ] Register the organization-owned App; generate its private key; install it on
      Kometa-Team with Default-Images as its **only** selected repository.
- [ ] Grant only Metadata read, Contents write, Pull requests write. No organization,
      Administration, Workflows or source-repository installation permission.
- [ ] Create source environment `english-canary-stage`, only reviewer `bullmoose20`,
      prevent self-review, disable admin bypass, allow only branch `main`.
- [ ] Add source environment App-ID variable/private-key secret. No broad PAT fallback.
- [ ] Authorize a separate infrastructure deployment PR in the source repo, exactly
      the deployment manifest; explicitly review/authorize its installation/merge.
      This does not merge or mark PR #12 ready, or modify PowerShell.
- [ ] Record installed implementation commit A and full file/action hashes.
- [ ] Keep source repository staging variable false/absent and policy/auth disabled.

## Artifact transfer requiring explicit artifact-sharing approval

- [ ] Choose/approve the source prerelease intake backend. It makes the existing
      ZIP publicly downloadable in the source repo; no such publication is currently
      authorized. If privacy is required, remain disabled until a private adapter
      has been separately reviewed. Do not silently use write credentials for drafts.
- [ ] Authorize source prerelease creation and uploading **only the existing ZIP**,
      not a new render/repack. Record tag, source asset ID, size and exact SHA/digest.
      Source release notifications can occur. No release in Default-Images.
- [ ] Retain a second verified backup and the separate seven-image approval records.
- [ ] Run source workflow `verify` only; no target writes or target token required.

## Distinct permission to activate staging

- [ ] Confirm target HEAD/tree and all seven existing exact-case blob identities.
      Any drift from the recorded base stops for a fresh reviewed baseline.
- [ ] Confirm writer reservation, 30-minute observation period and backup availability.
- [ ] Prepare activation/authorization-only commit B relative to reviewed code A.
      Bind all seven paths, existing ZIP and approval hashes, source asset ID,
      implementation/workflow/helper hashes, base HEAD, dispatcher, confirmed
      reviewer/owner and UTC expiry (at most 24 hours). No publish/merge authority.
- [ ] Explicitly authorize deployment of B and setting the source staging variable true.
- [ ] Explicitly authorize the specific staging run, not merely workflow installation.
- [ ] Have the independent operator dispatch `stage`; `bullmoose20` must review and
      approve the protected environment. No self-review or administrator bypass.

## Every possible target GitHub mutation in that future authorized run

1. POST App installation access-token creation (official action); repository scope
   narrowed to Default-Images. GET installation repository scope is verified.
2. GET target master, commit/tree and exact old blob identities (read-only).
3. Up to **7 × POST `/repos/Kometa-Team/Default-Images/git/blobs`** for accepted bytes.
4. **1 × POST `.../git/trees`** with base tree and exactly seven replacement entries.
5. GET complete candidate tree; verify no unrelated change.
6. **1 × POST `.../git/commits`** with exactly the approved master HEAD as sole parent.
7. Recheck master; GET new branch name to require absence.
8. **1 × POST `.../git/refs`** to create only the new `canary/english-<auth-prefix>` ref.
9. Recheck master. **1 × POST `.../pulls`** to open a **draft** seven-file PR against
   master; PR creation can notify target watchers/reviewers. No explicit reviewer
   request/comment/label operation is included.
10. Recheck master; append local immutable audit events and upload an audit artifact
    in **Defaults-Image-Creation**. Failure evidence is uploaded too.
11. Official action post step revokes its installation token (DELETE token, not
    a repository/ref deletion). Reconcile manually if revocation fails.

There is **no** PATCH/update of master or any existing ref, force push, merge API,
file deletion, tag change, settings change in Default-Images, per-file Contents API
replacement, workflow installation in Default-Images, rollback or publication route.
An App installation is a separately approved GitHub access/configuration change,
not an image update; it has not occurred under this preparation.

Partial errors may leave Git objects, a staging branch or draft PR. Stop and preserve
rather than retry/delete/rebase. Only the separately authorized run may create those
objects. The local dry-run creates none of those remote objects or local staging refs.

## Required approval wording must identify

Implementation A and activation B; installed workflow/helper hashes; source artifact
ID and ZIP SHA `97d82b19eb237908cbd4657c67ca16eefe089b5a6d6a5f9e1690fda6cdb597c5`;
preparation `bc7657363fb253bb41965b56bd73ef650be5dc9606bfff486ac8aa76eb2d77be`;
acceptance `139ed5b73c5ee555488163e024c85e33850207a401aa65b546d87c6b1a7f3919`;
target base and seven paths; independent dispatcher; confirmed `bullmoose20` roles;
window and expiry. Explicitly limit authority to the new draft staging PR and
forbid publishing, merging, production ref changes, PowerShell replacement and
anything outside the seven images. No future IDs/commit hashes are invented here.
