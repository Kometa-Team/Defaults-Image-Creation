# Package D: Local Preflight and Human Review

This is development tooling, not a production replacement or publication service.
Use `py -3.13` on Windows. Linux CI uses its pinned Python 3.13 interpreter.
All commands below run from the repository root. Source artwork and the approved
composer remain unchanged. Generated images, SQLite state and detailed reports
belong under ignored `config/`, never in the source catalog or Default-Images.

## One Engine

`bulk.preflight.preflight` resolves the selected logical graph, pins translations,
checks applicability, glyphs, native compositor metrics, paths, dependencies and
D01 colors. `bulk.generation.generate` always calls it before opening the shared
persistent spawn pool. `bulk.services.preview` uses that same entry point and
pool, not a second composer. `bulk.delta.regenerate` supplies exact variant IDs
to that engine. `bulk.overlays.generate` validates and persists its structured
transform plan before using the same worker lifecycle and review store.

For a single checked-in ID, `load_catalog(posters=[id])` reads the metadata index
and only its category YAML plus required parent definitions. It does not expand
all 9,957 contracts or hash unrelated artwork. `catalog_index.py` is an explicit
development export and must be rerun when catalog identities/dependencies change.

## Translation Sources

```powershell
py -3.13 -m create_defaults.bulk refresh-translations
py -3.13 -m create_defaults.bulk list-languages --snapshot SNAPSHOT.json
py -3.13 -m create_defaults.bulk --offline preflight --poster based.based-book.217e49bd --language all --snapshot SNAPSHOT.json
```

Refresh is explicit and GET-only. `Kometa-Team/Translations/master` is pinned to
an immutable commit/tree; only immediate `defaults/*.yml` resources are discovered.
Git blob SHA, byte size, SHA-256 and safe YAML/key parsing are verified. Blob
cache entries and registry snapshots are content-addressed and verified offline.
Loaded translations stay in memory for a run; refreshing files cannot change an
already loaded run. A new resource code needs no Python allowlist update.

Historical `nb_NO` and `pt-br` retain exact case/punctuation. Aliases require an
explicit registry mapping and are deduplicated, not additional destinations.
Unknown, unavailable and non-poster components remain distinguishable. Display
names are null where no authoritative mapping was verified, not guessed.

The public Weblate landing page requires sign-in. Reports link to the verified
landing page and explicitly mark direct-key navigation unavailable. They do not
invent project/component/editor URLs or write upstream changes.

## Audits, Proposals and Previews

```powershell
py -3.13 -m create_defaults.bulk preflight --category Based --language fr --policy strict
py -3.13 -m create_defaults.bulk generate --category Based --language en --policy audit
py -3.13 -m create_defaults.bulk preview --poster based.based-book.217e49bd --language en --representatives 1
py -3.13 -m create_defaults.bulk propose-layout --poster based.based-book.217e49bd --language fr
```

Use `--translation-dir`, before the command, for explicit local YAML snapshots.
The default directory contains only the frozen English compatibility fixture.
Use `--snapshot` for a refreshed registry. Language defaults are English for
`generate`, all discovered applicable codes for `preflight` and `preview`.

Preflight writes JSON, contributor CSV and human-readable HTML beneath
`cache/preflight/<hash>/` even when required variants are blocked. Reports separate
missing/invalid keys, unavailable resources, font/glyph failures, RTL, stale
fitting, dependencies, non-applicability and shared artwork. Deduplicated key
rows retain affected logical and variant IDs/counts, English source, resource,
pinned snapshot, fallback provenance and contribution-link limitations.

`partial` renders eligible variants and reports incompleteness. `strict` renders
nothing if any required selected variant is blocked. `audit` never renders.
Review previews require explicit variant IDs, `--high-risk`, and/or a bounded
`--representatives N` low-risk sample per category/language. Blockers are never
sampled away. Generated HTML places real previews beside readable diagnostics.

Translated captured-fit captions require an explicit language override bound to
the exact text, approved font hash, size and native measurement evidence.
`propose-layout` returns a versioned, bounded, deterministic proposal; it does
not edit YAML, approve the result or alter English typography. Supply reviewed
proposals through `--definitions` after an explicit maintainer decision.
New independent colors are checked against the D01 registry; historical colors
are retained without becoming automatic approved exceptions. Reservations and
authorized color approvals retain Package B's transactional APIs. A preview
does not reserve, approve or persist a suggested color.

Arabic is not made render-ready merely by having a YAML file. The isolated
Noto Sans Arabic OFL evaluation uses existing HarfBuzz/bidi/compositor APIs, but
the font and language-specific layout are not approved. RTL/directional text
stays blocked pending explicit font and visual acceptance; there is no OS font
fallback. Existing approved fonts and composer code are not changed.

## Translation Deltas

```powershell
py -3.13 -m create_defaults.bulk translation-delta --before OLD.json --after NEW.json --preflight PREVIOUS_PREFLIGHT.json
py -3.13 -m create_defaults.bulk translation-delta --before OLD.json --after NEW.json --preflight PREVIOUS_PREFLIGHT.json --generate
```

Deltas compare actual key values, templates, source-language keys, resource
availability and explicit mappings/aliases. The SQLite key-to-variant index also
tracks fallback-source keys. Removed resources become unavailable tombstones,
not silently approved old outputs. Changed definitions/assets/fonts/layouts are
detected by per-variant validation fingerprints at the next scoped preflight;
`validation_delta` compares those reports. A fresh preflight is required after
external edits. There is no filesystem watcher or background approval service.

## Overlays

```powershell
py -3.13 -m create_defaults.bulk overlays --audit
py -3.13 -m create_defaults.bulk overlays --group genre --source logos_genre/Experimental.png --review
```

The checked-in overlay catalog preserves 36 source operations, 18 groups, both
sizes and 4,122 destination contracts from 2,061 inputs. No production operation
launches PowerShell or ImageMagick. Pillow performs sRGB conversion, metadata
stripping, explicit trimming, fit/upscale sizing and premultiplied-alpha Lanczos
resizing. PNG/RGBA output is bounded, hash-verified and atomically promoted.
Pixel differences from ImageMagick are retained as review evidence, not declared
exact parity or hidden behind adjusted thresholds. Overlay review is separate
from translated-poster counts and requires individual warning acceptance.

## Review APIs and CLI

```powershell
py -3.13 -m create_defaults.bulk review list --state ready_for_review
py -3.13 -m create_defaults.bulk review batch --id VARIANT --inspected VARIANT
py -3.13 -m create_defaults.bulk review approve --id VARIANT --version 1 --reviewer NAME
py -3.13 -m create_defaults.bulk review reject --id VARIANT --version 2 --reviewer NAME --comment "Needs another layout"
py -3.13 -m create_defaults.bulk review export --report REVIEW.json
```

`Reviews` supports ingest, item/query, attach verified worker previews, batch,
individual approve/reject/comment/reopen, exact-membership low-risk group
approval, selective invalidation and audit export. `--accept-warning CODE` must
enumerate exactly the current nonblocking warnings. Blocked/private outputs,
changed bytes/assets, obsolete policy, stale versions and changed membership
cannot be approved. All high-risk and previously rejected/stale items require
individual review. Immutable events retain reviewer attribution, timestamps,
versions, exact fingerprints, bytes, accepted warnings and inspection scope.

SQLite migrations preserve existing jobs, claims and receipts. A changed worker
wrapper creates a new generation only after verifying the old owned receipt;
unowned, corrupt or unfinished outputs are never adopted.

CLI reviewer strings are development attribution, not authentication. Real
authorization is mandatory before any production approval service. Rendering,
previewing, comments, review decisions and batch creation never publish artwork.

## Exit Outcomes

| Code | Meaning |
| --- | --- |
| 0 | Complete validation, verified rendering, or audit-only command |
| 2 | Invalid input/configuration/schema |
| 3 | Partial required scope, including audit coverage with blockers |
| 4 | Read-only remote failure |
| 5 | Stale/conflicting review or state action |
| 6 | Strict preflight blocked before rendering |
| 7 | Runtime rendering incomplete/failed |

Full production rendering, multilingual acceptance/soak, legacy throughput
comparison and cutover remain Package E. Flask, authentication, deployment and
publication are not part of Package D or implicitly authorized by Package E.
