# Local Playlist staging flow

This is a runnable loopback-only prototype for the ten approved JPEG fixtures. A contributor selects a fixture and uploads its exact JPEG; the app validates its approval/hash and dimensions, stores an immutable preview and displays it. A separate fixture maintainer login approves that exact SHA-256, then stages it. The app checks absent CREATE paths or exact REPLACE preimages, writes into its newly owned destination, rereads the destination hash and records a receipt. No existing directory can be adopted as a destination.

It submits already-rendered, approved JPEGs. Arbitrary logo-to-render submissions, real authentication/roles, native historical Playlist lifecycle UPDATE, real catalog edits and live transport are separate work. The existing native eight-create result is independent evidence; this browser staging flow must not be described as ten-item native M6 acceptance.

## Run locally

From a clean committed checkout with the existing Python dependencies:

```text
python -B -m create_defaults.phase6.staging_app --state config/playlist-browser-review-1 --port 8765 --expected-head <FULL_COMMIT_SHA>
```

Open `http://127.0.0.1:8765`. The app prints the path to `fixture-access.json`, which contains two generated local fixture access codes. Use separate browser profiles/windows for contributor and maintainer. Upload the corresponding JPEG from `create_defaults/phase6/staging_fixtures/approved/playlist/`. The destination and `staging-receipts.json` remain under the chosen new state directory. A restart needs a new state directory so earlier evidence stays intact.

The app binds to loopback and accepts only same-origin bounded JSON writes. Server-side role checks, HttpOnly SameSite cookies and CSRF tokens apply to approval/staging. Missing, changed or linked preview objects, unapproved hashes, create collisions, stale preimages, changed fixture inputs and unrelated destination edits fail closed. Source verification runs at startup and before/after each staging write against the independently supplied HEAD. Fixture approval grants no live operational authority.

## Focused checks

```text
python -B -m unittest create_defaults.phase6.tests.test_staging_app -v
```

For real browser verification, install `playwright-core@1.65.1` in a separate tooling directory (not the renderer environment), using `npm install --prefix <TOOLS> --ignore-scripts --no-audit --no-fund playwright-core@1.65.1`. Chrome must already be installed. Set `PLAYWRIGHT_MODULE` to `<TOOLS>/node_modules/playwright-core`, launch the app above, then run:

```text
node create_defaults/phase6/tests/staging_browser.cjs <STATE_DIRECTORY> create_defaults/phase6/staging_fixtures <NEW_EVIDENCE_DIRECTORY>
```

The browser test uses two isolated Chrome contexts, normal file inputs and UI buttons. It proves one CREATE and one REPLACE first, then all ten; independently hashes destination files, requires eight creates/two replacements, preserves the other seven historical posters and checks role/CSRF/wrong-render rejection. Screenshots, first-two results and the full result are saved in the evidence directory. The only allowed page-request origin is the local app.

## Two-file publication review

[Replacement plan](review/replacements/replacement-plan.json) and [unapplied Git binary patch](review/replacements/two-playlist-replacements.patch) retain the original X-Men/Clone Wars catalog identities and public paths. The exact production preimages were read from pinned Default-Images master `dfff31ab08446353844bb97de601c3a64edc8220`; they match the historical comparison preimages. The patch passed an independent two-file apply/reverse round-trip in a new local fixture. It remains unapplied to Default-Images.

The generic publication operator supports exact existing-path replacements, requiring non-null previous hashes, exact old/new blobs, complete two-file `M` diffs, policy/manifest review and current-head verification. The current native Playlist lifecycle adapter still permits assigned ADD only; accepting historical UPDATE there requires a separate exact adapter/review change. This staging app does not weaken that gate.

Live reservations, catalog mappings, current operational authority, publication, activation and merge remain pending. Re-read the live head/preimages and obtain exact operator decisions before considering the live two-file update.
