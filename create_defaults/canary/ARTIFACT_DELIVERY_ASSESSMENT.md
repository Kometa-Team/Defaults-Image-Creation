# Sealed canary artifact delivery assessment - no transfer authorized

The approved ZIP is 7,256,318 bytes, SHA-256
`97d82b19eb237908cbd4657c67ca16eefe089b5a6d6a5f9e1690fda6cdb597c5`.
Its exact bytes, checksum inventory and seven independently approved image hashes
must survive every delivery option. Acceptance and historical comparison evidence
remain separate, trusted and version-bound; do not repack the ZIP to insert them.

| Option | Privacy and permissions | Recommendation / outstanding decision |
| --- | --- | --- |
| Actions artifact in current public source repository | Signed-in readers can download; public repository read access is broad. Source Actions read suffices for intake. | Not a private delivery mechanism; requires explicit sharing approval. |
| Public source prerelease asset (existing inactive template) | Publicly downloadable and may notify watchers; source Contents read is enough. | No release/tag/upload authorized. Retain as historical proposed backend, not privacy default. |
| Draft release in current public source repository | Draft read access cannot be assumed for the read-only source token; GitHub requires push access to view drafts. | Do not add write credentials or repurpose target App for this. Not recommended. |
| Pinned Actions artifact in a separately approved private holding repository | Repository read access controls download; cross-repository Actions read requires separately approved scoped credentials. | Preferred private design, subject to actual repository/access, producer and retention verification; no adapter or credentials created now. |
| Published release asset in an approved private holding repository | Private repository read/Contents read credential; immutable asset ID and ZIP hash remain pinned. | Viable alternative if long retention is preferable; release assets can be deleted/replaced, so never trust name/tag alone. |

GitHub documents [artifact download access and retention](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/download-workflow-artifacts),
[artifact metadata/digests and Actions read permissions](https://docs.github.com/en/rest/actions/artifacts),
[draft release access](https://docs.github.com/en/rest/releases/releases), and
[source token repository scope](https://docs.github.com/en/actions/concepts/security/github_token).
The public source repository's GITHUB_TOKEN does not grant private cross-repository
read access. No existing private holding repository or suitable credential was
verified, and no plan/private environment support is presumed. Keeping approval
in the current public source environment avoids silently requiring private-repo
required-reviewer features on GitHub Free.

For a later private adapter, authorize and pin repository numeric identity, producer
workflow/commit/run ID, immutable artifact/asset ID, expected name, outer transport
digest (where available), inner ZIP SHA and size, acceptance/preparation identities,
expiry and retention. The Actions artifact ZIP wrapper has its own digest; it must
contain only the unchanged accepted inner ZIP, not a re-encoded/repacked canary.
Validate both layers with bounded ZIP/path/link checks; never download latest by name.

Use a distinct short-lived **read-only intake** credential restricted to the private
holding repository (Actions read for artifacts or Contents read for release assets).
Do not expand the target-only staging App. Make that intake credential available
only through approved protected access; a private design may need to move archive
retrieval from the pre-environment verify job into the protected job, leaving public
preparation checks read-only. Review that workflow change before installation.
No new credentials, repositories, secrets, workflows, uploads or transfer adapter
are implemented under this request.

Confirm retention sufficient for staging, observation, rollback and audit review;
propose at least 90 days plus a second verified access-controlled offline copy, subject
to actual repository limits. Artifacts can expire or be deleted; record exact expiry
and stop if unavailable. Retain producer/acceptance/audit evidence independently.
Private cross-repository API access, expired/invalid artifacts and integrity failures
must be tested before staging; fail closed without public or write-token fallback.

Option A reviewer-model approval does not approve artifact transfer. The selected
configuration requires no organization-team membership credential. A private intake
credential remains a separate read-only repository access decision: choose the
private holding repository/owner, Actions artifact versus private release, approved
producer and retention/backup policy, then separately authorize an adapter and its
minimum access. No artifact transfer or credential is implemented here.
