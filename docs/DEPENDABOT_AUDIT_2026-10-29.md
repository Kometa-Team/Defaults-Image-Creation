# Dependabot audit, 2026-10-29

Audited `Kometa-Team/Defaults-Image-Creation` at main commit
`d013af718881dc5ec82178ee85540e29a0fb7ec3`. The REST alert API returned
**41 open alerts: 5 critical, 23 high, 13 medium**. Case-normalized grouping
produces **one package/manifest pair**, Pillow in
`create_defaults/phase2/requirements.txt`.

The [machine-readable evidence](dependabot-audit-2026-10-29.json) contains all
41 alert numbers, packages, manifests, detected requirements/versions,
severities, advisory links, affected ranges and first patched versions, plus
the dependency-graph snapshot, resolution results and wheel comparisons.
These are actual API results, not the push-time vulnerability banner.

## Root causes and minimum changes

| Root cause / scope | Current main evidence | Minimum safe version / change |
| --- | --- | --- |
| 41 Pillow alerts, optional Phase 2 experiment | Every alert detects `12.3.0`. The child graph contains both `=12.3.0` and `=13.0.0`; the file inherits parent `Pillow==13.0.0`. A clean pip resolution selects `13.0.0`, outside every alert range. | All 41 advisories first patch in **13.0.0**. Keep that version; make the same pin explicit in the child to remove inheritance ambiguity and request re-indexing when merged. |
| Vulnerable People base resolution, absent from those 41 alerts | Unbounded `Pillow` plus `rembg[cpu]==2.0.85` resolves **Pillow 12.3.0** on Python 3.13. Rembg's declared Pillow range is `>=12.1.0,<13.0.0`. | Pin **Pillow 13.0.0** and **rembg 2.0.86**, the first release permitting Pillow 13. Do not downgrade Pillow to satisfy old rembg. |
| Inconsistent pinned People CPU profile | It already requests Pillow 13 but pins rembg 2.0.85. Clean resolution fails with their incompatible constraints. | Change only rembg to **2.0.86**. All other CPU pins remain unchanged. |
| Stale Python setup note | Root README still advertises Python 3.10; Pillow 13 and rembg 2.0.86 require Python 3.11+. | Document **3.11+**, with **3.13 recommended** and used by CI. |

The Phase 2 edge is demonstrably inconsistent with current source and clean
resolution. Stale inherited graph data is the supported explanation; the API
does not reveal why that old edge survived. The draft cannot refresh main's
dependency graph. After a reviewed merge, re-query alerts, GraphQL manifests
and the SBOM to confirm the child no longer has Pillow 12.3.0. If it remains,
investigate GitHub ingestion/submission sources rather than dismissing alerts.

## Manifest ownership and retention

| Manifest | Classification and current Pillow assessment | Disposition |
| --- | --- | --- |
| `create_defaults/requirements.txt` | Active Default Images generator; exact 13.0.0 is outside all 41 ranges. | Unchanged. |
| `create_defaults/requirements-bulk.txt` | Active Default Images operator/CI profile, with testing extras; inherits exact 13.0.0. | Unchanged. |
| `create_defaults/phase2/requirements.txt` | Experimental Package A schema/audit tool; not the active generator. Code is still selected by CI and documented for reproduction. Effective version is 13.0.0. | Retain; explicit matching pin. |
| `create_defaults/canary/requirements-staging.txt` | Experimental staging/canary profile; exact 13.0.0 is safe against these ranges. Still has regression/provenance references. | Retain. |
| `create_people_posters/requirements.txt` | Active People orchestrator base profile; clean main resolution selects vulnerable 12.3.0. | Pin patched Pillow and compatible rembg. |
| `create_people_posters/requirements-ddcolor.txt` | Active People orchestrator's optional DDColor engine profile; Pillow floor is already >=13.0.0. | Unchanged. |
| `create_people_posters/requirements-rembg.txt` | Active People orchestrator CPU profile; exact Pillow 13.0.0, but incompatible rembg cap. | Update rembg only. |

No manifest is proven unused within its documented or tested scope, so none is
deleted merely to eliminate alerts. Phase 2 and canary are experimental,
retained reproduction tools, not active rendering entrypoints. Bulk includes
development/testing tools but is also the supported operator installation.
Optional scope never makes an affected installed Pillow safe. This audit
reconciles the retrieved alerts; it is not a claim that every unpinned package
or existing virtual environment is free of other vulnerabilities.

## Compatibility and behavior validation

- Pillow's [release metadata](https://pypi.org/pypi/Pillow/13.0.0/json)
  requires Python >=3.11 and supplies CPython 3.13 Windows x64 and Linux x64
  wheels. The existing Windows/Linux workflows use Python 3.13.
- Clean Windows x64 dry runs succeed for the changed Phase 2, People base and
  fully pinned People CPU profiles. Phase 2 resolves exactly the same package
  versions before and after its explicit pin. People resolves Pillow 13.0.0
  and rembg 2.0.86. The previous base resolves vulnerable 12.3.0; the previous
  CPU profile reproduces `ResolutionImpossible`.
- The existing dependency-provenance workflow now performs those three clean
  binary-only dry runs on **both Windows and Linux**, without changing its
  installed test environment. The existing cross-platform validation workflows
  and their required checks remain enabled; the PR checks record final results.
- Verified PyPI wheel SHA-256 hashes before comparing rembg 2.0.85 and 2.0.86.
  The inference entrypoints, session factory, base session, BiRefNet portrait,
  BiRefNet general and ISNet implementation are byte-identical. Differences are
  new session registrations/modules and an unused cloud session's mode handling.
  The application's three-model allowlist is unchanged; no new cloud or FP16
  model becomes selectable through the orchestrator.
- No renderer, fonts, layout, image processing settings, model checksums,
  generation entrypoints, orchestration or publication source is edited. No
  images are generated or published. This audit does not claim a new full-model
  inference/visual acceptance run; active rembg code equality, unchanged CPU
  pins, resolver checks and existing regressions support the dependency update.

## Preserving existing CI provenance

The repository verifies 190 protected sources, 299 adoption sources and 2,927
historical files. The narrow dependency-audit transition binds exact old/new
bytes for the changed manifests, workflow, audit evidence and necessary CI
readers/tests. Historical manifests and test-ID inventories stay byte-identical;
unknown edits, rollback, deleted files and links still fail. The two existing
test expectation updates follow that exact successor chain; no test IDs,
timeouts, renderer policies or publication gates are removed or relaxed.

This branch is separate from Phase 5 M2. It is a **draft PR**, with no automatic
merge and no dismissed alerts. Main's alerts remain open until a reviewed merge
and a confirmed dependency-graph refresh.
