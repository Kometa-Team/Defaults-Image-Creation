# PR #23 dependency provenance maintenance

## Verified cause and intent

Merged main `d6b039788315f2198304cf05f7efea5addc271c9` contains Dependabot commit
`06e3bc5959600d1bf5c5cec86f49b9ef5f5b198c` from PR #23. GitHub records the merge
by `bullmoose20`; there were no submitted PR reviews. The dependency PR's old
Windows/Linux checks failed, so merge intent is not represented as compatibility
proof. This maintenance PR supplies independent current-head validation.

The entire dependency commit changes four requirement files, five version lines:
Pillow 12.3.0 to 13.0.0 (exact pins and the existing DDColor minimum) and certifi
2026.7.22 to 2026.10.19. Every predecessor hash matches the approved 190-file
manifest. The Defaults requirement also matches the frozen 299-file adoption
snapshot. All four successors match both the dependency commit and merged main.
The other 186 protected files and 298 adoption files already match their pins.
No dependency or runtime file is changed by this maintenance PR.

Official PyPI release metadata, CPython 3.13 Windows/Linux wheel hashes and the
certifi wheel hashes are retained in `dependency-maintenance-v1.json`.
[Pillow release notes](https://pillow.readthedocs.io/en/stable/releasenotes/13.0.0.html)
raise the Python minimum from 3.10 to 3.11; repository CI uses 3.13. No repository
reference to the removed `_save_netpbm` or `ExifTags.IFD.Makernote` APIs was found.
The isolated Windows test environment installs Pillow 13.0.0 and certifi
2026.10.19, passes `pip check`, and loads 120 trust roots through Python SSL.
This validates the existing version update for the tested environment; it does
not claim all future rendering bytes equal historical Pillow 12.3 outputs.
Model inference is outside this repair's scope.

## Exact dependency transitions

SHA-256 values normalize CRLF to LF, matching the existing source verifiers.

| File | Prior approved SHA-256 | Merged PR #23 SHA-256 |
| --- | --- | --- |
| `create_defaults/canary/requirements-staging.txt` | `cf3f3461847241b012c0d5033035a12e6604f5917464fe18ea4a0a8dad2463db` | `f3e9cf9a0846f0e08498c654249bd9a3269829abb1510fc03e26c4e550c9b829` |
| `create_defaults/requirements.txt` | `867680e4833b29336eceb8f51c7f61cb4d067a26da4d4a09558a17dd8a01617d` | `fbf51f216bac9931370235520b8ad8207a6c2d82dd26d75bd5b7629c9801be42` |
| `create_people_posters/requirements-ddcolor.txt` | `6ea6faae8abe36ffce10ba1688b12f45176e4599f9a3aefc401a0d77dd2deebf` | `4bbfd33fd44706754d387e08861dc51268d670540627635b00e45f22170692fa` |
| `create_people_posters/requirements-rembg.txt` | `08b9485c9d2a64f556db53f5e8d75d49ada5fa33ea7a0e7753ef8c0f509ae104` | `e83d325e4bca2ae2c9aff93f3bea70c73e87769e76d295c4c3612ce5188f7a1e` |

## Preserve historical evidence; select exact current source pins

`ci/dependency-maintenance-v1.json` is a separate immutable, canonical-hash-pinned
transition. It names the dependency commit, merge baseline, author, prior
production manifest and adoption snapshot, and exact before/after source hashes.
Its canonical SHA-256 is `8deb50e4f2b2e18b9688fd3bbcc427e2d67cdf6051f6794f206f07acb69dd590`.

The original 190-file production manifest, 299-file adoption snapshot, historical
registries, source commit/tree identities, output hashes, receipt mappings and
approval records remain byte-for-byte unchanged. This transition grants no
contract, visual, activation or publication approval. It neither rerenders nor
relabels historical artwork as generated with newer dependencies.

The three existing verification paths select the successor hash only for an
exact listed path **and** exact predecessor. Every source is still read and
SHA-256 checked with the original LF normalization. Unknown paths and different
predecessors keep their original pin and receive no allowance. Changed, missing
or malformed transition data fails closed. Content-based caching never trusts
mtime or caller compatibility flags. Pin-envelope checks, 190-file membership,
AST activation checks, confinement and historical checks remain in place.

The source-selection changes to `activation/protection.py`, `adoption/sources.py`
and the necessary `ci/phase4.py` scope extension are also bound to exact
before/after infrastructure hashes in this transition. Every infrastructure
check validates both the predecessor Git bytes and the current bytes. Its returned verified file map includes the reader with a separately named
dependency-extension baseline and transition hash, preserving the caller
contract without relabeling the frozen M1 manifest. The
Phase 3 assertion is unchanged: its accepted maintenance scope gains only the
exact verified adoption reader; the original M1 manifest membership is unchanged. The existing People
maintenance verifier checks those exact bytes, retains its immutable earlier
manifest and exposes the separately verified current hash to older CI consumers.
Its historical view and all prior transition checks remain intact. The M5
disposable-copy fixture includes these exact dependencies and the one additional
Git baseline; its original negative tests and assertions are unchanged. No blanket
exception, resealing command or runtime flag is introduced.

## Frozen dependency fixtures and measured calibration compatibility

The first complete CI run revealed two further inherited dependency assumptions.
The frozen canary deployment expected the old staging requirements but read the
updated file. Its test now first verifies the exact merged successor and then
reads and verifies the exact predecessor from Git for the historical fixture.
All original frozen-manifest, helper, disabled-staging and deployment assertions
remain. The helper/runtime, deployment manifest and historical evidence are not
modified. Unknown or changed current dependencies cannot use the historical view.

The logo-corpus check compares a sealed Pillow 12.3 evaluation to the current
runtime. A full recursive comparison of all 60 synthetic evaluations found only
120 differences: 60 explicit Pillow version strings and 60 corresponding policy
fingerprints (which include that version). Every pixel/hash fixture, geometry,
topology, numerical measurement, outcome and summary is unchanged. There are no
new tolerances. The transition records both complete canonical report hashes:
`33b0ef0e6f9f65f28bb3c32e0fbaf987926688c26a4ded8e60d01e0a90082706`
(historical) and
`6e25ad818dc2bc12dffe31710434702542955b285cb5c70e3f3421217751a793`
(current dependency expectation). The test compares the complete current report
to that separate pinned expectation. No field is ignored. The old corpus and
calibration file remain unchanged. Automatic MATCH and policy approval remain
false. Current and historical policy fingerprints are distinct and are never
treated as interchangeable approvals.

These two test adjustments and the M5 fixture are also independently bound to
exact infrastructure hashes. Original test IDs, assertions and negative controls
remain; the corpus assertion now uses the measured dependency-specific expected
report rather than claiming its metadata equals the old runtime's report.

## Exact changed-file inventory

Modified:
- `ci/phase4.py`: independently verify exact dependency infrastructure before
  exposing the one additional adoption-reader path to the unchanged scope guard.
- `ci/people_security_maintenance.py`: apply exact transition pins; preserve the
  prior manifest, source-loop checks, AST checks and historical views.
- `create_defaults/bulk/contracts/activation/protection.py`: select the exact
  successor before the existing SHA-256 equality check.
- `create_defaults/bulk/contracts/adoption/sources.py`: same selection for the
  one approved dependency delta; preserve the frozen snapshot and history.

- `create_defaults/phase4/tests/test_ci_transactions.py`: fixture-only additions
  for the exact infrastructure dependencies and historical Git baseline.
- `create_defaults/bulk/tests/test_canary_staging.py`: verify current dependencies
  before reconstructing the exact frozen deployment requirements; preserve checks.
- `create_defaults/bulk/tests/test_logo_workflow.py`: compare the entire report
  against the separate dependency-specific expectation; preserve other assertions.

Added:
- `ci/dependency-maintenance-v1.json`: dependency/provenance and upstream evidence.
- `ci/dependency_maintenance.py`: stdlib-only, pinned exact transition selection.
- `ci/dependency_tests/test_dependency_maintenance.py`: independent positive and
  adversarial tests without changing any original test ID or assertion.
- `.github/workflows/dependency-provenance-validation.yml`: independent Windows
  and Linux tests at the exact PR head, with 15-minute limits and no tolerated
  failures. The protected original workflow is unchanged.
- `ci/DEPENDENCY_PROVENANCE_PR23.md`: this evidence and scope record.

## Validation and boundaries

Local validation: eleven maintenance tests, focused inherited-boundary/CI/security
regressions, `pip check`, and the original historical baseline check. Final local
counts and exact-head Windows/Linux job evidence are recorded in the draft PR
body so documentation does not require an endless change of the tested head.

The unchanged original workflow must pass all bounded Windows/Linux groups and
mandatory **Validation acceptance**. The additional dependency-provenance jobs
must also pass. Original test-ID reconciliation, all negative assertions, the
512 MiB worker-parent safeguard, 15-minute job caps, 14,079 historical outputs and
14,077 public receipt mappings remain required. The new checks do not substitute
for those original checks. Requiring the additional check in branch protection
is a maintainer repository-settings decision; no settings are changed here.

PR #39, its branch and its artifacts are untouched. No M7, remote operations,
activation, artwork changes, publication or merge is authorized by this work.
