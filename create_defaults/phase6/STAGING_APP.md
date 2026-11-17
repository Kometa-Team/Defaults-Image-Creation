# Local Playlist staging flow

This loopback-only prototype generates posters through the existing production Python renderer from a contributor-selected logo, style, background and required caption. The ten main requests compare generated JPEG bytes against the immutable approved references. Different bytes fail a required check; prior visual approval is never carried over. Generation records exact parameters, asset hashes, renderer hash, Pillow version and layout measurements. A separate fixture maintainer sees the exact render, before/after catalog state and current required checks, approves that complete change fingerprint, then stages it. Destination bytes and the physical staging catalog are independently reread after every write. No existing directory can be adopted as a destination.

The fixed input set is eight approved Playlist additions, X-Men and Clone Wars replacements, a disposable Playlist and a disposable existing Franchise preset. Logo selection is restricted to those local assets; arbitrary filesystem/network inputs are rejected. The catalog under the owned state directory is a browser fixture, not the native/live catalog. Native historical Playlist UPDATE and native tombstone restoration remain blocked. Real authentication/roles and live transport are separate work. The independent native eight-create evidence remains intact; this browser proof is not ten-item native M6 acceptance.

## Run locally

From a clean committed checkout with the existing Python dependencies:

```text
python -B -m create_defaults.phase6.staging_app --state config/playlist-browser-review-1 --port 8765 --expected-head <FULL_COMMIT_SHA>
```

Open `http://127.0.0.1:8765`. The app prints the path to `fixture-access.json`, containing two generated local fixture access codes. Use separate browser profiles/windows for contributor and maintainer (ordinary/incognito works). The destination, `catalog.json` and `staging-receipts.json` stay under the new state directory. A restart needs a new directory so earlier evidence remains intact.

1. **Contributor Add:** choose Alien & Predator (or Disposable Playlist), select its Playlist style and logo, retain the approved colour and `TIMELINE ORDER` caption, click **Generate preview**, inspect the preview and checks, then **Submit generated preview**.
2. **Maintainer:** sign in separately, reload, inspect the exact JPEG/hash, expand **Catalog change**, review every required check, click **Approve exact render and change**, then **Write to staging and verify**. The receipt records the file hash and exact catalog entry. Approval is bound to both image bytes and catalog pre/postimages, not just a poster hash.
3. **Replace:** choose X-Men or Star Wars The Clone Wars in the contributor form and repeat. Both keep the original catalog identity and existing destination path. To exercise a second replacement yourself, regenerate the Disposable Playlist with another background; it becomes an in-place REPLACE.
4. **Failed check:** change a main request's background to `#123456`, generate and submit it. Maintainer approval is disabled and the server rejects an attempted approval because the reference bytes differ. Regenerate with the approved inputs for a passing request; the failed request stays in the evidence.
5. **Removal/add-back:** first stage Disposable Playlist. Maintainer clicks **Attach active reference**; contributor clicks **Request disposable removal**. Inspect its current poster, proposed deletion/retirement and failed dependency check: approval is blocked. Maintainer releases the reference, contributor submits a fresh removal (the old request is stale), then maintainer approves/stages it. The file is absent and the catalog entry retired. Generate Disposable Playlist again; its RESTORE request retains the tombstoned staging identity/path and creates the file again. This restoration belongs only to the owned fixture catalog; the native registry explicitly rejects tombstone reuse.
6. **Second supported style:** choose Disposable Franchise, select its existing Franchise logo-only style and the supplied Franchise logo. The caption input disappears; generation uses the existing unbounded renderer preset without introducing text/compositing changes. Submit, approve and stage it normally.

The app binds to loopback and accepts only same-origin bounded JSON writes. Server-side roles, HttpOnly SameSite cookies and CSRF tokens apply. Missing/changed/linked objects, unapproved main hashes, create collisions, stale catalog/file preimages, changed inputs and unrelated destination edits fail closed. Source verification runs at startup and before/after generation and staging against the independently supplied HEAD. Render assets are freshly hashed before/after generation and again in review. A failed closing source proof restores the prior file/catalog state. Dependency changes invalidate prior requests/approvals. Fixture approval grants no live authority.

## Focused checks

```text
python -B -m unittest create_defaults.phase6.tests.test_staging_app -v
python -B -m unittest create_defaults.phase6.tests.test_staging_lifecycle -v
```

For real browser verification, install `playwright-core@1.65.1` in a separate tooling directory (not the renderer environment), using `npm install --prefix <TOOLS> --ignore-scripts --no-audit --no-fund playwright-core@1.65.1`. Chrome must already be installed. Set `PLAYWRIGHT_MODULE` to `<TOOLS>/node_modules/playwright-core`, launch the app above, then run:

```text
node create_defaults/phase6/tests/staging_lifecycle_browser.cjs <STATE_DIRECTORY> create_defaults/phase6/staging_fixtures <NEW_EVIDENCE_DIRECTORY>
```

The browser test uses two isolated Chrome contexts and normal contributor generation/submit and maintainer review buttons. It proves a CREATE and REPLACE first, all ten reference/destination hashes, unchanged replacement identities/paths and seven historical files/catalog rows, required-check denial, the disposable lifecycle (including active-reference and stale-request denial) and a generated second style. Screenshots and JSON evidence are saved in the new evidence directory. Only loopback requests are permitted. The earlier upload-only proof and its automation remain historical evidence; that superseded upload route is not exposed by the generated-browser app.

## Two-file publication review

[Replacement plan](review/replacements/replacement-plan.json) and [unapplied Git binary patch](review/replacements/two-playlist-replacements.patch) retain the original X-Men/Clone Wars catalog identities and public paths. The exact production preimages were read from pinned Default-Images master `dfff31ab08446353844bb97de601c3a64edc8220`; they match the historical comparison preimages. The patch passed an independent two-file apply/reverse round-trip in a new local fixture. It remains unapplied to Default-Images.

The generic publication operator supports exact existing-path replacements, requiring non-null previous hashes, exact old/new blobs, complete two-file `M` diffs, policy/manifest review and current-head verification. The current native Playlist lifecycle adapter still permits assigned ADD only; accepting historical UPDATE there requires a separate exact adapter/review change. This staging app does not weaken that gate.

Live reservations, catalog mappings, current operational authority, publication, activation and merge remain pending. Re-read the live head/preimages and obtain exact operator decisions before considering the live two-file update.
