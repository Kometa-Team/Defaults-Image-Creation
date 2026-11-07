# Bulk People poster regeneration with Docker

Generate private staged posters using the existing Python People renderer, including
its merged COLLECTION typography. This is separate from the daily acquisition and
Logscan workflow. No GPU, background-removal models, API credentials, SSH keys or
Unraid installation are needed. **There is no GitHub poster publisher in this workflow.**

Supported styles: `bw`, `diiivoy`, `diiivoycolor`, `rainier`, `signature`.
The default is **two workers**, with an admitted range of 1–8 and a RAM check.
BW remains grayscale; the other JPEGs are RGB. Output is 2000 × 3000 with exact
source-name casing and established typography. Existing production posters are
never a render destination.

## Requirements and build

Use a Linux Docker Engine and Docker Compose v2+ (the examples also work with
Compose v5). SQLite/checkpoints need persistent **ext4, XFS, Btrfs or ZFS** storage.
Do not put checkpoints on SMB/NFS, `/mnt/user` FUSE, tmpfs or container overlay.
Docker Desktop users need a native Linux VM volume for state; direct Windows/macOS
host bind mounts are not qualified. Linux amd64 was tested; other architectures
are not yet qualified. Rootless Docker/SELinux hosts may need site-specific UID
mapping or bind labels; do not disable host protections to bypass permissions.

The public transparent repository currently contains about 73 GiB of PNGs.
Checkout plus Git objects used about 147 GiB in qualification. Initial clone admits
**279.2 GiB free** by default (a conservative 128 GiB source ceiling), before download.
Outputs, receipts, retained versions and reserve need additional space. Five styles
projected roughly 177 GiB of JPEGs in one small sample; inspect your dry-run rather
than treating that as a fixed requirement.

```bash
git clone https://github.com/Kometa-Team/Defaults-Image-Creation.git
cd Defaults-Image-Creation
# Check out the reviewed release/commit containing this workflow.
docker build --target release -t kometa-people-bulk:local \
  -f create_people_posters/bulk/Dockerfile .
docker image inspect --format '{{.Id}}' kometa-people-bulk:local
```

Use the resulting immutable image ID for a batch and all its resumes. Do not silently
rebuild or substitute another image mid-batch. The base image and Python dependencies
are pinned; the runtime seal verifies the reviewed renderer, code, fonts and artwork.
LF normalization makes Windows and Linux build inputs agree without changing renderer
semantics. See [validation and limitations](VALIDATION.md).

## Configure ordinary bind mounts

The following are **Bash commands on the Linux Docker host**. PowerShell users can
enter a Linux shell/VM first; Windows native paths are not interchangeable with these
host paths. Choose storage outside the repository and all production image repositories.

```bash
export PEOPLE_ROOT="$HOME/people-bulk-data"
export PEOPLE_UID="$(id -u)" PEOPLE_GID="$(id -g)"
export PEOPLE_BATCH=canary-01 PEOPLE_PIN=source-01
export PEOPLE_STYLES=diiivoy PEOPLE_WORKERS=2
export PEOPLE_IMAGE=kometa-people-bulk:local
mkdir -p "$PEOPLE_ROOT"/{source/transparent,staging,checkpoints,reports}
mkdir -p "$PEOPLE_ROOT/staging/$PEOPLE_BATCH" "$PEOPLE_ROOT/checkpoints/$PEOPLE_BATCH"
IMAGE=$(docker image inspect --format '{{.Id}}' "$PEOPLE_IMAGE")
export PEOPLE_IMAGE="$IMAGE"
MOUNTS=(
  --mount "type=bind,src=$PEOPLE_ROOT/source/transparent,dst=/source,readonly"
  --mount "type=bind,src=$PEOPLE_ROOT/staging,dst=/batches"
  --mount "type=bind,src=$PEOPLE_ROOT/checkpoints/$PEOPLE_BATCH,dst=/batches/$PEOPLE_BATCH/.bulk"
)
```

For a root shell, select a non-root runtime UID/GID and give it ownership of these
new directories. The image defaults to UID/GID 1000:1000. The optional `.env.example`
contains the same settings; copy it to `.env` beside `compose.yaml` and edit it if
you prefer a persistent Compose configuration. Environment variables override `.env`.
Do not put credentials in it. All bind targets must exist; Compose will not silently
create missing host directories.

In examples below, run `docker compose -f create_people_posters/bulk/compose.yaml ...`
from the repository root. The explicit `PEOPLE_BATCH` value is part of recovery state.
Save the environment settings, image ID and command with your own operational notes.

## Clone, synchronize, audit and pin transparent sources

Initial source acquisition is explicit and uses native Git, not the GitHub REST tree
API. It keeps commit/tree ancestry, filters historical blobs and hydrates the current
checkout. Never run the initial clone against existing data.

```bash
docker compose -f create_people_posters/bulk/compose.yaml run --rm source \
  clone --source /workspace/transparent --confirmed-parent /workspace
docker compose -f create_people_posters/bulk/compose.yaml run --rm source \
  status --source /source
```

Before pinning, a future incremental refresh is:

```bash
docker compose -f create_people_posters/bulk/compose.yaml run --rm source \
  sync --source /source
```

Sync is one-way and fast-forward-only; dirty checkouts, unexpected origins and
rewritten/divergent history are rejected. Preserve failures; do not reset repositories
or delete locks. Save source status and sync output to new dated logs if needed.

Audit the **entire** checkout, then register a persistent cooperative pin:

```bash
AUDIT="source-audit-$(date -u +%Y%m%dT%H%M%SZ).json"
docker compose -f create_people_posters/bulk/compose.yaml run --rm audit \
  audit --source /source --report "/reports/$AUDIT"
docker compose -f create_people_posters/bulk/compose.yaml run --rm source \
  pin --source /source --batch-id "$PEOPLE_PIN" --audit-report "/reports/$AUDIT"
```

Audit checks Git blob bytes, Pillow verify/reopen/full decode, and eight retained
integrity acceptance paths. Pin creation requires a complete successful report for
the exact clean revision. The pin is stored under `.git/people-bulk-pins/`; render
mounts the whole source read-only. Cooperative pins prevent this helper from changing
the checkout. They do not protect against an administrator editing host files, so
reserve this directory exclusively for the bulk workflow. Rendering also verifies
source hashes against the frozen inventory before and after each input.

**Pin retirement is deliberately not implemented.** For future source revisions,
retain this pinned checkout and select a new `PEOPLE_ROOT` for a new audited clone.
`sync --fetch-only --source /source` can inspect newly fetched history without changing
pinned files. Do not manually remove pins to force a sync. Sites needing efficient
ongoing versions can use the optional [ZFS adapter](ZFS.md).

## Canary, dry-run and full regeneration

Compose's default command is a **20-person canary**, not a full regeneration:

```bash
docker compose -f create_people_posters/bulk/compose.yaml up -d render
docker compose -f create_people_posters/bulk/compose.yaml logs -f render
```

Ctrl+C leaves detached rendering running. Canary review files are under
`$PEOPLE_ROOT/checkpoints/$PEOPLE_BATCH/review/`. Check all requested styles,
long/short names, accents/apostrophes, subject placement and COLLECTION typography.
For all five styles set `PEOPLE_STYLES=bw,diiivoy,diiivoycolor,rainier,signature`
**before creating the batch**. Review automation does not replace human acceptance.

For a full run choose **new empty** batch/checkpoint directories, retain the same
source pin, and explicitly omit `--canary`. Commands below use ordinary Docker bind
mounts and match the Compose layout. Never reuse a previous batch for a new run.

```bash
export PEOPLE_BATCH=full-diiivoy-01
test ! -e "$PEOPLE_ROOT/staging/$PEOPLE_BATCH"
test ! -e "$PEOPLE_ROOT/checkpoints/$PEOPLE_BATCH"
mkdir -p "$PEOPLE_ROOT/staging/$PEOPLE_BATCH" "$PEOPLE_ROOT/checkpoints/$PEOPLE_BATCH"
IMAGE=$(docker image inspect --format '{{.Id}}' "$PEOPLE_IMAGE")
NAME="people-$PEOPLE_BATCH"
MOUNTS=(
  --mount "type=bind,src=$PEOPLE_ROOT/source/transparent,dst=/source,readonly"
  --mount "type=bind,src=$PEOPLE_ROOT/staging,dst=/batches"
  --mount "type=bind,src=$PEOPLE_ROOT/checkpoints/$PEOPLE_BATCH,dst=/batches/$PEOPLE_BATCH/.bulk"
)
docker run --rm --network none --read-only --user "$PEOPLE_UID:$PEOPLE_GID" \
  --cpus 4 --memory 8g --tmpfs /tmp:rw,size=512m,mode=1777 "${MOUNTS[@]}" "$IMAGE" \
  --dry-run --source /source --source-pin "/source/.git/people-bulk-pins/$PEOPLE_PIN.json" \
  --output "/batches/$PEOPLE_BATCH" --styles "$PEOPLE_STYLES" --workers "$PEOPLE_WORKERS"
```

Review `issues` and require `disk_space_sufficient=true`. The dry-run's successful
exit alone does not mean capacity is sufficient. Then, when you choose to launch:

```bash
docker run -d --name "$NAME" --restart=no --network none --read-only \
  --user "$PEOPLE_UID:$PEOPLE_GID" --cpus 4 --memory 8g \
  --tmpfs /tmp:rw,size=512m,mode=1777 "${MOUNTS[@]}" "$IMAGE" \
  --source /source --source-pin "/source/.git/people-bulk-pins/$PEOPLE_PIN.json" \
  --output "/batches/$PEOPLE_BATCH" --styles "$PEOPLE_STYLES" --workers "$PEOPLE_WORKERS"
```

Checkpoint inventories, manifests, receipts and logs persist in the separate native
bind. Output is `$PEOPLE_ROOT/staging/$PEOPLE_BATCH/<style>/<initial>/Images/<name>.jpg`.
Initial hashing of a full source library can take time; planning/resume progress is
logged. Full batches do not automatically build the canary gallery.

## Status, failures, stop and resume

For a Compose-created canary obtain its Docker name first (the leading slash is accepted by Docker):
`NAME=$(docker inspect --format '{{.Name}}' "$(docker compose -f create_people_posters/bulk/compose.yaml ps -a -q render)")`.
For a full batch retain the `NAME` above. Restore original environment/mount settings
after reconnecting; never generate a new batch name when resuming.

```bash
STATUS_MOUNTS=(
  --mount "type=bind,src=$PEOPLE_ROOT/staging,dst=/batches,readonly"
  --mount "type=bind,src=$PEOPLE_ROOT/checkpoints/$PEOPLE_BATCH,dst=/batches/$PEOPLE_BATCH/.bulk,readonly"
)
# Active renderer: sharing its PID namespace makes identity verification accurate.
docker run --rm --network none --read-only --pid="container:$NAME" \
  "${STATUS_MOUNTS[@]}" "$IMAGE" --status --output "/batches/$PEOPLE_BATCH" --json
docker logs --tail 50 "$NAME"
grep -n 'Input failed:' "$PEOPLE_ROOT/checkpoints/$PEOPLE_BATCH/run.log" || true
```

For stopped jobs omit `--pid=container:...`. Alternatively `docker compose ... run --rm
inspect` supplies independent read-only status, but without shared PID visibility
it may report the active renderer's identity as unverified. Exit 2 means unavailable
or contended status. Counts and latest errors are reported; there is no separate
failed-row management interface.

```bash
docker stop --timeout 120 "$NAME"
docker inspect --format '{{.State.Status}} exit={{.State.ExitCode}}' "$NAME"
```

Expect 130 for graceful interruption or 0 if already complete. Preserve unexpected
exits and inspect logs. Docker may force termination if the timeout expires; the
checkpoint/receipt recovery is designed for interrupted writes, but inspect the result.
The restart policy is intentionally `no`; do not start a second writer.

Resume using the exact original image, pin, batch paths and mounts:

```bash
test "$(docker inspect --format '{{.State.Running}}' "$NAME")" = false
RESUME_NAME="$NAME-resume-1"
docker run -d --name "$RESUME_NAME" --restart=no --network none --read-only \
  --user "$PEOPLE_UID:$PEOPLE_GID" --cpus 4 --memory 8g \
  --tmpfs /tmp:rw,size=512m,mode=1777 "${MOUNTS[@]}" "$IMAGE" \
  --resume --source-pin "/source/.git/people-bulk-pins/$PEOPLE_PIN.json" \
  --output "/batches/$PEOPLE_BATCH" --workers "$PEOPLE_WORKERS"
NAME=$RESUME_NAME
```

Valid completed receipts/JPEGs are reused without rewriting their posters. Invalid
or missing outputs can be regenerated. Existing failures remain unless you explicitly
add `--retry-failed`; changed source/runtime identity is rejected. Never delete a
runner lock, edit the checkpoint or replace a pinned source to make resume proceed.

## Read-only completed-output validation

After the renderer stops, validate using the **same image**, with only read-only
batch/checkpoint mounts:

```bash
docker run --rm --network none --read-only "${STATUS_MOUNTS[@]}" "$IMAGE" \
  --validate --output "/batches/$PEOPLE_BATCH" --json
```

Validation takes a shared nonblocking lock and checks SQLite integrity, completed
counts, manifest/inventory/runtime identities, each receipt/hash/filename, JPEG
dimensions/mode, complete Pillow decoding and COLLECTION receipt contracts. It
detects unexpected JPEGs and never repairs state. Exit 0 means valid, 1 invalid,
2 unavailable because a writer owns the batch. `--status` is a progress report,
not a substitute for this validation. Visual acceptance and publication authorization
are separate.

## Safe disposal of containers

Keep source pins, snapshots, checkpoints, receipts, posters and recovery evidence.
List containers and save logs before removing a reviewed **stopped** container:

```bash
docker ps -a --filter name=people- --format 'table {{.Names}}\t{{.Status}}'
docker logs "$NAME" > "$PEOPLE_ROOT/reports/$NAME.log" 2>&1
test "$(docker inspect --format '{{.State.Status}}' "$NAME")" = exited
docker rm "$NAME"
```

For Compose containers, `docker compose -f create_people_posters/bulk/compose.yaml rm render`
removes the stopped service container after confirmation. Avoid `-f`, `-v`, wildcard
removal and Docker prune commands. Container removal discards its local layer/logs;
bind-mounted data remains. **No source/batch/snapshot cleanup or pin-release command
is provided.** Container disposal is not production cleanup.

## Poster publication is unsupported

Rendering has no GitHub credentials, publication switch, scheduler or network access.
Do not mount production repositories into `/batches`. The experimental
`bulk_reconcile.py` can inspect history and prepare a **private** payload only after
an exact `STAGE:<plan_sha256>` authorization. Its fixtures exclude changed source or
destination image paths (including changes later reverted), reject rewritten history
and stop on remote drift. These are local regression results, **not end-to-end
qualification of a publisher**. No commit/push/production replacement operation
exists here. Every plan/payload records `publication_authorized=false`; a staging
token never authorizes publication. Do not use this candidate to overwrite newer
daily poster updates. Any actual publication needs a separately reviewed implementation
and explicit authorization.
