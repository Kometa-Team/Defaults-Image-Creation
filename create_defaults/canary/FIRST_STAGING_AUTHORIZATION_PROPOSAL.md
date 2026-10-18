# First English canary staging authorization proposal - NOT AUTHORIZED

This is an exact-scope proposal with unknown installation/credential IDs left unfilled.
Only a subsequent explicit maintainer authorization may permit the target branch/draft PR.
Production publishing, master updates, merging, PowerShell replacement and other artwork are excluded.

## Fixed accepted bindings

- Baseline master: `59e49ede8d41ac5991f971e66e93af596402329a`.
- Original ZIP SHA-256: `97d82b19eb237908cbd4657c67ca16eefe089b5a6d6a5f9e1690fda6cdb597c5`; 7,256,318 bytes.
- Preparation: `bc7657363fb253bb41965b56bd73ef650be5dc9606bfff486ac8aa76eb2d77be`.
- Seven individual approvals: `139ed5b73c5ee555488163e024c85e33850207a401aa65b546d87c6b1a7f3919`.
- Source: Kometa-Team/Defaults-Image-Creation, trusted protected main.
- Target: Kometa-Team/Default-Images, base master.
- Exactly five explicit native reviewers; one approval, self-approval allowed, bypass disabled.

| Exact replacement destination | Accepted candidate SHA-256 | Original published Git blob |
| --- | --- | --- |
| based/Book.jpg | `366a97b27d8e9d637297113f26fd567bed5289fcfaf65ccfb6ac4cd6181e0ce5` | `4a009e9e6a5e7edfccc4f30c8a4e2cb513fa70fd` |
| decade/2020.jpg | `2f203c63553b34d802d9c390b5888da1a1c2d1fdb56501f5ba4d3e1c87b764d5` | `cd18c62f091b7024b2b0d60ce642d7c8c5be1f85` |
| franchise/Death in Paradise (2011).jpg | `d1a0ed5653e60c873ec06f57ee96cffb5d0353e354148c759a2ea77ce8566d34` | `4a8660a19524e2f35de9e94e71b28a734ee7afb2` |
| genre/Action & Adventure.jpg | `6e117a400959e84c490d52370a5a3ca7920e4909f8429f67f5ed974a03681c45` | `a20f8bbaab0fdae2b5bd339ee680302b05621960` |
| genre/Splatter.jpg | `7ed904a5e3bc1e264b487f9f612ccc30117dda15340c209d8a2fbc53233dcf27` | `277090e979b2489f4a0fa847cb18463549b6c233` |
| year/2020.jpg | `c7be058188e042d4b7b7d001ee9848e7c2995592a7d76c0e55b76d8863d0f9f4` | `0c7d22aab297768a414d96f75e921136504a25f2` |
| year/best/2020.jpg | `48b58132ddf6a43b3e34382f4592315cb5019baea069583f8402069e6d5b7b54` | `bc813ea9d687555ba7b7e8ca554192999f6ef732` |

## Values required after external setup - none invented

- Actual reviewed installed implementation commit A and activation/config commit B.
- Full helper/installed-workflow SHA-256 and installation manifest/file hashes.
- Actual private repository numeric ID, immutable ZIP commit/blob, config envelope hash,
  >=90-day retention deadline and verified offline backup. Proposed private repo name is
  Kometa-Team/english-canary-artifacts; no repository or ZIP upload is authorized here.
- Real environment ID/API snapshot, source-admin UI evidence hash, verified hosted probe
  run/report identities, fresh setup receipt hash and <=24-hour inspection expiry.
- Exact staging-authorization envelope hash and UTC expiry no later than receipt expiry.
- Confirmed coordinator/rollback owner, legacy launcher, single-writer/observation window.

## Proposed future maintainer authorization wording

> I authorize one controlled English staging run using reviewed implementation A=<full SHA>,
> config B=<full SHA>, helper/workflow/manifest hashes=<exact values>, private configuration
> hash=<exact value>, setup receipt/environment snapshot=<exact values>, and staging
> authorization hash/expiry=<exact values>. The scope is only the seven paths and exact
> candidate/archive/approval identities above against the freshly confirmed baseline.
> The operation may create a new authorization-bound canary branch and one draft target
> PR, and retain audit evidence. It may not update master, merge, publish, replace
> PowerShell, delete/rename/add other artwork or continue into another migration phase.

The reviewer must still explicitly approve the fresh native environment deployment with
the exact run/setup/authorization comment printed by verify. This text does not preapprove
that deployment or production. A source admin separately enables the repository gate only
after this authorization. A failed/stale check stops; no force, write retry or cleanup.

Current external prerequisites remain unmet: source main protection, environments/Apps/keys,
private repo/upload, actual hosted verification, owner/window and final authorization.
See [setup checklist](STAGING_AUTHORIZATION_CHECKLIST.md).
