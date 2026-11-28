# Source-only People batches

The standard orchestrator creates managed `source-only-1000x1500-v1` batches and
defaults to local generation. Original is a 1000 x 1500 RGB JPEG; Transparent is
a 1000 x 1500 RGBA PNG. Existing seven-style batches cannot resume under this
contract. Use `--new-batch`; their archives, receipts and recovery data remain.

The audit step reuses recovery's centered `ImageOps.fit` preprocessing before
DDColor and BiRefNet. Working PNGs avoid intermediate JPEG encoding. Exact native
sources use the existing content-addressed `.history/recovery_sources` archive.
DDColor and BiRefNet keep their existing inference sizes and restore working
dimensions. The renderer rejects incorrectly sized working inputs instead of
downscaling final output. Compliant Original JPEGs retain their bytes.

The renderer skips all five derived styles and their asset/font loading. Legacy
renderers and resources remain available to existing standalone callers. Existing
quality thresholds, ratio checks, framing, rollback and retention are retained.
Local validated batches remain retained as `local_validated`, never published.

Publication requires `--publish-mode github_api`, `PEOPLE_GITHUB_TARGET=sandbox`
and an existing `config/sandboxes/RUN/targets.json` containing:

```json
{
  "version": 1,
  "owner": "YOUR-PERSONAL-OWNER",
  "branch": "master",
  "output_contract": "source-only-1000x1500-v1",
  "publication_authorized": true,
  "repositories": {
    "original": "YOUR-PERSONAL-OWNER/kometa-people-sandbox-original",
    "transparent": "YOUR-PERSONAL-OWNER/kometa-people-sandbox-transparent"
  }
}
```

Set `PEOPLE_SANDBOX_CONFIG` to that file. Both repositories must already exist
and support the existing README workflow and publisher permissions. Configuration
is rechecked at transport boundaries; revocation or retargeting blocks requests.
All seven legacy production repositories are rejected. No repository is created,
renamed, swapped or migrated. No real staging or production publication is part
of the implementation validation. Future Kometa rendering/caching is out of scope.

## Replacement repositories (separate operator approval)

The replacement profile reuses the REST publisher, inventory, quality checks,
receipts, README verification, conflict handling and resume. Personal sandbox
configuration is unchanged. No repository or workflow is created or edited.

After explicit approval, create `config/replacements/RUN/targets.json`:

```json
{
  "version": 1,
  "branch": "main",
  "output_contract": "source-only-1000x1500-v1",
  "publication_authorized": false,
  "repositories": {
    "original": "Kometa-Team/People-Images-1500",
    "transparent": "Kometa-Team/People-Images-transparent-1500"
  },
  "repository_ids": {
    "original": 1473470855,
    "transparent": 1473472220
  }
}
```

This example is disabled. Approval must cover both numeric identities, exact
current names, the common branch (`main` or `master`), and the source-only contract.
Only then set `publication_authorized` to `true`, clear `PEOPLE_SANDBOX_CONFIG`,
set `PEOPLE_GITHUB_TARGET=replacement`, `PEOPLE_REPLACEMENT_CONFIG` to the absolute
file path, and explicitly select `--publish-mode github_api`. Leave the default
local mode unchanged otherwise. Use an operator credential limited to these two
repositories with Contents and Actions permissions required by the existing
publisher. Credentials or names alone never authorize a destination.

Both destinations currently use `main`. The existing publisher uses one common
branch for a batch; it never falls back between main/master. An explicit
`--branch` or `PEOPLE_BRANCH` must match the file. Each request rechecks configuration,
numeric identity, exact canonical name and default branch, and routes through
the numeric repository ID. Renames and branch changes require a newly approved
configuration and a fresh batch. The two immutable replacement IDs are the only
eligible identities, so the seven legacy repository identities remain blocked
even if names are reused during a separately approved cutover.

State and jobs remain isolated under `config/replacements/RUN/{state,jobs}`.
Preparation records the complete authorization in the existing SQLite publication
state before the image plan. Resume/retry/push reject a changed or missing binding;
retain that state and the prepared files together. Existing batches cannot be
retargeted. The native Git backend is not enabled for this replacement profile.

Before publishing, run the existing read-only preflight from `create_people_posters`:
`python publish_people_github.py --op validate --config PATH_TO_BATCH --branch main`.
Then use the existing `--op prepare` and, only under a separately approved release,
`--op push` with the same config, branch and batch ID. Preparation itself makes no
GitHub writes. Do not disable required README dispatch or receipt checks.

Live preflight currently remains blocked: neither replacement repository has
`.github/workflows/readme.yml` on main (verified read-only). An authorized operator
must resolve that existing publisher prerequisite separately; this PR does not
modify Chaz's workflows, migration, images or repository settings. Replacement
validation requires the existing active README workflow before artwork writes.
