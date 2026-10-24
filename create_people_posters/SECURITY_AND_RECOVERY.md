# People credential containment and recovery

Status: security/recovery implementation for review. The protected workflow
extension requires a separate maintainer decision before it can be applied.
This document is not a publication, lifecycle activation or merge approval.

## Incident and operator action

The original `recover_edge_chops.tmdb_person`/`tmdb_candidates` requests placed
the v3 API key in query parameters. Requests included that URL in a TLS exception.
`recover_one` copied the exception text into `RecoveryRow.note`; `log` and the
CSV reporter then emitted it. The orchestrator also treated every unresolved
person as exit 1 and stopped after otherwise successful processing.

Treat the exposed credential as potentially compromised. The operator must
revoke/replace it through the TMDB account's API settings, update the private
runtime secret/environment, and restart affected processes. Code cannot make a
previously exposed key safe. No replacement credential is included here.

Review earlier terminal transcripts, People logs, recovery CSVs, archived support
files, CI logs/artifacts and copied issue/chat reports. Inspect with a private
value-aware scanner that emits filenames/counts only; never echo matching lines
or put a credential in a shell argument, ticket or screenshot. Restrict exposed
artifacts and follow the hosting provider's removal procedure. Rotation and any
remote removal/history changes remain operator actions, not automated here.

TMDB supports its **API Read Access Token** in a Bearer header. Configure the
private `TMDB_READ_ACCESS_TOKEN` to prefer it. A legacy `TMDB_KEY` remains a v3
query credential; it is never misrepresented as a Bearer token. The provider
transport never emits its authenticated URL. A future service must use the read
token and must not construct browser/service query URLs containing credentials.
See [TMDB's application authentication documentation](https://developer.themoviedb.org/docs/authentication-application).

## Source-backed exposure audit

The baseline is main `46e1334504fcdd598e0c34fcd45612ff58e91074`.
The local audit inventory records source paths, normalized source hashes,
line numbers, function/class scope and finding kinds, with no source excerpts or
configuration values. It covers tracked/new Python, PowerShell, workflows,
documentation and text/JSON definitions; generated configuration and binary
artwork are not copied into that inventory. The report accompanying this PR
records its final count/hash and complete changed-file inventory.

| Boundary and source evidence | Finding and treatment |
| --- | --- |
| `recover_edge_chops.py`: TMDB helpers, `recover_one`, staging, `log`, `write_report` | Original leak and raw report fields; closed network failures, sanitized CSV/HTML/JSON, exact recovery receipts and durable rollback. |
| `tmdb_people.py`: SDK construction and `save_image` | SDK parameter debug logs and request exceptions; credentials registered before SDK initialization, secured read-only session, no raw exception arguments passed to logging. Existing SDK paging/person/image behavior retained. |
| `tmdb_top_people_list.py`: `tmdb_get` | Direct authenticated query and unbounded provider delay; shared bounded client. |
| `review_tmdb_profile_alternates.py`, `stage_original_candidates.py` | Direct authenticated lookup and raw request failures; shared JSON/image transport and checked TMDB profile paths. |
| `resolve_original_images.py`: TMDB, Google, image download and reports | Provider errors, JSON decoding and URLs in CSV/unresolved reports; shared transport, closed JSON errors, sanitized serialization. |
| `orchestrator.py`: `run_cmd`, probe diagnostics, markers, cleanup, recovery handling | Inherited/captured subprocess output and raw persisted errors; pipe adapter, safe summaries, metadata rejection, nonce-bound partial receipt handling. |
| `remove_bg_birefnet.py`, `colorize_noncolor_ddcolor.py`, `sel_remove_bg.py`, `smoke_people_models.py` | Model, browser and child diagnostics; secure handlers, closed exception categories, guarded CLI entry points. Inference, alpha/colour/edge thresholds and model settings are unchanged. |
| `people_workspaces.py`, `people_publication_state.py` | Errors enter SQLite and exported manifests; sanitize errors before persistence, reject credential-bearing metadata before writing. Successful publication receipts retain their immutability. |
| `people_github.py`, `publish_people_github.py`, `sandbox_people_github.py`, `ensure_people_repo.py`, `update_people_repos.py` | Register configured/discovered token before requests; errors remain fixed categories, subprocess output is piped, console and persisted failure fields are sanitized. Destinations, authorization, conflict checks and publication algorithms are unchanged. |
| `find_and_download_missing_people.py`, `scan_kometa_logs.py` | Download failures, archive diagnostics and source log text; secure handlers and safe exception arguments. These consume local logs; no Quickstart/Logscan **upload** integration was found in this repository. |
| `audit_people_images.py`, `auto_readme.py`, `stage_original_candidates.py` | File logging, progress and structured reports; final handler protection and diagnostic serialization. |
| `create_people_poster.py`, `poster_renderer.py`, `poster_fonts.py`, `grayscale_sweeper.py` | Renderer/source bytes remain unchanged, preserving renderer fingerprints and completed poster checkpoints. Orchestrator processes run through the guarded adapter. A service must use the adapter for these existing local tools, not expose their raw entry points. |
| `face_crop.py` and DDColor model download | Public fixed model sources, not TMDB authenticated transport; caller and child diagnostics use the guarded boundary. No model downloads or live TMDB authentication are performed by security tests. |
| `github_inventory_core.py`, Defaults `bulk/remote.py` and `bulk/e_network.py` | Shared read-only/public asset transports already emit bounded/fixed failure categories and do not persist response bodies as diagnostics. Defaults lifecycle/renderer/publication sources remain outside this repair. |
| Defaults canary/library GitHub transports and legacy font comparisons | Existing read-only/approved GitHub paths or public font assets; source reviewed for credential construction and diagnostic sinks. No People credential is passed to them; no broad Defaults logging rewrite or publication is introduced. |
| `.github/workflows/` | Existing validation artifacts are explicitly selected CI evidence, not People runtime configurations/log trees. Proposed new jobs upload only their CI evidence namespace and receive no TMDB/publishing secrets. |

No historical logs containing the incident credential are uploaded or reproduced
as evidence. No claim is made that earlier public exposure has been remediated.

## Shared security boundary

`people_diagnostics.py` registers known runtime secrets and bounded alternate
representations (URL/JSON/unicode/base64/base64url/hex). Generic field detection
also covers case/percent variants, provider fields, authorization, cookies and URL
userinfo. Diagnostic URLs retain host/path but drop userinfo, query and fragment.
Known values are removed even under an unrelated field name. Redaction is
idempotent so re-exporting a record does not corrupt its integrity check.

`Diagnostic` is a closed immutable allowlist: provider, operation, category,
status, retryability, endpoint and a non-secret correlation ID. Network errors
never carry request/response objects, headers, bodies or raw exception chains.
HTTP status and retryability must agree with the category. JSON decoding errors
also become closed records. Safe application conflict/model guidance comes from
fixed categories; arbitrary exception strings/repr are not forwarded.
Provider sessions disable ambient netrc/proxy authentication. Environments that
depend on an ambient proxy/CA configuration require an explicit, server-controlled
transport integration; there is no insecure automatic authentication fallback.

`RedactingFormatter` sanitizes the final formatted representation, including
arguments and extra fields, and removes raw exception/stack information. Handler
failures use a fixed withheld message, never logging's raw-record fallback.
Unknown handler destinations are rejected. `RedactingStream` buffers complete
lines, handles text/binary writes, and discards incomplete/over-budget records
rather than emit their fragments. Sanitizer failures withhold content.

`people_process.run_process` always pipes both OS streams, including native
library `os.write` output, before console/file/caller delivery. It bounds captured
output, handles timeout/cancellation, and returns only sanitized captures.
Credential-bearing argv is rejected; credentials belong in private runtime
configuration. Guarded direct People CLIs use this parent/worker arrangement too.
`people_secure_cli.py --script SCRIPT -- ...` is the supported adapter for an
existing renderer/tool. Its internal worker mode is not a public service API.
Rendering source bytes are not changed just to install logging hooks.

Example (synthetic failure; no credential or full authenticated URL):

```text
provider=TMDB operation=search_person category=tls status=None retryable=True endpoint=/3/search/person correlation_id=0123456789abcdef0123456789abcdef
```

CSV/JSON/HTML and selected-report ZIP exports sanitize nested diagnostic fields.
The ZIP interface does not accept a filesystem tree, environment dump, binary
configuration snapshot or arbitrary Python objects. Job/model metadata rejects
sensitive content instead of silently changing identities or fingerprints.

## Recovery contract

| Outcome | Script exit | Orchestrator action |
| --- | --- | --- |
| All recovered, exhausted or no eligible work | 0 | Validate exact current receipt; complete recovery checkpoint. Exhaustion alone is nonfatal; artwork and quality warnings remain. |
| Unresolved without a supported retryable diagnostic | 1 | Stop; no success checkpoint. |
| Fatal/unsafe state, missing authentication for selected work, corruption, disk failure, lost artifacts | 2 | Stop; retain artifacts/backups and require correction/review. |
| At least one transient unresolved, no fatal/nonretryable unresolved | 3 | Validate receipt; continue completed work, persist pending names, never create recovery `.done`. |

The request wrapper makes at most three GET attempts by default (hard maximum
four), with finite connect/read timeouts and exponential backoff. TLS, timeout,
connection reset, 429 and 5xx remain retryable. A provider delay over 30 seconds
or malformed delay ends the attempt as unresolved instead of retrying early.
401/403 and invalid responses are not silently retried or treated as exhaustion.

Transient lookup/download failures are never added to exhausted-name or permanent
attempted-candidate files. Valid rejected alternatives can remain attempted.
Recovered checkpoints bind exact output hashes, settings, roots and renderer
fingerprints; unchanged successful people are reused. Changed/missing retained
outputs or malformed checkpoints fail closed. Per-person reports/checkpoints are
written during progress, retaining earlier successful work on a later failure.

Inline recovery keeps current artwork through download/screening. A durable
per-person transaction captures exact original bytes/absence, including native
sources and sidecars, before rendering/staging. Failure or cancellation restores
and verifies them. All backups are checked before touching restoration targets;
interrupted prepared journals reconcile before another attempt, and corrupt or
changed journals block. Backups/history are retained, never auto-pruned.

Orchestrator receipts bind the run nonce, complete outcomes, changed/retry names
and digest. Missing, stale or contradictory receipts cannot create success.
Resume selects pending people; existing poster and upstream model checkpoints
remain intact. Only actual accepted replacements invalidate downstream image/
README synchronization. Publication remains content/hash driven, so unchanged
images are skipped. This repair grants no new publication destination or rights.

An already immutable, published **batch** plan is not edited to accommodate a
later alternate. If a later recovery changes its approved membership/bytes, use
the existing explicit new-batch workflow; conflict/receipt safeguards still stop
silent substitution. Persistent mode can use its normal fresh publication plan.

## Future service integration and limits

No public service is implemented. Credentials and raw HTTP objects must remain
server-side. The service must own an isolated workspace, constrain executable
and script selections, register credentials before work, and use the guarded
process/closed diagnostic interfaces. It must not expose arbitrary Python,
environment overrides, the internal worker mode, raw tool entry points, raw
tracebacks, health dumps or whole-tree support downloads. User debug options do
not grant access to server configuration or credentials. Unknown integrations
remain disabled until their diagnostic adapters have containment tests.

Unregistered/novel arbitrary encodings cannot be made safe by regex guessing;
closed diagnostic records are the primary boundary. Text redaction is defense
in depth. Local input artwork/configuration is not a downloadable diagnostic
surface. Existing historical artifacts require an operator audit, not a claim
that this patch retroactively sanitizes them.

The new CI proposal keeps all original test-ID sets, historical 14,079-output
checks, 190 protected source members, nonactivation AST checks, resource limits
and 15-minute timeouts. It separately reconciles every People test across the
original executor and bounded diagnostics/recovery/compatibility groups on each
OS. Missing, cancelled, failed, skipped or stale mandatory security evidence
cannot satisfy Validation acceptance. Existing explicit platform/opt-in skips
remain visible. Exact final-head CI evidence is required after approval; local
tests alone are not final security acceptance.
