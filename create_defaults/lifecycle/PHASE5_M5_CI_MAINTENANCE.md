# Exact M5 / PR59 CI provenance transition

The user explicitly approved the original prerequisite and then the exact PR59
compatibility amendment. Integration baseline:
`3c15fb56b63bababa5d216b8d885e7dee257c11d`. Five existing successors are literal
before/after pairs in ci.phase5_m5_maintenance.APPROVED; two prior pre-PR59
in-memory views are literal RETAINED values for their respective exact paths.
The existing roadmap successor remains exactly the previously approved bytes.

There are exactly 27 allowed paths: 25 manifest members and two trust anchors.
New delivery hashes are sealed in phase5-m5-maintenance-v1.json with a pinned
canonical digest in its independent verifier. No directory/prefix allowance,
caller approval boolean or manifest reseal can expand membership. The verifier
checks baseline ancestry, every physical file, exact old bytes, absence of new
paths in the baseline and regular-file paths/modes. It rejects foreign checkouts.

Historical projection always checks the actual physical successor first. Only
the exact current/predecessor pair or explicitly retained per-path historical
input is accepted. In-memory historical views never authorize physical rollback.
The composed M5 -> PR59 -> M4 -> M3 -> M2 views preserve every original manifest,
pin, test identity and frozen inventory. Scope validation rejects unknown paths,
deletions, renames, links and incomplete raw Git diffs. Routing is usable only
with the complete sealed physical M5 cohort; partial delivery fails closed.

The two added shared retention CI paths serve this composition only. No People
runtime or fixture changes belong in the M5 diff. The existing shared-directory
test instruments real M5 checks separately while retaining its original exact
legacy scan assertions. All 10 M4 and 8 retention dependency IDs remain intact.

The 190 protected production, 299 adopted and 2927 frozen inventories are
unchanged, with zero M5 intersection. All nine inherited workflows remain
unchanged. M5 adds a pinned, read-only Windows/Linux workflow with unchanged
15-minute limits and resource budgets. Exact IDs, all execution phases, full
native files, catalog postimages, actual Git bundles/packs and false authority
flags are rechecked at acceptance. All ten workflows must pass at one final SHA.

No production/source ownership rule, operational approval, contract acceptance,
publication policy, workflow permission, READY/ACTIVE state, remote deletion or
merge permission is added. Further existing successor changes or path expansion
require another exact review. M6 and later milestones remain unauthorized.
