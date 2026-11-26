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
