# Full English library synchronization engineering - 2026-10-18

The engineering and read-only/local execution are complete for this recorded
inventory. Artwork publication, new visual approvals, policy activation, merges
and production generator cutover were not performed.

Production `master` was refreshed before analysis and again afterwards. Both
observations identify `22c5ff5225fab7dce972f369bb16bf17a7abe8e0`, tree
`712d5eae6820c1bc9b18404d3222bd51bce59c14`. PR #198 is merged and its merge is in
production ancestry. Actual published bytes match all seven accepted canary
SHA-256 hashes. None of those exact matches enters the replacement plan.

| English class | Public destinations |
| --- | ---: |
| Exact binary match | 7 |
| Passes proposed renderer-equivalence screen; policy approval pending | 9,785 |
| Direct or inherited font changes requiring scoped review | 50 |
| Outside proposed tolerance; targeted visual/layout review | 113 |
| Total | 9,955 |

There are no English missing candidates, missing published destinations or
verification gaps. Both private intermediates are excluded. **9,948 English
SHA-256 mismatches remain**; none is treated as synchronized merely because its
appearance is similar. Zero English replacements are currently eligible under
new approval decisions, and zero images were published by this assignment.

The 113 exceptions reproduce exact prior candidate/published comparison bytes:
70 previously classified Python migration differences, 41 historical published
artwork differences, and two encoding differences. That history is diagnostic;
it transfers no visual approval. The complete exception gallery contains all
113 image pairs. Two sampled diagnoses explicitly identify caption displacement
and a one-line to two-line caption change; they are not an exhaustive semantic
layout-change count and do not approve either image.

The font matrix covers 17 active families and every public destination, with
license metadata and zero missing English caption characters. Three documented
substitutions affect 53 public destinations: 31 directly and 22 through generated
parents. Three are already exact canary matches, leaving 50 font-affected
replacements. Jakarta affects 22, Monoton 22, and Bebas Neue nine destinations.
Font selection approval is kept separate from resulting layout acceptance.

## Overlays

All 4,122 transformations map to unique proposed public destinations. Actual
inventory found 4,109 verified binary differences, 12 missing destinations, and
one blocked case mismatch: candidate `network/overlays/bigger/tokyo mx.png`
versus published `network/overlays/bigger/Tokyo MX.png`. That published uppercase
path is the only overlay path outside the exact proposed destination set.
It is not automatically deleted or renamed.

The 64 existing individually accepted overlay decisions retain exact image,
render, validation, source-context and prior published comparison identities.
Those 64 exact outputs enter the local publication manifest, although remote
publication remains unauthorized. Different worker receipt envelopes are
retained separately. The other 4,058 destinations remain withheld or blocked.

The separately proposed overlay screen passes 1,915 measured candidates, flags
2,183 other differences and 11 dimension changes, and grants no new approval.
It rejects 38 of the individually accepted examples, which remain exact reviewed
exceptions. Source inventory covers 1,784 RGBA, 238 LA and 39 palette images;
890 sources contain ICC profiles. The full corrected outputs still match their
verified Package E receipts, including the corrected LA/ICC processing.

## Calibration, transport and validation

The poster policy passes all four accepted unchanged-font positives. Three
additional accepted positives belong to direct/inherited font migration and are
excluded from that equivalence scope. All eight defective poster controls and
seven defective overlay controls are rejected. These are measured samples, not
a universal guarantee or an approved policy.

The actual 64 accepted overlays were rehearsed in four isolated local Git
batches. Recovery succeeded after a local commit without a journal update and
after a completed push without a journal update. An unchanged resume created no
extra commits. Exact paths and bytes were checked in each local remote commit;
incremental pack limits are enforced. The final local pack was 871,226 bytes for
505,044 replacement-artifact bytes plus the synthetic baseline and Git history.
There were zero network writes in this rehearsal. It is not a GitHub throughput
benchmark. The proposed starting limits are 300 files and 200 MiB of artifacts,
with a separate incremental pack cap. GitHub transport batches, visual approval
groups and publication PRs remain independent; five logical publication groups
are proposed, including one consolidated overlay group.

Local validation completed:

- 44 migration tests passed, including approval/context drift, inherited fonts,
  tagged colorspace review, exact bytes, baseline drift and Git recovery.
- 120 composer tests and 35 Package A tests passed.
- The broad bulk run had 453 passes, two OS symlink skips and one sandbox launch
  failure. The exact blocked PowerShell helper test subsequently passed with
  executable access; the original failure is retained in the execution index.
- 129 People compatibility tests passed; one OS symlink test was skipped.
- Historical/current baseline checks, compilation and `pip check` passed.
- Real smoke runs verified 35 posters and 38 overlays, followed by zero-render
  warm runs. All 35 newly generated posters exactly match frozen full-run hashes.
- Headless browser checks passed at 1,440 and 390 pixels: 918 main English
  previews, 226 English exception previews, 359 overlay previews and 58
  calibration previews, with no broken images or horizontal overflow.
- Normal source PR CI passed at `3c985b1`; the final evidence/source update runs
  normal CI again. PR #12 remains draft.

## Evidence and reproduction

[Usage and executable commands](../../../LIBRARY_SYNC_USAGE.md) describe
`library_sync`, `library_review`, `library_report`, `library_transport` and
`library_exercise`. Complete local reports, metrics, matrices, manifests,
comparison SQLite checkpoints and galleries are under
`config/library-sync-20261018/`. Full images and galleries are local artifacts;
they are not included in this source metadata package.

- `reconciliation-summary.json`: counts by category/font, approvals, gaps,
  publication groups, native runtime identities and transport evidence.
- `english-reconciliation.json.gz` / `overlays-reconciliation.json.gz`: every
  expected public path, exact candidate/published identities, disposition and
  bound review context. These contain metadata, not artwork.
- Proposed policy files and calibration records: immutable recorded proposals,
  numerical distributions, accepted-scope distinctions and defective controls.
- `deterministic-reproduction-probe.json`: all 35 direct rerender/hash matches.
- `sampled-layout-diagnosis.json`: exact hashes for two sampled layout findings.
- `execution-index.json`: compressed-file/payload identities and actual test
  outcomes, including the resolved sandbox failure.

Envelope `sha256` hashes canonical JSON excluding that field. Ledger index
`payload_sha256` hashes the entire decoded canonical envelope, including its
envelope hash; `file_sha256` hashes compressed bytes. Gzip timestamps are zero.
Generation, comparisons, final classification and historical diagnostic history
remain separate records; original Package E and canary evidence is unchanged.

Before any artwork staging: approve the exact calibrated policy scope, approve
font/layout groups and exceptions, decide the 12 missing overlay destinations
and Tokyo MX case mapping, and separately authorize the exact remote operation.
Merging and production PowerShell cutover require their own authorization.
Explained outstanding mismatches remain unsynchronized until the exact Python
bytes are published and remotely SHA-256-verified.
