# Private canary delivery - selected implementation, no upload authorized

Selected: an unchanged regular Git blob in dedicated private repository proposed as
Kometa-Team/english-canary-artifacts, at canary/english-canary-review-bundle.zip.
The repository does not exist as an authorized/verified resource in this task.
No remote creation/upload occurs. This replaces the earlier Actions-artifact proposal
because one 7.26 MB file needs no extra ZIP wrapper, producer workflow or expiring artifact.

Original byte count: 7,256,318. SHA-256:
97d82b19eb237908cbd4657c67ca16eefe089b5a6d6a5f9e1690fda6cdb597c5.
No rerender, repack or public prerelease. Individual accepted JPEG/context and rollback
bindings are independently verified from trusted source evidence after retrieval.

| Option | Disposition |
| --- | --- |
| Private Git blob, separate Contents-read App | Implemented locally: pinned repository ID/private visibility, commit/tree/path/blob, raw ZIP SHA and acceptance checks. |
| Private Actions artifact | Supported alternative, not selected: requires Actions-read access, producer/run/artifact pins, wrapper validation and expiry handling. |
| Private release asset | Viable alternative, not selected: Contents-read plus asset identity/retention; avoid draft-read permission assumptions. |
| Public source artifact/prerelease | Rejected for selected delivery; public access is incompatible with private handoff. Public intake code removed. |

A separate artifact-reader App has only Metadata read and Contents read, installed
on the single private holding repo. The existing target writer App remains restricted
to Default-Images, Contents/PR write. Both use short-lived installation tokens and the
pinned official token action with post-job revocation. No PAT/ambient GH_TOKEN fallback,
no organization membership permission and no target-App permission expansion.
Native approval and source/setup checks precede reader mint; full ZIP verification
precedes writer mint. GET-only fixed API routes refuse redirects, wrong scope/visibility,
wrong objects, unavailable responses, oversized/base64-invalid data or hash mismatches.
Audit contains statuses and hashes, not private URLs, key/token values or ZIP bytes.

GitHub Free supports private repositories; a standard 7.26 MB Git object is below the
100 MiB per-file block. No LFS, paid private environment feature or cloud service is
needed. ZIP retention does not consume Actions artifact storage because it is an ordinary
Git blob. Public source workflows keep their native environment protections; normal
account/API/runner policies and organization repo-creation controls still apply. No
paid-plan upgrade is presumed. Verify current organization limits before setup.
Sources: [plans](https://docs.github.com/en/get-started/learning-about-github/githubs-plans),
[file limits](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github),
[blob API and Contents-read access](https://docs.github.com/en/rest/git/blobs).

Pin real repository ID/commit/blob and >=90 days remaining retention in private-artifact.json;
retain an independently verified access-controlled offline copy. Nothing is auto-deleted.
After rollback/audit obligations end, owner separately authorizes deletion. Deleting a
file does not purge Git history; delete/retire the dedicated holding repo and copies only
under that authorization. Never change visibility to public, upload the ZIP to source
Actions artifacts, or use an unapproved URL. Neither deletion nor upload API exists here.

Remaining external decisions: approve holding repository/access/owner, retained backup
location and retention deadline, owner upload procedure, reader App/key setup, and exact
private config pins. These require separate authorization; disabled/null values remain
in tracked templates. Local fixtures and original-ZIP rehearsal do not establish real
private-repository access or successful hosted approval enforcement.
