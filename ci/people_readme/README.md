# People README publication

`workflows/` contains the updated `.github/workflows/readme.yml` for each of
the seven People image repositories. `targets.json` records the inspected
baseline blob SHA for each file. These files are deployment sources for those
repositories; they do not execute as workflows in Defaults-Image-Creation.

Install the corresponding workflow in **all seven destination repositories
first**, then enable the updated API publisher. The workflow's optional
`batch_id` input puts a unique dispatch ID in the run name. Manual dispatches
without this input and ordinary pushes continue to work. Generated image links
use the actual repository and triggering branch, including in private sandboxes.
Preparation and commit both use that branch and retry network errors, incomplete responses,
HTTP 429, rate-limited 403 and HTTP 500/502/503/504 up to four attempts with
exponential delays and rate-limit headers (maximum delay 300 seconds).
Permission, missing-resource and validation errors fail immediately.

The publisher starts all needed jobs before waiting, persists dispatch IDs,
run IDs and attempts in the existing publication ledger and exported manifest,
and grants up to three workflow attempts. Reruns wait for a higher `run_attempt`
so GitHub's old failed result cannot be mistaken for the new result. A successful
run with stale output gets a fresh dispatch. Exhausted retries fail the batch,
while still collecting results from the other repositories.

Verification reads Git blobs from one branch snapshot and checks exact raw
image URLs in the top-level README and each affected letter README. It includes
repository, branch, path, case and extension, verifies blob hashes, and confirms
the branch did not move during the checks. Mentioning a person's name is
insufficient. Published image blobs must still match the batch receipts.

On an incomplete batch, keep its files and resume the same batch. An interrupted
or timed-out wait reuses the recorded run; already verified repositories are
rechecked without dispatching jobs or uploading images. A new explicit run after
exhausted retries grants a fresh retry budget for the failed repositories.

The API publisher treats README completion as required whenever
`UPDATE_TRIGGER_READMES=true` (default). `UPDATE_REQUIRE_README_DISPATCH=false`
does not bypass verification. Explicitly disabling README processing still
records `disabled`, preserving the existing opt-out and local Git behavior.

Offline validation:

```powershell
python -m pytest -q create_people_posters/tests/test_people_github.py create_people_posters/tests/test_people_readme_publication.py create_people_posters/tests/test_people_readme_workflows.py
```
