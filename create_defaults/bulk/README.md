# Defaults Bulk Generator (Packages B/C)

Run from the repository root using Python 3.13 on Windows. No command below
publishes artwork. Dependencies are pinned in `create_defaults/requirements-bulk.txt`.
The checked-in English category catalog and local Python rendering flow are
implemented in Package C. The production PowerShell workflow is unchanged.

```powershell
py -3.13 -m create_defaults.bulk list-categories
py -3.13 -m create_defaults.bulk list-languages
py -3.13 -m create_defaults.bulk validate-definitions --definitions create_defaults/bulk/examples/genre.yml
py -3.13 -m create_defaults.bulk plan --definitions create_defaults/bulk/examples/genre.yml --category Genre --language en --manifest config/genre-infrastructure-plan.json
py -3.13 -m create_defaults.bulk discover-assets --directory logos_genre
py -3.13 -m create_defaults.bulk audit-colors
py -3.13 -m create_defaults.bulk --offline remote-inventory --path genre/Action.jpg
```

Global configuration flags precede the command. Manifest output is exclusive:
choose a new filename rather than overwrite evidence. `remote-inventory --refresh`
explicitly fetches metadata from `Kometa-Team/Default-Images` / `master`, without a
clone. `--download --path <exact-path>` explicitly downloads one verified image;
neither happens implicitly. Missing/stale/inaccessible metadata are distinct.
`suggest-colors --policy <JSON> --logo <PNG> --poster <ID> --category <category>`
requires explicit versioned `ColorPolicy` values and returns proposals, not approval.

## Python APIs

- `Config.load(...)`: explicit arguments > file > supported environment > defaults.
- `load_definitions(files, profiles_path=...)`: safe category YAML, one named profile layer.
- `Planner(config).plan(definitions, translations, ...)`: validated deterministic manifest.
- `Translations({language: local_path}).resolve(...)`: offline lookup/casing/placeholders/fallback provenance.
- `RemoteInventory(store, config, client)`: snapshot, refresh, exact lookup, selective verified fetch.
- `ColorRegistry(store, policy, authorized_reviewers=...)`: historical occupancy, policy evaluation, reservations and audited approval.
- `discover_assets(...)`: read-only source classification; no definition creation/deletion.
- `Store(path)` / `Workspaces(store, root)`: local SQLite transactions/events and owned retention/cleanup.
- `PersistentWorkers(store, config, limits)`: direct composer API execution, durable receipts and bounded persistent spawn workers.

The worker API must be called from an import-safe entry point:

```python
from create_defaults.bulk.config import Config
from create_defaults.bulk.state import Store
from create_defaults.bulk.workers import PersistentWorkers, WorkerLimits, tasks_from_manifest

def execute_verified_plan(manifest):
    config = Config()
    store = Store(config.cache_dir / "state.sqlite")
    limits = WorkerLimits(workers=2, recycle_after=200)
    with PersistentWorkers(store, config, limits) as pool:
        return pool.run(tasks_from_manifest(manifest))

if __name__ == "__main__":
    # A caller supplies an explicitly reviewed, current, render-ready manifest.
    pass
```

No worker-render CLI or full-category generator was provided in B. The default
adapter uses the existing composer without changing fonts/layout/encoding. B tests
exercise orchestration with small deterministic byte artifacts plus an injected
composer API check, not actual poster throughput or new visual parity evidence.
New generated parents require verified hashes before dependent planning; staged
category integration belongs to C. Overlay/RTL/preview adapters belong to D.

## Bounds and Recovery

At most one active task per worker; input queues have capacity one. Each worker
has an isolated bounded OS result pipe with at most one outstanding response.
Tasks are JSON metadata, capped individually at
one MB and collectively at 64 MiB by default; the catalog also has a job-count cap.
No full rendered collection is retained in RAM. Artifact promotion is byte-capped.
Worker RSS is sampled; per-worker budgets sum to the configured worker budget.
These checks are not OS-enforced allocation ceilings or real-workload sizing evidence.

Timeouts/errors/crashes have bounded retries. Retained failed jobs require
`retry_failed=True`. Cancellation accepts an object with `is_set()` and reaps
owned workers; abrupt parent loss requires lease expiry before another owner
recovers the job. Verified outputs are SHA/receipt checked before reuse. Corruption
and changed destination ownership fail closed; no automatic force/overwrite exists.
Worker-private requests prevent option mutation leaking into another poster.

Receipts, output reservations and input hashes bind resume to exact specifications.
Interrupted promotion can resume only when the owned final bytes match a fresh
verified result. Workspace cleanup requires its token and an explicit retention
period, and cannot remove live-job workspaces or source artwork.

Metrics record wall time, jobs/sec, worker starts/PIDs/recycling, in-flight maximum,
parent/worker RSS, worker I/O counters and verified-cache hit rate. Disk counters
are OS-level worker counters, not complete physical-disk profiling. Native Linux
execution, actual poster workloads and comparison with legacy execution remain
unclaimed until their respective validation gates.

## Package C Local Generation

All 21 poster categories are in `catalog/*.yml`, with one explicit profile layer
in `catalog/profiles.yml`. Stable IDs are stored in the data, not source-line
numbers. Named generators expand Awards years, Best Of years, Separator variants
and Content Rating codes. Production generation never reads the legacy capture
or PowerShell source. `migration.py` is a development-only extraction/comparison
tool and refuses replacement unless explicitly requested.

```powershell
py -3.13 -m create_defaults.bulk --output-dir config/my-posters/output --cache-dir config/my-posters/cache --workspace-dir config/my-posters/work generate --category Based --workers 2 --report config/my-posters/run-01.json
```

Use `--category All` to explicitly request all English poster categories, not
overlays. Do not run a full batch merely to preview a category. Repeat a run with
a new report filename: outputs reuse their verified receipts automatically.
`--poster <stable-id>` narrows the selected category and includes real parents.
Timeouts, retries and recycling are configurable; failed retained jobs require
`--retry-failed`. An incomplete generation returns exit code 3.

`generation.generate(...)` stages parents before dependent planning and uses one
persistent spawn pool across stages. It returns per-stage execution evidence and
a combined canonical manifest. Successful runs clean only their token-owned
scratch directory; SQLite, receipts and final outputs remain for resume. Failed
and interrupted workspaces remain available for diagnosis/owned cleanup.

Changed specifications may replace only their own exact, previously verified
bytes. SQLite reservations prevent a second unfinished version or different
logical job from taking the destination. Atomic replacement checks the prior
SHA under the reservation lock. Restoring an older fingerprint creates a new
receipt generation; historical verified job records are never rewritten.

English fitting sizes are pinned to the approved captured caption/font/size.
A changed fitted caption must supply new hash-bound fitting evidence or an
explicit fixed-layout definition; no silent refitting or fallback is performed.
Other-language catalog applicability/layout approval remains Package D work.

Generate an independent local sample review without changing tracked summaries:

```powershell
py -3.13 -m create_defaults.bulk.category_check Playlist --evidence-root config/my-review --samples 2
```

Use a fresh evidence directory. `--refresh-summary` explicitly updates the compact
tracked summary after fresh validation; it is not required just to view samples.

See `../PACKAGE_C_REPORT.md` and `catalog/audit/package-c-evidence.json` for exact
coverage, real-workload measurements and review limitations. No artwork is
published, no legacy speedup is assumed, and no production cutover is enabled.
