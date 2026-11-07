#!/bin/bash
# Optional host-side ZFS adapter. No dataset creation, destroy, release or cleanup.
set -euo pipefail
mode=${1:?plan, freeze or verify required}
commit=${2:?exact Git commit required}
image=${3:?immutable Docker image ID required}
authorize=${4:-}
dataset=${PEOPLE_SOURCE_DATASET:?Set the dedicated source ZFS dataset}
registry=${PEOPLE_PIN_REGISTRY:?Set the absolute persistent pin registry}
[[ $mode =~ ^(plan|freeze|verify)$ && $commit =~ ^[0-9a-f]{40}$ && $image =~ ^sha256:[0-9a-f]{64}$ ]]
[[ $dataset =~ ^[A-Za-z0-9][A-Za-z0-9_.:/-]*$ ]]
source_path=$(zfs get -H -o value mountpoint "$dataset")
[[ $source_path == /* && $(realpath -e "$source_path") == "$source_path" ]]
[[ $registry == /* && -d $registry && ! -L $registry && $(realpath -e "$registry") == "$registry" ]]
[[ $(zfs get -H -o value sync "$dataset") != disabled ]]
container_user=${PEOPLE_CONTAINER_USER:-$(stat -c '%u:%g' "$source_path")}
dataset_guid=$(zfs get -Hp -o value guid "$dataset")
snapshot="$dataset@people-$commit"
snapshot_path="$source_path/.zfs/snapshot/people-$commit"
description=$(printf 'version=1\nhost=%s\ndataset=%s\ndataset_guid=%s\nsource=%s\nregistry=%s\ncommit=%s\nimage=%s\n' "$(hostname)" "$dataset" "$dataset_guid" "$source_path" "$registry" "$commit" "$image")
digest=$(printf '%s' "$description" | sha256sum | cut -d' ' -f1)
if [[ $mode == plan ]]; then
    printf '%s\nplan_sha256=%s\n' "$description" "$digest"
    exit 0
fi
[[ $(docker image inspect --format '{{.Id}}' "$image") == "$image" ]]
if [[ $mode == freeze ]]; then
    [[ $authorize == "FREEZE:$digest" ]] || { echo 'Exact reviewed plan authorization required' >&2; exit 1; }
    [[ -d $source_path/.git && ! -L $source_path/.git ]]
    [[ -f $source_path/.git/people-bulk-source.lock && ! -L $source_path/.git/people-bulk-source.lock ]]
    exec 9<"$source_path/.git/people-bulk-source.lock"
    flock -x 9
    docker run --rm --network none --user "$container_user" --read-only \
        --tmpfs /tmp:rw,size=64m,mode=1777 \
        --mount "type=bind,src=$source_path,dst=/source,readonly" \
        --entrypoint python "$image" -B /opt/people/create_people_posters/bulk_zfs_source.py identity --source /source --commit "$commit"
    if ! zfs list -H -t snapshot -o name "$snapshot" >/dev/null 2>&1; then zfs snapshot "$snapshot"; fi
    if ! zfs holds -H "$snapshot" | awk '$2=="kometa-people-bulk" {found=1} END {exit !found}'; then zfs hold kometa-people-bulk "$snapshot"; fi
    snapshot_guid=$(zfs get -Hp -o value guid "$snapshot")
    flock -u 9
    docker run --rm --network none --user "$container_user" --read-only --cpus 2 --memory 4g \
        --tmpfs /tmp:rw,size=256m,mode=1777 \
        --mount "type=bind,src=$snapshot_path,dst=/source,readonly" \
        --mount "type=bind,src=$registry,dst=/pins" \
        --entrypoint python "$image" -B /opt/people/create_people_posters/bulk_zfs_source.py register \
        --source /source --registry /pins --commit "$commit" --snapshot "$snapshot" --guid "$snapshot_guid" --host-path "$snapshot_path"
else
    zfs holds -H "$snapshot" | awk '$2=="kometa-people-bulk" {found=1} END {exit !found}'
    snapshot_guid=$(zfs get -Hp -o value guid "$snapshot")
    docker run --rm --network none --user "$container_user" --read-only \
        --tmpfs /tmp:rw,size=64m,mode=1777 \
        --mount "type=bind,src=$snapshot_path,dst=/source,readonly" \
        --mount "type=bind,src=$registry,dst=/pins,readonly" \
        --entrypoint python "$image" -B /opt/people/create_people_posters/bulk_zfs_source.py verify \
        --source /source --registry /pins --commit "$commit" --snapshot "$snapshot" --guid "$snapshot_guid" --host-path "$snapshot_path"
fi
