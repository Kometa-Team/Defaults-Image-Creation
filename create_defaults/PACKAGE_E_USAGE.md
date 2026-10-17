# Package E acceptance commands

Run these from the repository root with a dedicated Python 3.13 environment and
`create_defaults/requirements-bulk.txt`. The commands create local evidence only;
they never approve artwork or publish. Use fresh explicitly named roots for new
measurements; retain previous observations and inspect failures before retrying.
Do not combine the independent People ML/browser requirements into this environment.
The People regressions used here cover shared GitHub/workspace/orchestrator behavior.

```powershell
py -3.13 -m venv config/package-e-env
$python = Join-Path (Get-Location) 'config/package-e-env/Scripts/python.exe'
& $python -m pip install -r create_defaults/requirements-bulk.txt
& $python -m create_defaults.bulk.e_validation baseline --root config/package-e/manual-baseline
& $python -m create_defaults.bulk.e_validation workload --root config/package-e/manual-small --category Based Decade --workers 2
```

Linux uses the environment's `bin/python` in place of the Windows executable.
Dependency versions, renderer source hashes, source head, final SHA/receipts and
resource observations are recorded. A cold label on a reused root does not prove a
fresh cache; check actual executed/cache-hit counts. Library upgrades require fresh
processes. Unowned/corrupt outputs are not adopted; do not delete receipts to force
reuse or replacement.

## Explicit full acceptance

These are expensive opt-in jobs, not ordinary PR CI. Review available memory/disk
before running them. Current bounds include four selected workers at 512 MiB each,
4 GiB sampled process-tree RSS, 8 GiB free disk, finite job caps, three hours per
English phase and 45 minutes per full-overlay phase. English final-output cap is
16 GiB; overlay cap is 2 GiB. Temporary artifacts also occupy disk, so free-disk
monitoring covers more than the final-output cap. A `STOP` file in the selected
root requests cancellation. Preserve receipts/completed outputs on interruption;
only token-owned workspace cleanup is supported. An incomplete run is not a pass.

```powershell
& $python -m create_defaults.bulk.e_validation workload --root config/package-e/manual-full-en --category all --workers 4 --full
& $python -m create_defaults.bulk.e_overlays --root config/package-e/manual-full-overlays --all --workers 4
```

The English helper runs cold and unchanged warm phases, verifies all 9,957 outputs,
private/public counts, validated manifests, claims, receipts, exact hashes, JPEG
headers and dimensions. Full decode is mandatory during new worker promotion.
The overlay helper verifies 4,122 PNG/RGBA transforms, alpha extrema, dimensions,
hashes and an unchanged zero-worker rerun. Neither helper grants visual acceptance.
Historical D decisions remain bound to their exact image/version context.

## Bounded performance observations

Use a quiet machine, sequential measurements and fresh roots for each worker count.
Selections are capped at 64 effective outputs including generated parents.
`small`, `medium`, `larger`, `dependencies` and `mixed` select four Based, 31 Decade,
32 Chart, six dependent Year children/parents and 16 mixed contracts respectively.

```powershell
& $python -m create_defaults.bulk.e_performance python --root config/package-e/bench-small-w1 --workload small --workers 1
& $python -m create_defaults.bulk.e_performance python --root config/package-e/bench-small-w2 --workload small --workers 2
& $python -m create_defaults.bulk.e_performance python --root config/package-e/bench-small-w4 --workload small --workers 4
& $python -m create_defaults.bulk.e_overlays --root config/package-e/bench-overlay-w2 --workers 2
```

The legacy harness requires existing PowerShell 7/ImageMagick and a completed matched
Python workload. It copies inputs and bundled fonts, redirects output privately and
removes bootstrap/update/install code while preserving composition. Source hashes
are checked before/after. It refuses an existing legacy workspace and more than
64 outputs. Poster processes are sequential, with bounded per-command/total duration;
overlays reproduce grouped mogrify operations. This is not the entire production
launcher's concurrency/bootstrap performance.

```powershell
& $python -m create_defaults.bulk.e_performance legacy --root config/package-e/legacy-small --python-root config/package-e/bench-small-w2 --powershell 'C:/path/to/pwsh.exe' --magick 'C:/path/to/magick.exe'
& $python -m create_defaults.bulk.e_performance legacy-overlays --root config/package-e/legacy-overlays --python-root config/package-e/bench-overlay-w2 --magick 'C:/path/to/magick.exe'
```

The ordinary module entry points support `--help`. Keep fresh measurements separate
from retained historical ledgers. A warm-only profile can inspect verified Year work:

```powershell
& $python -m create_defaults.bulk.e_validation workload --root config/package-e/manual-year --category Year --workers 2 --profile
& $python -m create_defaults.bulk.e_validation workload --root config/package-e/manual-year --category Year --workers 2 --warm-only --profile --record-prefix followup
```

## Explicit read-only network evidence

`gh` must already have suitable read access. The helper obtains the token privately;
do not echo it or put it in commands/logs. Requests are GET-only to the selected
GitHub repository, rate/time bounded, redirect-restricted and blob verified. Source
refresh is explicit; it cannot alter a running generation implicitly.

```powershell
& $python -m create_defaults.bulk.e_network translations --root config/package-e/manual-languages
& $python -m create_defaults.bulk.e_network audit --root config/package-e/manual-languages
& $python -m create_defaults.bulk.e_languages coverage --root config/package-e/manual-languages --baseline config/package-e/manual-baseline
& $python -m create_defaults.bulk.e_network published --root config/package-e/manual-published --baseline config/package-e/manual-baseline --generated config/package-e/manual-full-en --samples 24
```

`e_languages proposals` also requires the exact previously evaluated Arabic
candidate/font-license cache from Package D, verified pinned translation resources
and a fresh proposal root. It is a controlled maintainer evaluation helper, not an
automatic font installer. Candidate provenance and pending decisions are in the
report. Preview creation never activates a fitting definition or approves images.

Full comparison against previous Phase 1 evidence requires its retained accepted
`config/phase1-validation-20261016/full-batch-monoton-ofl` run, rather than fabricated
reference outputs. The index command records exact reference identities. Comparison
fails on unexplained differences and calls the approved API for changed real-parent
inputs. For an isolated dependency compatibility comparison, use the retained
original renderer environment for that reference call and the patched environment
for production-path generation; report both exact versions.

```powershell
& $python -m create_defaults.bulk.e_comparison index --root config/package-e/manual-reference
& $python -m create_defaults.bulk.e_comparison compare --root config/package-e/manual-reference --generated config/package-e/manual-full-en
```

See [Package E report](PACKAGE_E_REPORT.md) for actual results, immutable evidence
links, platform skips and readiness limitations. PR CI runs the smaller offline
`e_smoke` only. Full catalogs, databases, temporary workspaces and font/image payloads
stay under ignored roots. A successful command is neither maintainer visual
acceptance nor authorization to publish, merge, deploy or cut over.

## Multilingual fitting correction

The multilingual addendum supersedes the English-matching rule from the original
D/E audits. Those completed files remain historical evidence. The correction
measures each actual translated caption with the approved bundled font and native
compositor logic. Different lengths, widths and line counts do not fail validation.
Normal two- or three-line wrapping is informational; four or more lines and margins
under 20 pixels remain measurable review warnings. Glyph, Unicode, directional,
caption-box and poster-image bounds remain enforced.

A fitting current layout is technically eligible. A smaller-font proposal remains
`needs_layout_review` and is excluded from rendering under partial policy; strict
policy refuses the whole batch. The proposal records exact caption, font, renderer,
position, parameters, measurements and validation version. It never replaces current
parameters or edits a definition. The existing explicit proposal/preview and review
workflow remains available for a maintainer to inspect a candidate before a separate,
reviewed definition change. Creating technical evidence grants no artwork approval.

Use the exact retained original audit and a fresh destination for a controlled
before/after comparison. This command stages verified pinned translation blobs
locally and performs no network refresh or upstream writes:

```powershell
& $python -m create_defaults.bulk.e_multilingual --root config/package-e/manual-corrected-languages --previous config/package-e/manual-languages
```

The command audits only caption keys and resolved dependencies used by active,
applicable posters. It reports unique valid, missing and invalid keys separately
from affected logical posters and language variants, retaining exact source and
English-reference identities. Identical English values are informational; numeric
labels, acronym candidates and identifiable proper-name keys are tagged separately.
It does not infer proper nouns from capitalization or flag equal character counts.

The report separates key completeness, technical typography and human artwork
review. Diagnostic counts overlap: for example, current clipping and a fitting
proposal can describe the same variant. The cache reuses exact text/font/size/offset,
renderer and validation-policy inputs. The compositor chooses shaping from the
actual Unicode text; language does not alter that computation, so identical native
inputs can safely share measurement evidence while variant validations remain
language-bound.

English and overlay review policies retain their original identities. Only
translated-caption policy revisions invalidate the affected review context;
old reports keep the policy they actually recorded. Caption, font, layout, renderer
and output changes still require precise revalidation. Immutable decisions remain
in the existing review event history.

A future risk-based workflow can group exact language/font/layout/template
combinations, inspect representatives and record the exact inspected subset.
Current translated-caption policy still requires individual artwork review.
Any future group acceptance needs an explicit maintainer decision bound to all
enumerated members and exact image/version identities. High-risk typography
changes, unsupported scripts, clipping and stale decisions require individual
review. Representatives never automatically approve uninspected members.

## Recorded maintainer decisions

The 2026-10-17 acceptance record covers exactly 64 presented overlay previews and
six presented FR/DE/BG image/layout previews. It does not activate catalog layout
changes or approve other variants. Language previews keep their original validation
context; revalidate before any activation and do not transfer approval automatically.

The canonical public English destination is **`genre/Action & Adventure.jpg`**.
The catalog explicitly maps its captured internal `Action & adventure.jpg` output
to this exact public path. Future operations must use the manifest's
`remote_relative`, never derive a public filename from the local output basename
or apply case-insensitive matching. Run fresh strict preflight for a future rollout.
No production cutover or publication is authorized by these sample decisions.
