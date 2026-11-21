# Catalog-owned Playlist reservations

This integration is implemented for review and exercised only in staging.
It has not been deployed, and no production UUIDs or catalog records have been
created. Historical lifecycle schemas, receipts, pins and workflows are retained.
The draft includes the empty production-owned ledger and an exact additive CI
receipt; its Windows/Linux validation workflow has read-only permissions.

The existing owner is the Git-backed catalog in
`Kometa-Team/Defaults-Image-Creation`, branch `main`, under
`create_defaults/bulk/catalog/`. Its current index owns historical output IDs.
The contract registry selects contracts rather than owning new poster IDs;
the M2 identity store and browser catalog remain isolated planning/staging.

The proposed durable reservation ledger is
`create_defaults/bulk/catalog/reservations-v1.json`, under the same repository
ownership and maintainer review as `playlist.yml` and `index-v1.json`. It is
separate from the immutable synthetic M1/M2 records. No additional database,
hosted service, UUID generator or mutable approval system is introduced.

## Implemented boundary

`CatalogReservations.reserve` delegates to the unchanged
`IdentityRegistry.allocate` algorithm through a private storage bridge. The
existing UUID creation, historical semantic bridge, entry schema and complete
namespace collision checks remain in use. This is a new Git persistence layer,
not a change to the synthetic allocator's schemas or its authority flags.

The reservation request binds its idempotency token to names, semantic key,
definition template, exact logo hash and approved JPEG hash. Exact retries
return the stored UUID even after reopening the checkout or merging a catalog
PR. Changed token payloads, semantic collisions, case-folded output collisions,
source-path reuse and stale heads are rejected. All public paths are compared
with a complete Git tree at an independently selected destination commit.

One private-index Git commit contains the new reservation, its catalog
definition, index lookup and source PNG. `git update-ref <ref> <new> <expected>`
is the local CAS: two concurrent writers cannot both win at the same head.
Failed CAS attempts leave no referenced reservation or partial catalog state.
The concurrent-writer regression retries the loser against the fresh revision,
then reopens the store: both reservations remain and retrying the second token
returns its original UUID without another commit. CAS protects the shared Git
ref; separate clones must publish through a non-force, current-base catalog PR.
Existing profiles, definitions and index records are checked on reload.

`prepare_publication` passes the assigned identities and exact approved JPEGs
to the existing `operator_publication.prepare` path. It creates no approval or
write authorization. `stage_publication` refuses staging owners and adds fresh
registry/mapping/JPEG checks before each original transport mutation. A
production owner must point at the real catalog repository and branch; its
reservation commit must already be published on catalog `main` before artwork
publication can be prepared. The original operator decision, addition allowlist,
destination snapshot, pack, hash and complete-diff checks remain required.

There is no automatic remote push, production bootstrap or merge command.
The public staging initializer explicitly rejects production owners.

## Proposed live rollout, requiring review first

1. Review this implementation, staging results, empty ledger and proposed owner.
   `ci/catalog-reservations-maintenance-v1.json` registers only the exact new
   implementation, test, documentation, evidence, workflow and empty-ledger
   hashes. The prior Phase 6 receipt and all its member hashes remain unchanged.
   The later data change needs a separate narrow admission for ledger updates,
   the two catalog postimages and the eight exact source-PNG additions. Retain
   historical receipts and source-pin inventories; register exact successors
   rather than editing old evidence or granting a directory-wide exception.
   Data successor hashes cannot be finalized until the separately authorized
   production UUID allocation has produced those exact postimages.
2. Refresh catalog `main` and Default-Images `master`, and require the eight
   approved destinations still to be absent. Merge the separately reviewed
   implementation/empty-ledger PR before allocating production identities.
   The empty ledger pins its initialization parent and destination snapshot;
   a staging ledger must never be relabelled as production. Destination drift
   requires a reviewed successor before allocations, not a silent rebase.
3. Only after the rollout is authorized, call the existing allocator through
   this adapter against that owner using the eight approved tokens and mappings.
   These will be production allocations; the staging UUIDs are test evidence
   and will not be copied or forced into the production allocator.
4. Rebind the eight definition IDs, index keys and background-assignment IDs to
   the returned UUIDs. Review the atomic reservation/catalog/source-PNG commits
   and merge the catalog PR under an exact current-base check. A competing
   catalog update requires revalidation; no force push or lost-update merge is
   permitted. A local candidate commit is not a live reservation until it is
   accepted by the owner on `main`.
5. Open the production owner at that published head, prepare the exact eight
   JPEG additions with `prepare_publication`, and bind the separate operational
   decision to that registry commit, policy and candidate manifest. Use the
   original operator transport with its eight explicit allowed additions and
   the registry write guard. Verify actual branch JPEG hashes and the full
   eight-`A` diff, then open a draft PR against current Default-Images `master`.
   Leave that PR unmerged. A source/destination head drift stops the rollout
   for refreshed validation; it does not silently allocate replacement IDs.

Current scope is eight English, single-logo Playlist additions. It does not
implement other categories, updates, removals, restoration, activation or
automatic publication. It does not infer real authority from fixture approvals.
