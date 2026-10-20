# Python operator workflow candidate

This workflow is implemented in draft source PR #12. Activation as the supported
production entry point requires the separate cutover decision. The legacy
PowerShell entry points and the root README remain unchanged until that decision.

Use Python 3.13 and `python -m pip install -r create_defaults/requirements-bulk.txt`.
Rendering uses the existing Pillow composer, planner, validation and persistent
workers. It does not launch PowerShell or ImageMagick. Git and the authenticated
GitHub CLI are needed only for explicit production reads/staging/PR operations.
No application installation or hosted service is required.

## Generation and incremental reuse

Run from the repository root. Global directory arguments go before the action.
Keep cache, temporary work and output in separate directories outside source
artwork. The defaults are under `config/bulk/`.

```powershell
# Discover exact IDs, including the existing Playlist definitions.
python -m create_defaults.bulk list-categories
python -m create_defaults.bulk validate-definitions --definitions create_defaults/bulk/catalog/playlist.yml --profiles create_defaults/bulk/catalog/profiles.yml

# One existing poster; additional --poster arguments select a small batch.
python -m create_defaults.bulk.operations generate --poster playlist.playlist-arrowverse-timeline-order.09b7e4b8 --report config/playlist-generation.json

# Selected authored YAML definitions, including a single new poster definition.
# Use the existing definition-v1 schema and profiles; supply actual names/assets.
python -m create_defaults.bulk.operations generate --definitions path/to/definitions.yml --profiles create_defaults/bulk/catalog/profiles.yml --report config/selected-generation.json

# A category; repeat --category for several. All selects the full English catalog.
python -m create_defaults.bulk.operations generate --category Based --report config/category-generation.json

# Current overlay catalog, one group, or an exact source.
python -m create_defaults.bulk.operations overlays --group aspect --report config/overlay-generation.json
python -m create_defaults.bulk.operations overlays --source logos_aspect/1.33.png --report config/overlay-selected.json
python -m create_defaults.bulk.operations overlays --definitions path/to/new-overlays.yml --report config/new-overlays.json

# Layout/font/asset audit without poster rendering.
python -m create_defaults.bulk preflight --category All --language en --policy audit --report config/english-preflight.json
```

An authored new-overlay file has `schema_version: 1` and an `overlays` list.
Each item explicitly supplies `source` (relative to the asset root), `destination`
(a public `category/overlays/size/name.png` path), `box` (`[285,85]` or `[440,100]`)
and boolean `trim`. The same existing Pillow overlay transform and workers render
these definitions. The destination basename must exactly match the source basename,
including capitalization. Rendering does not approve its public mapping.

The first run validates dependencies and renders only uncached identities. An
unchanged repeat verifies artifacts/receipts and renders zero outputs. Changed
parents are rendered before dependents; their actual hashes bind child plans.
Corrupt artifacts/receipts fail closed. A native encoding/font dependency change
refuses reuse of the operator cache: select new cache/work/output roots and review
the resulting changes. Do not edit SQLite or old receipts to bypass this guard.

English and overlays can be selected independently. `generate --category All`
selects posters; `overlays` selects overlays. The two use distinct manifests.

To adopt this workspace's validated migration cache without regenerating artwork:

```powershell
python -m create_defaults.bulk.operations --cache-dir config/package-e/full-en-final/cache --workspace-dir config/package-e/full-en-final/work --output-dir config/package-e/full-en-final/output adopt --kind english --inventory config/library-sync-20261018/english-reconciled-inventory.json --save-profile config/english-operator-profile.json
python -m create_defaults.bulk.operations --profile config/english-operator-profile.json generate --category All --cache-only --report config/english-unchanged.json
```

Adoption checks the complete validated ledger, native runtime, source inputs,
artifacts, original receipts and finalized worker state. It changes no artwork.
Use the analogous overlay cache/output roots and the refreshed canonical overlay
inventory with `adopt --kind overlays` to adopt overlay artifacts. A cache-only
poster run refuses to start rendering on a cache miss. Overlay cache-only runs
verify all selected existing receipts before invoking the shared generation path.
New work uses ordinary generation after preflight and its own explicit review.

## Preview and exact approval

```powershell
python -m create_defaults.bulk.operations preview --generation config/category-generation.json --root config/category-review
```

This GET-only action pins actual production master, checks current generation
inputs/runtime, downloads the compared bytes and writes `inventory.json` plus
`review/review.html`. Exact SHA-256 matches are skipped. Binary-different files
remain replacement candidates even when their pixels look identical. Missing
destinations require explicit addition decisions. Overlay case-only basename
corrections require exact rename decisions; other case conflicts remain blocked.

Supply a versioned policy file describing the exact review scope and limits:

```powershell
python -m create_defaults.bulk.operator_publication prepare --inventory config/category-review/inventory.json --policy path/to/review-policy.json --root config/category-staging
```

Review `candidate-manifest.json`, `proposed-policy.json`, the gallery and withheld
membership. No policy or proposal is approved automatically. Canonical payload
SHA-256 values are printed/stored; they differ from serialized file hashes.
The maintainer must supply the actual decision, both exact hashes and explicit
individual-exception acceptance where needed. For each genuinely new public
destination add one exact `--allow-addition` argument. A mapping conflict cannot be
approved by relabeling it as an addition.
For a proposed overlay case-only rename, add
`--allow-rename "exact/old.png=>exact/Old.png"`. Every pair must match the
manifest's `rename_from` and destination exactly. The destination basename must
match its authoritative source. The transport removes the old Git path and adds
the canonical path in the same commit; it checks the complete resulting tree.
Arbitrary destination overrides are not supported.

```powershell
python -m create_defaults.bulk.operator_publication approve --root config/category-staging --reviewer bullmoose20 --policy-sha256 APPROVED_POLICY_HASH --manifest-sha256 APPROVED_MEMBERSHIP_HASH --decision-text-file path/to/actual-maintainer-decision.txt --accept-exceptions
```

The `approve` command records a decision the maintainer actually supplied. Agents
and unattended generation must not invent a decision or run it to grant themselves
permission. It writes sealed approval/authorization files without uploading.
Source definitions, source files and catalog snapshots must agree before approval.
Use `python -m create_defaults.bulk.case_audit --help` for the native case audit.
On Windows, a successful file lookup is insufficient: the audit checks directory
entries and Git index spelling. Correct source case through a verified two-step
`git mv`; preserve source bytes and update stale catalog references, not the
authoritative definition. Both overlay sizes retain that exact source basename.

## Draft staging, verification and recovery

```powershell
python -m create_defaults.bulk.operator_publication stage --root config/category-staging
python -m create_defaults.bulk.operator_publication verify --root config/category-staging
python -m create_defaults.bulk.operator_publication draft --root config/category-staging --title "Stage approved Python artwork"
```

`stage` uses the existing bounded Git transport, checks master before writes and
each push, and downloads every staged image for SHA-256 verification. It checks
the complete Git tree, including untouched paths. Only exact approved ordinary
modifications, additions and case-only overlay renames are permitted. There are no
implicit renames/deletions, force pushes, master writes or merges.

After interruption, run the identical `stage` command with the retained root,
journal, receipts and authorization. Known commit prefixes resume; ambiguous
pushes are reconciled. Unexpected history, changed source/bytes or a changed
baseline stops writes. Refresh the proposal while preserving unchanged material
review decisions if master changes. Keep old evidence roots immutable.

Run `draft` only after complete staging verification. It creates/reconciles one
draft PR, fetches the actual PR ref and checks its complete raw Git diff. Technical
batches do not determine review groups or PR grouping. A second no-op publication
does not create an empty PR. Merge authorization is a separate decision.

## Full production reconciliation

```powershell
python -m create_defaults.bulk.operations verify-production --inventory config/library-sync-20261018/english-reconciled-inventory.json --root config/english-production-verification
python -m create_defaults.bulk.operations verify-production --kind overlays --inventory path/to/final-approved-overlay-inventory.json --root config/overlay-production-verification
```

These are read-only checks of the complete validated output ledger and local
candidate identities against a fresh production tree and actual pinned response
bodies. They do not regenerate/reupload artwork. New runs after changed production
state should use a new evidence root. Historical migration inventories are not
general-purpose inventories for newly added definitions; preview a new generation
report for those operations.

## Activation and rollback

Proposed entry point replacements:

| Legacy operation | Python replacement |
| --- | --- |
| `create_default_posters.ps1 All` | `bulk.operations generate --category All` plus explicit `overlays` |
| Category arguments to the bulk PS script | Repeat `--category` or exact `--poster` selection |
| `create_poster.ps1` one-off composition | Authored definition through `bulk.operations generate`; direct `create_poster.py` remains a low-level local composer |
| PS overlay ImageMagick loops | `bulk.operations overlays` |
| Manual artwork copy/push | Preview, exact approval, `operator_publication stage`, `verify`, `draft` |

Repository audit found one validation workflow and no scheduled generation job.
CI validates Python; it does not publish production artwork. External schedulers
cannot be inferred from repository contents and must use the approved commands
when their operators switch them.

The cutover approval covers promoting these commands in the root README and
marking the two PS rendering scripts legacy in operator documentation. It does
not authorize merging PR #12, deleting scripts, publishing unapproved mappings,
or merging artwork PRs. Keep old scripts for rollback. To roll back operational
entry points, restore the prior documented command selection from the source
baseline; do not automatically render/publish legacy bytes over migrated artwork.
Any production-artwork rollback needs its own exact reviewed diff and approval.
Development-only PS capture/legacy comparison helpers can remain for historical
reproduction and be removed separately after retention/rollback decisions.
