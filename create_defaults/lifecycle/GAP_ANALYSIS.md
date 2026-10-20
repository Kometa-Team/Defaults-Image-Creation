# Gap analysis and maintainer decisions

**Phase 1 findings; acceptance PENDING.** Observed capabilities are in [discovery](PHASE1_DISCOVERY.md); exact current variants are in the [category matrix](CATEGORY_RULES_MATRIX.md). Everything described as a future contract, operation or safeguard below is proposed, not implemented or approved.

## Priorities by risk and impact

| Priority | Evidence-backed gap / impact | Recommended phase and acceptance evidence |
| --- | --- | --- |
| P0 | Schema permits category design edits without a category-specific contract. Global approved font bytes do not enforce Playlist typography. Flattening era, white, captionless/other or separator variants would alter intentional design. | **2:** versioned maintainer-owned contracts plus named variants and exact exception references; prove unauthorized field edits block and approved category-wide edits enumerate their complete scope. |
| P0 | English operator defaults to a frozen fixture; preflight is selectable/partial and not a mandatory authoritative all-language gate at every entrypoint. Non-English can have its own value even when English source key is absent. | **3:** pinned authoritative source/key validation, explicit supported language/applicability policy, report all missing values before full generation; test missing catalog/English/non-English separately. Never silently replace current production input. |
| P0 | Official operator is English/overlays, but a complete multilingual destination contract and user-repository route are absent. Discovery is broader than the eleven compatibility codes. | **3:** enforce official-English-only at the final publication boundary; non-English local or explicit user repository. Test hostile/mixed manifests and routing errors. No Phase 1 remote artwork operations. |
| P0 | Generated child IDs contain output paths. General rename/delete semantics and tombstones are missing; removal from definitions cannot safely imply a public delete. | **4:** persistent identity independent of filename, explicit operation ledger and dependency impact; retain old public image by default and require exact delete authorization. Test case-only/Unicode/general rename and rollback. |
| P1 | Existing bulk selection and render invalidation are not category-wide design approval. Review groups, transport batches and publication PRs can be confused without an explicit operation scope. | **2 / 5:** bind contract delta, full affected membership, exact candidate/context hashes and reviewed exceptions; keep approval grouping separate from technical batch sizing and PR grouping. |
| P1 | Current staging supports additions/replacements and narrow approved overlay case renames, not arbitrary moves/deletes. Generic rollback is a runbook rather than a reverse lifecycle transaction. | **4 / 5:** extend existing transport only after defining operation semantics; verify before/after paths, non-force chain, remote SHA-256 and entire tree, with interruption/recovery and reversal evidence. |
| P1 | Fallback metadata records a reviewer but does not authenticate the decision. RTL discovery does not mean font/shaping/layout approval. Available resources include substantial missing/empty values. | **3:** maintainer-bound fallback receipts, script-font/layout scope, strict invalidation, explicit incomplete-resource reporting. Preserve all previous approvals when identities remain unchanged. |
| P2 | Shared profile/generator edits and asset changes already invalidate consumers, but no submitter-facing impact receipt or business ownership exists. Explicit year ranges do not expand automatically. | **4:** expose exact affected IDs/languages/dependencies without introducing automatic year additions or regeneration outside scope. |
| P2 | Committed migration evidence contains historical then-pending states; current remote merge status must be checked independently. No permanent lifecycle acceptance ledger existed before these documents. | **1 / 6:** pin source/art/translation baselines, preserve dated exception decisions, add new evidence rather than rewrite historical receipts; require explicit phase acceptance. |

## Proposed contract structure — documentation only

The future design should describe the following fields. This is **not** a schema, YAML profile, parser, validator, CLI or approved policy.

| Section | Intended responsibility |
| --- | --- |
| Identity and ownership | Contract ID/version, category, maintainer owner, source baseline and explicit approval receipt. |
| Named variants | Distinguish era styles, white/color logo treatments, captionless/other posters, separator families and individually accepted exceptions. |
| Caption and languages | Required/prohibited/conditional caption; authoritative key/order-type mapping; casing/templates; explicit applicability; fallback and RTL approval scope. |
| Locked design | Hash-bound font family/weight, font-size/fitting bounds and reviewed language overrides; logo scale/anchor, offsets, margins, background policy, effects, dimensions and encoding. |
| Submitter content | Allowed identity/display metadata, exact asset/provenance, catalog-backed content key, permitted variant and brand/color assignment; reject modifications to locked design. |
| Naming and routing | Stable identity separate from source/display/render/local/public names, exact case/Unicode policy, destination language boundary and user repository configuration. |
| Dependencies and impact | Fonts, logos, translations/templates, profiles, generators and parent artifacts; full affected membership and incremental/no-op expectations. |
| Review and lifecycle | ADD/UPDATE/RENAME/DELETE intent, retained/tombstoned paths, explicit removal approval, review/context hashes, artifact hashes, publication plan and rollback evidence. |

Category constants proposed for locking are the design portion of each category's observed variants, not all currently equal fields indiscriminately. For example Playlist's typography/geometry/effects should be inherited while brand art and appropriate brand color vary. Year/Decade need separate era designs. Captionless logos may contain lettering in the source image without having a translated composer caption.

## Decisions for maintainer review

1. **Accept or amend the Phase 1 baseline and exception inventory.** Confirm intentional variants and whether the measured facts are sufficient to progress. Acceptance marks Phase 1 COMPLETE only after an explicit decision; Phase 2 work still requires authorization.
2. **Category ownership and edit boundary (Phase 2).** Decide who approves contracts, which named variants are first-class, permitted brand/color content and whether Playlist's proposed locked values reflect the intended design. Decide the separate category-wide design-change review boundary.
3. **Language and routing policy (Phase 3).** Choose the supported language set, freshness/update cadence, incomplete-language blocking/report policy, English-source requirement, authenticated Weblate component mapping, fallback authority and RTL/font review scope. Choose user-repository configuration and final destination enforcement.
4. **Identity and removal policy (Phase 4).** Decide how generated identities persist across path/name changes, whether old paths are retained or explicitly renamed, exact deletion authority and rollback retention. Preserve source spelling without normalization-driven public renames.
5. **Review and pilot acceptance (Phases 5–6).** Confirm reuse of exact Package E approvals/transport, limits for bulk changes and the Playlist pilot cases, followed by representative era, generated-family, captionless, language-template and overlay examples. Define unchanged-output and rollback acceptance.

No new gallery review, candidate regeneration or publication approval is requested by this document. Existing decisions are retained for unchanged artifacts. The review required now is acceptance of these discovery findings, followed by a separate decision about the next phase.

## Phase 1 delivery validation

The draft PR contains exactly `ROADMAP.md`, `PHASE1_DISCOVERY.md`, `CATEGORY_RULES_MATRIX.md`, `EXCEPTIONS_REGISTER.md` and `GAP_ANALYSIS.md` under this directory. Validation must confirm no tracked renderer, Python, YAML, fonts, assets, translation files or production workflows differ from the pinned source baseline. Read-only graph/metadata audits and documentation link/count checks are sufficient local checks; rendering suites are not rerun solely for Markdown. Automatic PR CI results are reported by actual run/head separately. Source and artwork production branches are checked again at delivery. Stop at the draft PR; do not merge or begin Phase 2.
