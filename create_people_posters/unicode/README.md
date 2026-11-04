# Unicode / Inter successor — local review candidate

This profile is separate from the historical Jost/COLLECTION/bulk release.
It has **no CI authorization and no artwork publication authority**. Do not
deploy it over an existing renderer until the successor scope is reviewed.
The existing daily publication implementation is unchanged. There is no bulk
artwork publisher in this change.

## Fonts, identity and failure handling

Both the daily Python renderer and the five-style bulk worker call
`unicode_labels.resolve_label` through `Renderer.render_independent`.

| Style | Person-label font |
| --- | --- |
| BW, Rainier | Existing Comfortaa Medium |
| Signature | Existing Fuggles Regular |
| diiivoy, diiivoycolor | Official Inter 4.1 static Light, weight 300 |
| original, transparent | No person-label rendering |

The unmodified Inter archive member is `extras/ttf/Inter-Light.ttf`, from
<https://github.com/rsms/inter/releases/tag/v4.1>. Its SHA-256 is
`164414f0aacbe98a7e64addc43f7b3bfd2e32f7b90e101feeab227f14c371bda`.
The original SIL OFL notice is `../fonts/OFL-Inter.txt`. Historical Jost/font
documentation and prior release receipts remain evidence of their old profile;
Jost is not required by the new release image. COLLECTION still uses the same
Montserrat assets, tracking, stroke, size and coordinates.

Resolution tries the original display lettering, canonically equivalent NFC/NFD,
the approved punctuation rule, then a whole-label bundled Inter fallback.
Unsupported U+02BB becomes U+2019 **for display only**, and only when the primary
font lacks U+02BB and can render the replacement. Catherine's Signature uses
this rule; her Comfortaa and Inter labels keep the original character.
No accent stripping, transliteration, system font search or identity aliases
are applied. Existing style uppercase rules and filename display cleanup remain.
The original name, filename, TMDb identity and repository path are not normalized
or substituted by the resolver. Case/normalization collision protections remain.

The old NFC Latin layout stays in use for supported Comfortaa/Fuggles labels.
Inter and remaining combining/complex clusters use pinned uharfbuzz 0.56.3
shaping, with the same original outlines passed to Pillow through an in-memory
cmap bridge. The bridge replaces an existing `(3,10,0)` subtable instead of
creating a duplicate. No on-disk font is rewritten. Glyph zero remains an error.
No unsupported-glyph bypass is available in normal generation.

Unresolved names produce per-style `review-required` records and conspicuously
marked PNG previews under daily `logs/unicode-review` or bulk `.bulk/unicode-review`.
Those directories contain no production receipts and are outside style output
trees. Successful styles are saved independently. A partial daily run returns
failure and retains its inputs and successful outputs for retry; the existing
orchestrator publication gate still stops. This is not a new partial publisher.

Daily JSON and bulk output receipts record the resolved font, display text,
method, attempts, substitutions and policy digest. Resource fingerprints bind
the resolver, actual font/license bytes, layout code and shaping library version.
The new bulk runtime checks a separate version-3 inventory; old release manifests
and seals are untouched. A new renderer cannot resume or validate an old batch.
Use its original image to inspect the existing staged artwork.

## Local focused verification

Use the project's existing daily environment, with its requirements installed.
The focused test requires Pillow, fonttools, uharfbuzz, python-dotenv, requests,
alive-progress, numpy and pytest; no model download, TMDb key or GitHub token.

```powershell
python -m pytest create_people_posters/unicode/tests -q
python create_people_posters/unicode_runtime.py verify --manifest create_people_posters/unicode/runtime-release-v3.json
```

The tests render all four regression names across five styles, preserve original
identity and spelling, exercise NFD clusters, explicit fallback/review, retain
partial successes, compare daily/bulk JPEG bytes in one runtime, run two real
workers through interruption/resume and validation, and reject changed runtime
or tampered policy/receipts. The offline daily test supplies a representative
`people_list.txt`, invokes the real orchestrator's `poster_ps1` step and its real
renderer subprocess, and verifies all seven styles. Upstream acquisition is
pre-staged and every other external operation is blocked by the fixture.
It does not simulate a successful live GitHub publish.

The historical tests remain unchanged. Their Jost-only font inventory, explicit
Jost label tests and all-or-nothing failure expectations describe the predecessor
profile. They are not a valid claim of a green Inter CI run. New tests live
outside the frozen historical test namespace; registering the successor in CI
requires separate exact authorization.

```bash
# Repository root; build-time tests are bounded and offline after dependency install.
docker build --target unicode-test -t kometa-people-bulk-tests:unicode-inter-v1 \
  -f create_people_posters/bulk/Dockerfile .
docker build --target release -t kometa-people-bulk:unicode-inter-v1 \
  -f create_people_posters/bulk/Dockerfile .
docker image inspect --format '{{.Id}}' kometa-people-bulk:unicode-inter-v1
```

`unicode-test` runs only the successor tests during the build. The historical
`test` target and its test files are retained, but this checkout's runtime is
Inter: that target is expected to fail Jost-only assertions. Reproduce the old
green profile using the unchanged predecessor checkout/image; there is no
automatic profile switch. Do not describe historical tests as qualified against
Inter. The runtime base remains the digest-pinned
Python 3.13.15 slim Bookworm image in `../bulk/Dockerfile`. Docker dependencies
remain hash-locked; uharfbuzz is added with official PyPI release-file hashes.
The local daily environment may use newer Pillow/fonttools than this established
Docker profile. Fingerprints distinguish them. Byte parity is tested **within
the same pinned runtime**, not across arbitrary Pillow/FreeType builds.

Bounded local qualification on 2026-11-03 passed 23 successor tests on Windows
(Python 3.13.17, Pillow 13.0.0, fonttools 4.68.0) and 23 in the Linux Docker build
(Python 3.13.15, Pillow 12.0.0, fonttools 4.60.1); both used uharfbuzz 0.56.3.
The four real regression cutouts produced 20 decodable 2000 × 3000 JPEGs.
Sixteen predecessor pixel comparisons passed across BW, Rainier, Signature and
transparent controls, including decomposed Unicode. Text-only coverage of a
retained 15,434-name inventory passed 77,170 style checks: one Signature
punctuation substitution, zero fallback fonts, zero unresolved names. These
counts describe bounded rendering plus inventory text coverage, not a new full
regeneration or a new Gen10 benchmark. Reproduce with the tests and tools below.

`POSTER_ENGINE=powershell` now forwards to the same canonical Python renderer.
The orchestrator passes its exact interpreter with `-PythonExecutable`; direct
PowerShell calls can supply that parameter or `PEOPLE_POSTER_PYTHON`. Historical
ImageMagick code is retained below the early exit as predecessor evidence. It
is not executed. This is an explicit backend compatibility change: legacy
ImageMagick output is not claimed to be byte-identical to Pillow. Python remains
the default and requires neither PowerShell nor ImageMagick.

## Offline visual and inventory evidence

These optional developer tools read existing inputs; they never download or
publish images. Output must be a new directory disjoint from the inputs.

```bash
python create_people_posters/unicode/qualify.py coverage \
  --audit /review/source.audit.json --output /review/new-coverage
python create_people_posters/unicode/qualify.py gallery \
  --audit /review/source.audit.json --source /review/four-source-fixtures \
  --references /review/retained-diagnostic-gallery \
  --baseline /review/predecessor/create_people_posters \
  --output /review/new-gallery
```

The source fixture has the existing `initial/Images/name.png` layout. Gallery
hashes must match the retained source audit. References and predecessor are
optional. The retained reference gallery supplies `github-reference-manifest.json`
and its referenced JPEGs; no current remote state is assumed. Gallery files are
review-only, have no batch checkpoint or validated receipt, and cannot be resumed
or validated as a production batch. Coverage exercises text/glyph shaping for
every retained filename without re-reading PNGs; it is not an image integrity
audit or human visual approval.

## Daily operator procedure

1. Review this successor and its visual gallery before deploying it. Keep the
   original daily configuration, acquisition engines and publisher credentials.
   Install the updated daily requirements in the existing orchestrator venv;
   preserve the separate DDColor/BiRefNet/recovery environments.
2. Run the offline test and seal verification above. Confirm the Python renderer
   fingerprint names Inter Light, its exact hash, the Unicode policy and
   uharfbuzz. Keep `POSTER_ENGINE=python`; use all seven existing daily styles.
3. Continue the existing Logscan → `people_list.txt` invocation. Do not use a
   bulk source list in place of TMDb identities. To inspect an **already staged**
   daily batch, use the existing orchestrator's `--redo poster_ps1 --stop-after
   poster_ps1` with its existing workspace/batch arguments. This can rerender
   that batch and must not be pointed at the old 77,150-poster bulk staging tree.
4. Review `logs/create_people_poster.json`, `.orch/poster-render.json` and any
   `logs/unicode-review` records. A failed style retains successful files and
   inputs, returns a failure and stops normal publication. Diagnose/retry the
   same daily batch through the existing resume interface.
5. Run the existing daily validation/publication steps only under their existing
   authorization and destination-branch protections. No publication command was
   added here, and no live end-to-end publication has been performed for this
   candidate. Existing acquisition, DDColor, BiRefNet and publisher source files
   were not changed by this task.

## Bulk operator procedure

Use the new image for a **new** batch, never the existing Jost checkpoint. Start
with a bounded canary and review it. The existing portable `../bulk/README.md`
documents source synchronization and ordinary Linux bind mounts; ZFS is optional.
Use a persistent native filesystem for checkpoints, outside any Git repository.
Keep the verified source and pin read-only, and use an immutable image ID on
every start/resume/status/validation command. The operator selects the two styles
with `--styles diiivoy diiivoycolor --workers 2`; omitting `--canary` selects the
whole pinned inventory. For 15,434 images this plans 30,868 posters.

This task does not create server directories or launch that regeneration. The
private handoff contains the exact existing Unraid paths and mount commands.
Do not infer an Inter throughput estimate from the older Jost benchmark: shaping
changed, and this successor has only bounded qualification. Preserve snapshots,
pins, receipts and every existing completed batch. No cleanup is needed for this
font migration.

## Eventual bulk artwork release — proposal only

`bulk_reconcile.py` already provides read-only reconciliation and separately
authorized private payload staging. It checks source/destination history,
including changed-and-reverted files, newer daily updates, exact case/Unicode,
rewritten ancestry and unknown destination changes. It provides no commit/push
interface. Its historical tests/receipts remain scoped to their original release;
the Inter candidate is not an independently qualified bulk publishing solution.

A future release should reuse the daily publisher's authentication, destination
allowlist and compare-and-swap branch/ref safeguards, after separately reviewing
how it imports bulk provenance. Capture exact per-repository destination baselines,
reconcile source and destination history since those baselines and the pinned
source commit, and classify additions, replacements, unchanged files and conflicts
in a read-only dry run. Any independently added/updated poster requires explicit
conflict resolution, even if its change was reverted. Preserve filename bytes and
casing. Publish bounded commits with per-repository durable journals and payload
hashes; retry idempotently after verifying the expected remote head and committed
blob identities. A changed remote head requires fresh reconciliation, not a force
push. Qualify mid-upload/ref-update failures and recovery independently before
calling this production-ready. None of that publisher integration is implemented
or authorized by this Unicode/font task.
