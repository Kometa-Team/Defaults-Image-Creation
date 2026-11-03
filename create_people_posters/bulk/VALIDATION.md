# Reproducible validation and qualification limits

## Public revision validation

The portable candidate was built on a Linux amd64 Docker engine from a Windows
checkout, normalizing copied runtime text to LF. Both release and test stages built
successfully. **148 offline tests passed**: standalone checkpoint/recovery/disk-full
contracts, native partial clone with REST unavailable, historical-blob exclusion,
incremental fast-forward and rewrite rejection, cooperative pins/read-only mounts,
optional ZFS registration, existing COLLECTION/font/pixel contracts, and read-only
completed-batch validation including tampering and active-writer refusal.

The interruption fixture explicitly selects one worker because it asserts a precise
one-person stop boundary; a separate test checks the new two-worker default. The
first run exposed that old implicit-default assumption; it was corrected before the
complete passing run. No renderer/font contract was relaxed.

The release image also downloaded **20 fresh upstream PNGs** pinned to commit
`7581953a1210de8086f5256715efb1787068794c` and verified their Git blob IDs and complete
decoding. A bounded two-worker five-style run produced **100 JPEGs**. All 100 matched
the retained Linux reference JPEG hashes and typography fields. The new read-only
validator accepted all 100. A no-op resume preserved every poster's SHA256, size and
nanosecond mtime. These are fresh-source compatibility results, not a full-library run.

Compose was exercised with a separate **eight-image synthetic Git fixture**, ordinary
native Linux bind mounts and the normal mandatory-pin entrypoint. Full fixture audit,
cooperative pin registration, default two-worker diiivoy rendering, read-only validation
and no-op resume passed. Compose syntax/interpolation also passed. The synthetic fixture
is not represented as an upstream GitHub source revision.

No public-revision full regeneration, remote poster publication, actual pin retirement
or destructive cleanup was tested or performed. Existing server images/data were not
changed. Retained private logs, container names, NAS paths, machine identifiers, screenshots
and downloaded portraits are intentionally excluded from the contribution.

## Run the offline suite

From the repository root:

```bash
docker build --target test -t people-bulk-tests -f create_people_posters/bulk/Dockerfile .
docker run --rm --network none --read-only --cpus 4 --memory 8g \
  --tmpfs /tmp:rw,size=4g,mode=1777 people-bulk-tests
docker build --target release -t kometa-people-bulk:local \
  -f create_people_posters/bulk/Dockerfile .
```

The dedicated PR workflow runs these builds/tests with read-only GitHub permissions
and no persisted checkout credentials. Existing daily/provenance workflows are unchanged.

## Repeat a bounded fresh-source compatibility test

This optional network test fetches only the explicit 20-image historical fixture, not
the complete transparent source payload. It needs roughly a few hundred MiB of source
and output space rather than the full production clone budget. Choose **new** Docker
volume names on each attempt; retain earlier evidence rather than clearing volumes.

```bash
IMAGE=$(docker image inspect --format '{{.Id}}' kometa-people-bulk:local)
SMOKE="people-bulk-smoke-$(date -u +%Y%m%dT%H%M%SZ)"
REVIEW="$PWD/create_people_posters/bulk"
docker volume create "$SMOKE-source"
docker volume create "$SMOKE-batches"
docker run --name "$SMOKE-fetch" --user 0:0 --read-only \
  --tmpfs /tmp:rw,size=256m,mode=1777 \
  --mount "type=volume,src=$SMOKE-source,dst=/fixture" \
  --mount "type=bind,src=$REVIEW,dst=/review,readonly" \
  --entrypoint python "$IMAGE" -B /review/prepare_canary_source.py \
  --selection /review/canary-selection.json --destination /fixture/transparent

docker run --name "$SMOKE-render" --network none --read-only --cpus 4 --memory 8g \
  --tmpfs /tmp:rw,size=512m,mode=1777 \
  --mount "type=volume,src=$SMOKE-source,dst=/fixture,readonly" \
  --mount "type=volume,src=$SMOKE-batches,dst=/batches" \
  --mount "type=bind,src=$REVIEW,dst=/review,readonly" \
  --entrypoint python "$IMAGE" -B -u /opt/people/create_people_posters/bulk_regenerate.py \
  --source /fixture/transparent --output /batches/canary --canary 20 \
  --canary-selection /review/canary-selection.json \
  --styles bw diiivoy diiivoycolor rainier signature --workers 2

docker run --rm --network none --read-only \
  --mount "type=volume,src=$SMOKE-batches,dst=/batches,readonly" "$IMAGE" \
  --validate --output /batches/canary --json
```

The fixture explicitly overrides the production entrypoint because a sparse 20-image
checkout cannot truthfully supply a full-repository source audit/pin. The source is
still mounted read-only and every selected payload is bound to the pinned upstream
commit/blob. **This exception is for the bounded compatibility fixture only.** Use the
normal entrypoint, complete audit and registered source pin for real regeneration.
No-op fixture resume likewise uses the explicit Python entrypoint, original source and
batch mounts, and `--resume --output /batches/canary --workers 2`.

After completion inspect `/batches/canary/.bulk/review/index.html` and `report.json`
in the output volume. Expected: 100 valid JPEGs, 20/style, no failed/pending/skipped
outputs. Tests verify established dimensions/modes/fonts/COLLECTION calls; human
visual acceptance remains required. Keep the volumes/checkpoints if diagnosis is needed.

## Historical Gen10 evidence, anonymized

Before public portability changes, the held-snapshot version was qualified on a
Linux NAS with 48 physical CPU cores and ample RAM. The complete transparent source
contained **15,434 PNGs / 78,780,859,039 bytes**; every file and all eight integrity
acceptance inputs passed Git/Pillow audit. The original 139-test server suite passed.
Graceful interruption, recreated-container resume, restart and independent read-only
status passed; 700 staged qualification outputs matched their reference hashes across
11 bounded batches. No production poster was replaced.

Sequential 20-person/all-five cases used 16 CPU / 24 GiB limits and warm ZFS cache:

| Workers | Rendering posters/min | Peak process RSS MiB |
|---:|---:|---:|
| 1 | 133.94 | 597 |
| 2 | 170.06 | 1,095 |
| 4 | 171.22 | 2,121 |
| 8 | 142.69 | 3,946 |
| 2, repeat | 176.97 | 1,098 |

Two workers were the lowest count within 10% of the fastest case and are the public
default. These rates exclude source admission/review, include durable rendering and
checkpoint operations, and are not throughput promises for other hardware or cold
storage. The new generic guide uses 4 CPU / 8 GiB caps; adjust caps and repeat a bounded
canary/benchmark on your machine. The old server's exact immutable image remains the
correct runtime for its existing batches; do not substitute the public build on resume.

The generalized ZFS host adapter has isolated protocol coverage, but was not redeployed
to the qualified NAS. Linux amd64 and native ext4 Docker storage were exercised for the
public revision. ARM, rootless Docker, SELinux-specific mounts, remote checkpoint
filesystems, native Windows/macOS checkpoint binds and future GitHub source advances
on that NAS have not been qualified. Checkpoint storage outside the supported native
filesystem set is deliberately rejected.

## Publication boundary

Poster publication is **unsupported**, not merely disabled by a default flag. No
poster push/merge command exists. Experimental reconciliation/private payload tests
exercise changed-and-reverted history, newer daily outputs, source changes, tampered
receipts, rewritten baselines and remote drift. They do not validate an actual publisher
or eliminate the race between a final observation and a future push. Any future
publication implementation needs explicit authority and atomic expected-head/ref
protection; never infer permission to overwrite current daily updates from a completed
render or a private staging token.
