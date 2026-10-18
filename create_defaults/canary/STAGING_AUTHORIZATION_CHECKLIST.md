# Final English canary infrastructure setup checklist for separate authorization

Only implementation/local testing/source draft-PR push are authorized. Every external
setup/staging item below is **unexecuted**. Option A's five explicit reviewers are already
accepted; that decision grants no environment, credential, upload or target write authority.
Exact UI instructions and evidence limits: [setup guide](STAGING_INFRASTRUCTURE.md).

## External infrastructure authorization checklist

- [ ] **Organization owner/source admin:** protect source main and reviewed workflow/runtime
      changes. It currently reports unprotected; this blocks preflight. No permissions/rules
      are changed in this task. Keep force/deletion restricted and review bypass policy.
- [ ] **Source admin (not bullmoose20's source write role):** create english-canary-stage;
      Required reviewers exactly bullmoose20, YozoraXCII, chazlarson, meisnate12, badja-dev
      as Users. One explicit approval; self-review allowed; admin bypass disabled; only main.
- [ ] **Source admin:** add harmless environment-only ENGLISH_CANARY_APPROVAL_PROBE sentinel.
      Do not add reader/writer keys before the no-credential hosted approval exercise.
- [ ] **Source writer/reviewer/merger:** separately authorize the minimal infrastructure-only
      PR from deployment-files.json, including both workflows, adapters, runtime and disabled
      templates. Do not merge PR #12. Record actual installed commit A and immutable hashes.
- [ ] **All five reviewers/source admin:** run actual native self/cross approval probes;
      outsider approval denial, no-bypass UI, main restriction and sentinel isolation checks.
      Use an existing eligible outside initiator only; otherwise record N/A and complete
      collaborator evidence. Grant no new access just for testing. Record probe runs/reports.
- [ ] **Source admin:** inspect UI no-bypass/source protection; retain redacted evidence
      privately and its SHA-256; bind exact API snapshot/A and hosted report into fresh
      environment-setup-verification.json. <=24-hour validity. Do not claim hidden setting
      machine verification. The helper rejects missing/stale/unverified receipts.
- [ ] **Owner:** authorize/create private Kometa-Team/english-canary-artifacts (proposed name),
      confirm access/retention/backup/deletion policy, then separately authorize committing
      the unchanged ZIP at canary/english-canary-review-bundle.zip. Record real repo ID,
      commit/blob and original 7,256,318-byte SHA-256. No public release or archive upload here.
- [ ] **Owner/App manager registers; owner installs:** Kometa English Canary Stager,
      Metadata read + Contents/Pull requests write; only Kometa-Team/Default-Images.
- [ ] **Owner/App manager registers; owner installs:** distinct Kometa Canary Artifact Reader,
      Metadata read + Contents read; only private holding repo. No PAT, writer-App expansion,
      organization Members, Administration, Workflows or Actions permission required.
- [ ] **Source admin:** protected environment variables ENGLISH_CANARY_APP_ID and
      ENGLISH_CANARY_ARTIFACT_APP_ID; secrets ENGLISH_CANARY_APP_PRIVATE_KEY and
      ENGLISH_CANARY_ARTIFACT_APP_PRIVATE_KEY. No repository-wide keys. Keep source job
      token Contents read + Actions read and repository staging variable false/absent.
- [ ] **Maintainer/operator:** confirm bullmoose20 coordinator/rollback owner, actual PowerShell
      launcher, backups, competing-writer reservation and observation window. Confirm >=90 days
      remaining private retention and separately authorized deletion after audit/rollback needs.

## Distinct first staging authorization - not part of infrastructure setup

- [ ] Re-read current target HEAD/tree/seven old blobs. Baseline remains
      59e49ede8d41ac5991f971e66e93af596402329a. Drift requires additive review, not edited history.
- [ ] Approve B changing only four config/receipt JSON files relative to A; exact source/helper/
      workflow/model/archive/acceptance pins, private config/setup receipt hashes, seven paths,
      ownership/reservation, target base and expiry within receipt validity. Merge/publish false.
- [ ] Separately authorize deployment of B and enabling ENGLISH_CANARY_STAGING_ENABLED.
- [ ] Eligible writer dispatches main/stage/confirm; one trusted maintainer explicitly reviews
      setup/scope and uses the exact run-bound approval comment shown by verify. No auto approval.
- [ ] Guarded operation: native/source/setup checks -> read-only private token -> exact ZIP/seven
      decisions -> full preflight -> target-only short-lived token -> seven blobs/tree/commit ->
      new canary branch -> one draft PR. Never update master, merge or replace PowerShell.
- [ ] Retain immutable audit, full source logs, verified backups and token-revocation results;
      disable repository gate afterward under the separately approved procedure. No auto cleanup.

Exact destinations: based/Book.jpg; decade/2020.jpg; franchise/Death in Paradise (2011).jpg;
genre/Action & Adventure.jpg; genre/Splatter.jpg; year/2020.jpg; year/best/2020.jpg.

Native UI/admin-bypass evidence is partly manual, not API proof. Local mocks/CI prove
implementation checks, not live GitHub authorization. Missing infrastructure or actual
hosted evidence means staging is **not ready**. Future publication needs a separate
protected production approval and reviewed exact candidate commit; no production publisher
or additional migration phase is implemented.
