# People Posters storage maintenance

This is independent People Posters maintenance based on main
`ef3b2713cf5dcab9b92395321c6be3fdf1efdbce`. No Phase 5 integration,
publication, old-file deletion or merge is authorized by this change.

## Findings

Both inline and staged recovery wrote every raw TMDB candidate to
`edge_chop_recovery/candidates/<safe_name>/`. Adobe/rembg screening PNGs
also used that directory. Neither success nor failure retired these files.
Person-based filenames also allowed separate attempts to overwrite one another.
TemporaryDirectory cleaned normalization, colorization and local BiRefNet
staging on ordinary exits, including failures, while an abrupt process exit
could strand them in the system temporary directory without a recovery owner.

Rollback transaction backups are intentional durable safety evidence. They are
not disposable candidate downloads. Existing originals, source history,
attempted-candidate CSV, exhausted-name history, reports, checkpoints and
publication receipts must not be inferred disposable from age or filename.

The repair moves new attempt work into
`edge_chop_recovery/operations/<uuid>/work/`. Each operation inventories its
files, directories, sizes and SHA-256 hashes. A per-person lease (Unicode NFC
and case folded) prevents overlapping rollback operations for the same person.
Different people own separate trees. Processing leases are never stolen based
on PID or age. A crashed processing lease requires explicit operator review.

After transaction commit, final selected-warning QA and a durable recovered
checkpoint, cleanup preserves and verifies the exact downloaded source in
`original/.recovery_sources/<sha256>/source.<extension>`, the normalized original
and the final output files. It then removes only unchanged inventoried scratch.
The source archive is outside scratch and never a renderer input. Candidate,
precheck, normalization, colorization, temporary render and redundant temporary
backup files can then be discarded. Rollback journals/backups remain untouched.

Stage-only, exhausted, failed and retryable attempts retain their scratch. A
staged candidate is not treated as recovered. A successful staged postcheck now
saves its recovered checkpoint before enabling cleanup. Cleanup warnings do not
turn accepted artwork into a failed render or authorize publication.

## File lifecycle

| Artifact | Created / reused by | Retention and cleanup |
| --- | --- | --- |
| `posters/`, batch `posters/`, `input/` | TMDB/download/list selection | Retry inputs; retain until verified batch cleanup. Persistent inputs have no automatic age policy. |
| `Downloads/other`, `Downloads/color` | audit + DDColor + prep_dirs | Colorization staging; validated colorization can remove its grayscale staging copy; no new behavior here. Model/vendor caches are durable and separate. |
| `people_dirs/Downloads/*.jpg` | prep_dirs/recovery | Background-removal queue. BiRefNet preserves the original before removing a processed queue entry. |
| `original/`, `.history/`, `.recovery_sources/` | background removal/recovery/renderer | Original artwork and selected source evidence. Scratch cleanup cannot delete them. Batch copies remain subject to the existing verified-publication retention policy. |
| Cutout PNGs and BiRefNet provenance sidecars | background removal; fingerprint/overwrite checks | Reusable successful checkpoints; preserve on retry. Existing overwrite requirements remain unchanged. |
| `sel_downloads/` and intermediate cutout mirrors | background removal | Persistent mirror or isolated batch artifact; no new global pruning. |
| Seven style outputs | renderer + QA | Publishable artwork; preserve bytes and rendering settings. Renderer code is unchanged. |
| Batch `prepared/` and publication plans | publisher | Validated publication staging; retain until all expected receipts are verified and retention expires. |
| Legacy `edge_chop_recovery/candidates/<person>/` | old recovery | Ownership and accepted-output correspondence are unknown. Report as blocked; never delete automatically. |
| New `operations/<uuid>/work/` | one recovery attempt | Temporary after verified success. Failed, exhausted, interrupted and staged work remains retry/evidence material. |
| `operations/<uuid>/scratch.json` | owner inventory/cleanup | Compact retained operational evidence and cleanup state. Not a publication receipt or grant. |
| `transactions/<person-hash>/<uuid>/` | RecoveryTransaction | Durable verified rollback backups/journals; retain even after successful restoration/commit. |
| `recovery-checkpoints.json`, summaries, CSV/JSON reports | recovery/orchestrator | Retained QA/retry evidence; never scratch-cleaned. Mutable current summaries retain their existing semantics. |
| attempted-candidate CSV / exhausted-name history | recovery; normally shared state in batch mode | Durable skip history. Transient failures remain retryable; never prune to save image space. |
| `.orch/` markers, fingerprints, pending receipts | orchestrator | Resumption state; unchanged redo/publication semantics. |
| `state/publication_state.db`, `state/manifests/` | publication ledger | Durable publication receipts outside managed jobs; never scratch-cleaned. |
| Batch manifest and logs | Workspaces | After verified cleanup, retain manifest and last 32 KiB per large log. This explains compact `complete` job directories. |
| Persistent logs, recovery debug reports, benchmark/validation work | individual tools | Evidence/manual retention; report size, do not infer safe deletion. |
| System-temp `edge_chop_*` from older interrupted runs | old TemporaryDirectory | Outside managed ownership; this tool does not scan/delete arbitrary OS temp files. Explicit manual inspection is required. |
| Seven `People-Images-*` repositories, master branches | publisher only | No cleanup writes or recursive traversal for deletion. Repository mapping and publication implementation are unchanged. |

## Batch retention audit

`Workspaces.confirm_published()` first requires `ledger.verified(batch)`, captures
image hashes, sets `published`, timestamps the publication, exports durable
receipts and sets `cleanup_eligible`. Cleanup requires those receipts, an image
catalog, unchanged remaining local images, no active lease, and a publication
age of at least `PEOPLE_BATCH_RETENTION_DAYS` (default **3 days**).

`PEOPLE_FAILED_BATCH_RETENTION_DAYS=14` controls an informational warning; it
does not expire failed batches. Validation-only and no-work batches also remain
retained. Partial publication cannot satisfy verified-publication cleanup.

Automatic batch cleanup runs on a later batch launch (`cleanup_on_launch`, or
`Workspaces.create` for other callers). It is not a timer. A machine with no later
launch can therefore retain eligible work indefinitely. The standalone
`people_workspaces.py` command supports dry-run and explicit `--apply` already.
No changes to that deletion policy are included here.

The live read-only audit found 19 job directories: five compact `complete`
directories and 14 retained jobs. Three jobs were `cleanup_eligible`; all three
had complete verified receipts and were younger than three days. There was no
observed expired published batch, missing-receipt blockage or incomplete
published-to-cleanup transition. Remaining jobs were failed, validation-only or
no-work. They require operator review, not automatic deletion. See the JSON
snapshot for counts, ages, bytes and individual reasons.

Recommended follow-up: schedule the read-only report daily; alert when a fully
verified published job exceeds retention; after separately approving automated
deletion, schedule the existing verified batch cleanup command as an independent
task. Add durable start/finish/count/byte receipts and a common cleanup/activation
lease before making batch deletion unattended. Existing batch cleanup currently
reports batch counts, not exact recovered bytes, and predates this operation
ownership protocol; it is not expanded or invoked by this repair.

## Operator commands

Run from the repository root using the normal People Python environment:

```powershell
python -m create_people_posters.people_cleanup_report --config-dir create_people_posters/config
```

This does not construct writable Workspaces/PublicationState managers, run
models, modify checkpoints, start a batch, contact GitHub or delete files. It
reports category sizes, batch ages/status/receipt and retention blockers,
legacy candidate counts, owned eligible files and recoverable byte estimates.
Inaccessible paths are explicitly reported; totals are lower bounds when any
path is inaccessible. Use `--jobs-dir`, `--state-dir`, `--recovery-root` for
external roots; their corresponding environment overrides are honored by the
CLI. Overlapping roots are counted once. The report does not load `.env`.

Only after separate operator approval, inspect a particular ready operation:

```powershell
python -m create_people_posters.people_cleanup_report --recovery-root PATH --operation UUID
# Explicit deletion, after reviewing the dry run:
python -m create_people_posters.people_cleanup_report --recovery-root PATH --operation UUID --apply
```

`--apply` requires an explicit operation UUID; it cannot select a batch, legacy
person folder or publication repository. It returns exact `removed_files` and
`recovered_bytes`, including partial counts after a filesystem interruption.
Missing inventoried files allow cleanup retries; changed/added files, extra
directories, symlinks, Windows reparse points, hardlinks and malformed paths
block cleanup. No recursive deletion is used. An OS cleanup lock serializes
cleaners and releases on process death; the inert lock file stays as evidence.
Dry runs perform no writes. Automatic processing success invokes the same
cleanup API only for its newly created operation, never an older local folder.

An interruption before the ready checkpoint conservatively retains work. A
later recovery does not adopt or prune an earlier operation automatically.
Manual review must reconcile its lease, checkpoint, sources and QA evidence.
This conservative rule trades some retained storage for recovery safety.

## Security and CI boundary

No historical hashes, protected-file membership, test ID inventories,
production pins, renderer settings, thresholds, publication code or resource
limits are changed. The seven repository/master targets remain identical.

The existing exact-source guard in `ci/people_security_maintenance.py` rejects
the changed `recover_edge_chops.py` bytes. The inherited M7 preservation check
also restricts development to its original milestone scope. These checks remain
enabled: this draft is **not merge-ready**. A separately reviewed exact
predecessor/successor maintenance transition and appropriate CI scope decision
are required before these intended production-source changes can pass the
mandatory integrity gate. PRs #44 and #45 are not altered or integrated here.
The added Windows/Linux workflow exercises storage and existing compatibility
tests; it does not replace or bypass the mandatory historical/security checks.

Local and exact-head remote results, changed-file inventory and before/after
evidence are recorded in the draft PR. No old local images were removed.
