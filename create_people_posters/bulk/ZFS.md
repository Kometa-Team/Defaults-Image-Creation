# Optional ZFS source snapshots

Ordinary Linux Docker bind mounts and cooperative source pins are the default.
ZFS adds host-enforced immutable source versions so the mutable Git checkout can
advance without modifying active batches. It is not required for rendering.

An administrator must provision a **dedicated source dataset** whose mountpoint is
the transparent Git repository, plus a persistent pin-registry directory writable by
the container UID/GID. Never reuse an unrelated dataset. This adapter does not create
datasets, install software, change pool/share properties or remove snapshots/holds.

Example configuration (replace with your actual dedicated dataset and registry):

```bash
export PEOPLE_SOURCE_DATASET=tank/people/transparent
export PEOPLE_PIN_REGISTRY=/srv/people-bulk-data/checkpoints/source-pins
export PEOPLE_CONTAINER_USER=1000:1000
COMMIT='<exact 40-character commit from source status>'
IMAGE='<immutable sha256: Docker image ID>'
SCRIPT=create_people_posters/bulk/source_snapshot.sh
bash "$SCRIPT" plan "$COMMIT" "$IMAGE"
```

The plan records the current host, dataset GUID, native mountpoint, registry, source
commit and image ID. Review all fields; the authorization token is bound to that plan:

```bash
FREEZE_PLAN_SHA='<reviewed plan_sha256>'
bash "$SCRIPT" freeze "$COMMIT" "$IMAGE" "FREEZE:$FREEZE_PLAN_SHA"
bash "$SCRIPT" verify "$COMMIT" "$IMAGE"
```

Freeze uses the same OS lock as source sync, checks Git identity, creates snapshot
`<dataset>@people-<commit>` if absent, applies persistent hold `kometa-people-bulk`,
then audits every Git PNG and all eight acceptance paths through a read-only mount.
Registration fails closed and retains snapshot/hold/report on failure. Existing
records must match their audit digest and snapshot GUID.

For rendering, replace the ordinary source mount with the snapshot's native path:

```bash
SOURCE_PATH=$(zfs get -H -o value mountpoint "$PEOPLE_SOURCE_DATASET")
SNAPSHOT="$SOURCE_PATH/.zfs/snapshot/people-$COMMIT"
# Include both in the normal render/resume mount array:
# --mount "type=bind,src=$SNAPSHOT,dst=/source,readonly"
# --mount "type=bind,src=$PEOPLE_PIN_REGISTRY,dst=/pins,readonly"
# Use --source-pin "/pins/$COMMIT.json" instead of the cooperative-checkout pin.
```

Verify the hold/GUID with the host adapter before launch/resume; the unprivileged
container verifies the registered pin/audit and read-only mounts. It does not have
access to ZFS administration. The snapshot remains immutable while explicitly
invoked Git synchronization advances the separate mutable checkout. A deliberate
cooperative checkout pin still blocks helper checkout changes, so use one pin strategy
per source store rather than creating a checkout pin first for the ZFS workflow.

Holds prevent ordinary destruction until deliberately released by an administrator;
they are not protection against that administrator. No retention expiry, destroy,
release, rollback or cleanup operation is implemented. Snapshot-exclusive usage may
grow when a mutable checkout advances. The original held-snapshot workflow was
qualified on a Linux NAS; the generalized adapter also has isolated protocol tests.
New pool configurations still require their own bounded canary and recovery checks.
