| Phase | Name | Status | Detailed documentation | Approval |
| --- | --- | --- | --- | --- |
| 1 | Discovery and Baseline | IN PROGRESS | [PHASE1_DISCOVERY.md](PHASE1_DISCOVERY.md) | PENDING |
| 2 | Business Rules and Category Contracts | NOT STARTED | TBD | Not requested |
| 3 | Translation and Destination Safeguards | NOT STARTED | TBD | Not requested |
| 4 | Lifecycle Operations | NOT STARTED | TBD | Not requested |
| 5 | Review and Publication Integration | NOT STARTED | TBD | Not requested |
| 6 | Pilot and Acceptance | NOT STARTED | TBD | Not requested |

## Decision log

- **2026-10-20:** Maintainer requested Phase 1 documentation and read-only discovery only. [Phase 1 draft PR #13](https://github.com/Kometa-Team/Defaults-Image-Creation/pull/13) contains the five discovery documents and local read-only validation results. Phase 1 findings await explicit acceptance; approval remains PENDING. No later phase is authorized.
- **2026-10-20:** Fresh GitHub reads confirmed source `main` at `e7febf88d1dc8f8b93408e88da78e524b191acea` ([source cutover PR #12](https://github.com/Kometa-Team/Defaults-Image-Creation/pull/12)) and artwork `master` at `dfff31ab08446353844bb97de601c3a64edc8220` ([overlay PR #202](https://github.com/Kometa-Team/Default-Images/pull/202)). Neither head had advanced beyond the supplied historical baseline. Source repository default/development target is `main`.

## Permanent roadmap

This is the Kometa Defaults Lifecycle Management project. Status values are **NOT STARTED**, **IN PROGRESS**, **BLOCKED**, and **COMPLETE**. Evidence may justify updating progress; only explicit maintainer acceptance permits COMPLETE. A draft documentation PR does not constitute acceptance or authorization for the next phase.

1. **Discovery and Baseline:** audit all categories, definitions, profiles, generators, fonts, assets, translations, filenames, dependencies and exceptions. Deliver the [discovery](PHASE1_DISCOVERY.md), [category rules](CATEGORY_RULES_MATRIX.md), [exceptions](EXCEPTIONS_REGISTER.md), and [gaps](GAP_ANALYSIS.md). No production behavior changes.
2. **Business Rules and Category Contracts:** establish versioned maintainer-controlled category designs, intentional variants and submitter-editable content. Lock caption requirements, typography, fitting, geometry, effects, dimensions, casing and naming. Category-wide design changes require explicitly scoped bulk review.
3. **Translation and Destination Safeguards:** require English and supported non-English preflight against the authoritative Weblate-backed catalog. Missing English must block English generation; report missing non-English values before full generation. Official Default-Images receives English artwork only; non-English stays local or goes to an explicitly configured user repository.
4. **Lifecycle Operations:** add safe ADD, UPDATE, RENAME and DELETE with stable identity, separate display/render/source/local/public names, dependency impact and incremental generation. Definition removal retains public artwork by default; deletion requires explicit approval.
5. **Review and Publication Integration:** reuse Package E previews, exact approvals, verified workers, bounded resumable transport, draft PRs, remote hashes and full-tree reconciliation. Extend the operation model for authorized general renames, deletions and category-wide changes. Transport batches, review populations and publication PRs remain independent.
6. **Pilot and Acceptance:** start with Playlist, then representative other categories. Exercise additions, edits, renames, removals, translation failures, shared dependencies and category-wide changes; prove unchanged outputs, destination boundaries and rollback. Record explicit final production acceptance.

Phases 2–6 are prospective scope only. Phase 1 authorizes no generation, artwork writes, merges, translation changes or lifecycle implementation.
