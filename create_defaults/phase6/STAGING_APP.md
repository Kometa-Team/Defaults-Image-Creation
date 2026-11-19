# Local Playlist staging flow

This loopback-only prototype has separate Add, Replace and Remove contributor forms. Add accepts a title, style and either a mapped logo or a local PNG with no mapping. Replace starts from the catalog, shows the current poster and prefills available recorded settings; the contributor can reuse its logo or upload a new one. Remove needs only a catalog selection and reason. The existing production Python renderer generates Add/Replace previews. The maintainer sees current/proposed replacements side by side, the exact JPEG/hash, catalog change and required checks. Staging rereads file and catalog postconditions. No existing directory can be adopted as a destination.

Pilot presets retain the eight approved additions, X-Men/Clone Wars and two disposable style fixtures. Custom posters require no preexisting logo mapping. Uploads are decoded on the server as single-frame PNGs, limited to 2 MiB / 40 million pixels, with nonempty visible alpha; malformed, animated, oversized and empty-alpha inputs fail. Only immutable SHA-256-named PNGs under the owned staging root are passed to the renderer. Filenames never select filesystem paths. Shared mapped and uploaded source logos are retained on removal. The owned catalog remains a browser fixture; native historical UPDATE/restoration and real authentication/authority stay separate.

## Run locally

From a clean committed checkout with the existing Python dependencies:

```text
python -B -m create_defaults.phase6.staging_app --state config/playlist-browser-review-1 --port 8765 --expected-head <FULL_COMMIT_SHA>
```

Open `http://127.0.0.1:8765`. The app prints the path to `fixture-access.json`, containing two generated local fixture access codes. Use separate browser profiles/windows for contributor and maintainer (ordinary/incognito works). The destination, `catalog.json` and `staging-receipts.json` stay under the new state directory. A restart needs a new directory so earlier evidence remains intact.

1. **Contributor Add:** select **Add a poster / add back**, enter a title, choose a style, then either use the mapped-logo picker or choose **Local logo file** and a PNG. Enter the background and any style-required caption; **Generate preview**, inspect, then **Submit generated preview**. A custom title and valid unmapped logo work without a catalog mapping. Optional pilot presets prefill the approved eight or Disposable Playlist/Franchise inputs.
2. **Maintainer:** sign in separately, reload, inspect the exact JPEG/hash, expand **Catalog change**, review every required check, click **Approve exact render and change**, then **Write to staging and verify**. The receipt records the file hash and exact catalog entry. Approval is bound to both image bytes and catalog pre/postimages, not just a poster hash.
3. **Replace:** select **Replace a poster**, choose an active catalog entry and inspect its current image. Available recorded style/logo/background/caption are prefilled. Reuse the recorded logo or choose a local PNG, generate and submit. Identity and destination come from the catalog and cannot be changed by this form. The maintainer compares current/proposed images side by side. Historical preimages use the recorded legacy layout; for the exact approved X-Men/Clone Wars regression select `playlist-contained-v1` with their approved inputs. Deliberately changed replacement inputs require new visual approval of the exact new JPEG; their earlier visual approval is not carried forward.
4. **Failed check:** change an approved main Add preset's background to `#123456`, generate and submit it. Reference mismatch disables approval and the server rejects approval. Regenerate with the approved inputs for a passing request; the failed request stays in the evidence. Every new render starts without an approval, including byte-identical replacements.
5. **Removal/add-back:** first stage Disposable Playlist. Maintainer clicks **Attach active reference**; contributor selects **Request removal**, chooses that catalog poster and enters a reason. No title, style, logo or render settings are requested. Missing legacy render metadata is allowed when identity/path/file are exact. Inspect the current image, file hash, reason, catalog retirement and active references: approval is blocked. Release the reference, submit a fresh removal and approve/stage it. The file is absent and the catalog retired; logos remain. Select Add and its retained disposable preset (or enter the same title) to restore its original fixture identity/path. A newer replacement invalidates an already approved removal, including when it retains the same destination. Native registry tombstone reuse remains blocked.
6. **Second supported style:** choose Disposable Franchise, select its existing Franchise logo-only style and the supplied Franchise logo. The caption input disappears; generation uses the existing unbounded renderer preset without introducing text/compositing changes. Submit, approve and stage it normally.

The app binds to loopback and accepts only same-origin bounded JSON writes. Roles, HttpOnly SameSite cookies and CSRF tokens apply. Add/Replace approval binds the exact generated JPEG and catalog change. Removal approval binds the reason, exact catalog entry/revision and current destination-file SHA-256; render metadata is unnecessary. Missing/changed/linked objects, create collisions, stale preimages, changed inputs and unrelated destination edits fail closed. Source verification runs before/after generation and staging against the supplied HEAD; render assets are freshly checked across calls. A failed closing proof restores prior file/catalog state. Fixture approval grants no live authority.

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
