# Default Poster Font Provenance Review

Subsequent action: the restricted Bebas asset has been replaced by official
OFL-licensed Bebas Neue v2.000 after a nine-Playlist comparison. Its unchanged
original notices are bundled in `fonts/licenses/BebasNeue/`. See
[comparison, tradeoffs and final configuration](BEBAS_REPLACEMENT.md).
The original Bebas findings below are retained as historical evidence, not a
claim that the restricted font is still bundled or licensed for redistribution.

Helvetica has subsequently been replaced by approved OFL-licensed Plus Jakarta
Sans Bold 2.071 at fixed 409 points for the 2020s decade and 2020-2029 year
definitions. Its original notices are bundled in `fonts/licenses/PlusJakartaSans/`.
The Liberation trial was rejected and is not bundled. See
[comparison and final configuration](HELVETICA_REPLACEMENT.md). The Helvetica
license and file-health findings below are historical, not active prerequisites.

Reviewed 2026-10-15. This is an evidence audit, not legal clearance. No font was
replaced during the initial provenance-only review. The later authorized
replacements are documented above; no original font was repaired or installed.
No license grants are inferred from a font's filename or embedding flags.

## Outcome

The earlier four generic license warnings now have more precise evidence:

| Bundled asset | Finding | Remaining action |
| --- | --- | --- |
| Bebas-Regular.ttf | Exact match to the author's linked download; custom free-font EULA, not OFL | Permission review for redistribution and private in-memory cmap processing |
| BoecklinsUniverse.ttf | Exact bundled font recovered in the archived official author ZIP with its original 2013 OFL notice | Keep original notices in `fonts/licenses/BoecklinsUniverse/`; no font replacement needed |
| Monoton-Regular.ttf | User-approved unmodified official Google Fonts release, with exact font and original OFL hashes verified | Retain `fonts/licenses/Monoton/OFL.txt`; retired private reference binary is not distributable |
| Helvetica-Bold.ttf | HP version 1.3, proprietary metadata, no bundled license; one-byte outline-table boundary inconsistency diagnosed | Original entitlement/EULA and intended-use confirmation; authorized source file if repair is needed |

The other 13 fonts retain their embedded evidence: 11 SIL OFL declarations and
two Apache declarations. This follow-up has not independently reconstructed their
complete distribution histories. The full family/category/character inventory is
in [the composer audit](PYTHON_COMPOSER.md#font-inventory).

Machine-readable findings and source/license hashes live in
[`font_provenance.json`](font_provenance.json). Inventory generation applies each
record only to its reviewed SHA-256. A changed font does not inherit that record;
the report instead adds a provenance warning. These are reporting fields, not
automatic runtime licensing decisions. Ordinary inventory/tests remain offline.

## Bebas

- File SHA-256: `39d2eb178fdd52b4c350ac6dee3d2090ae5a7c187225b0d161a1473ccbb6320d`.
- Local version 1.100; 17,408 bytes, 86 glyphs; Ryoichi Tsunekawa / Dharma Type.
- The [author's repository](https://github.com/dharmatype/Bebas) explicitly permits
  commercial use and links to [its distribution page](https://www.dafont.com/bebas.font).
- The [linked download](https://dl.dafont.com/dl/?f=bebas) contains a byte-identical
  TTF and `Lisense.txt`, free-font EULA version `2018.03.01.1`.
- The license allows commercial/noncommercial works and raster artwork. It
  prohibits sale or redistribution without permission and also restricts
  modification, derivative work, reverse engineering, and decompilation.
- Archive SHA-256: `ad85b47ecb450d82ac9a63bd3d634912916cb2207249fce955365300858575cf`.
- License-member SHA-256: `d7482f6aba531feb3c2228e2c58c159dc578e8ba286f5681b9a9d2e510aaab06`.

Do not label this font OFL because Bebas Neue/Kai use OFL: they are distinct
releases. Commercial artwork permission is not blanket redistribution permission.
The current Python layout technique creates a private in-memory cmap; have the
licensor confirm that use as well as any binary redistribution/service packaging.
This is a permission question, not a determination that existing use violates the
license. Original sources and rendering behavior were left unchanged.

## Boecklins Universe

### Phase 1 Follow-up, 2026-10-16

The exact bundled binary is now verified. The
[archived official author ZIP, captured 2015-03-21](https://web.archive.org/web/20150321100356id_/http://www.peter-wiegel.de/Fonts/BoecklinsUniverse.zip)
contains a byte-for-byte matching `Boecklins Universe.ttf`, plus the original
2013 `Open Font License.txt` and `OFL-FAQ.txt`. Original notice bytes are retained
unchanged under `fonts/licenses/BoecklinsUniverse/`, including their original
legacy character encoding. No newer license is substituted for this release.

- Archived ZIP SHA-256: `3bb4cce23dc108507683442a9fb8e24013e55995992f5b92bef012681c0887df`.
- Original OFL SHA-256: `2d57569aa55506bb37630d35728754048d3faf961516719d2ee2fd6c6087bbad`.
- Original FAQ SHA-256: `7c140bfe7a997951ebd8f85667c6b921d4e35bc96a2fef3e4c6f606a47aa00e1`.

Keep the existing font with these required notices. Its exact-release OFL grant
supports redistribution subject to its conditions and Reserved Font Name.
No visual change, internal name change or replacement approval is needed.
The local archive and metadata are in
`config/phase1-validation-20261016/font-history/author-2015/`.

Before that archive was recovered, the current official author archive was
downloaded again and compared as a possible alternative. Its hashes are below.
All 11 affected numeric definitions (1900s and 1900-1909) were compared locally
using the same PowerShell/ImageMagick rendering body for both releases. Fitted
point sizes, line breaks and centered ink bounds are unchanged. Maximum RGB MAE
is 0.002995/255; minimum global luminance SSIM is 0.999996.

The newer official `Boecklins Universe.ttf` remains an optional alternative,
not needed to resolve provenance. **Not applied or approved by this task.** Do
not attach its 2018 notice to the existing font as a provenance claim.

Local before/after evidence and exact glyph/kerning measurements:
`config/phase1-validation-20261016/font-candidates-verified/index.html` and
`measurements.json`. The earlier sibling `font-candidates` attempt is marked
invalid because the legacy alias selected the original file; none of its
measurements are used in this recommendation. The corrected run checks the
private resolved font bytes and records any isolated alias redirection.

- File SHA-256: `5f6f6396edee3fa1fe9443258d7463f82e6b2512a03c5102a90295a095339fb5`.
- Local file: 969,084 bytes, 1,670 glyphs, version 1.000 / 2012 initial release,
  copyright 2013 Peter Wiegel; no embedded license fields.
- The [author's family page](https://www.peter-wiegel.de/Boecklin.html) links to
  [the original host's archive](https://www.peter-wiegel.de/Fonts/BoecklinsUniverse.zip).
  The author's [FAQ](https://www.peter-wiegel.de/) also discusses commercial use
  and software distribution, subject to the package's applicable license.
- That archive includes an OFL 1.1 license with a 2018 notice and Reserved Font
  Name, but its font is 771,460 bytes and has a different hash:
  `f337d1e6e75f879f952017341c819d65df5c4b441d9bb188c104c94423832f16`.
- Archive SHA-256: `602945fb203b94b00ada8fcf81f3aa7aa2497fa4d23d77362a6c0bd1c06c6320`.
- `Open Font License.txt` SHA-256: `3b21223952a38b64131e00ee7ddc3f391a83b8746f8ef7d829423f0c2ca514e3`.

The archived 2013 package, not this different current release, establishes the
exact-byte provenance chain for the bundled font. No font file was replaced.

## Monoton

### Phase 1 Follow-up, 2026-10-16

**Approved and applied on 2026-10-16.** The official 373-glyph file is now bundled
under its actual `Monoton-Regular.ttf` filename and unchanged Monoton family name.
Its original OFL notice is in `fonts/licenses/Monoton/OFL.txt`. The production
dependency checksum was updated; no poster definitions or fitting rules changed.

Fresh installed-font verification confirms all 11 PowerShell outputs match the
previous official-candidate SHA-256 values, and all 11 Python outputs are
byte-identical with the old and new fonts. Evidence is in
`config/phase1-validation-20261016/monoton-approved/`. The earlier binary remains
only in private historical validation inputs, not as a distributable asset.

The official Google Fonts history for `ofl/monoton/Monoton-Regular.ttf` points to
initial commit `90abd17b4f97671435798b6147b698aa9087612f`. Current official metadata
links the older source tree at `52f780bc9d197280a9f430574e179a5f233c56b6`.
Its font and OFL were also downloaded and hashed: they match the official
373-glyph release and notice below, not the formerly bundled 371-glyph binary. Neither
establishes provenance for the retired bytes. No inference
of exact-release permission is made from a family-level license or third-party
download page.

The pinned official 373-glyph release and original OFL notice were fetched and
verified. All 11 affected numeric definitions (1970s and 1970-1979) produce
pixel-identical PowerShell posters with that candidate: RGB MAE 0, global SSIM 1,
unchanged fitted sizes, line wrapping and centered ink bounds.

The user approved that exact unmodified official `Monoton-Regular.ttf` with its
original `OFL.txt` copyright and Reserved Font Name notice. Its OFL release may
be redistributed with the required notices; that does not retrospectively
verify the historical different binary.
The same local 22-case report cited above contains these comparisons.

- Retired file SHA-256: `1565b395f454d5c2642d0f411030051e7342fbaf6d5bfc5da5899c47ecd3511e`.
- Retired file: 49,908 bytes, 371 glyphs, version 1.000, FontForge dated
  19-8-2011; copyright Vernon Adams; no embedded license fields.
- [Official Google Fonts metadata](https://raw.githubusercontent.com/google/fonts/main/ofl/monoton/METADATA.pb)
  identifies Vernon Adams, OFL, and the original source repository.
- A [pinned official OFL file](https://raw.githubusercontent.com/google/fonts/90abd17b4f97671435798b6147b698aa9087612f/ofl/monoton/OFL.txt)
  records the Monoton Reserved Font Name. Its SHA-256 is
  `585c6d2da8bcd8ffa651e0016f2e992a6891b625143a46a1dacf00699a817d9a`.
- The official font is 51,604 bytes / 373 glyphs, SHA-256
  `951c4cea65ffede784a7c9672feec5d329a7e1e12216c42d53ecf36c90d04dea`.
  It is now the bundled font. The original source commits
  `61aaa857ea2647b0fdbdae0b667a15c0ca67959b` and
  `2ff5c63ecce2d2d4f30b26806a74f1c2e9bae3c2` were checked as well; neither matches.

The historical release's source remains unverified; no license is inferred for
those retired bytes. The approved official file resolves the active Monoton
provenance gap without changing the tested numeric poster appearance.

## Helvetica: Entitlement and File Health

- File SHA-256: `d19ccd4211e3caaac2c7f1ae544456f5c67cd912e2bdfb1efb6602c090c724ee`.
- The file identifies Hewlett-Packard, version 1.3, copyright 1992-97. A general
  [Monotype license page](https://www.monotype.com/terms-and-conditions) cannot
  establish ownership or service/redistribution rights to this particular binary.
- Its `fsType` is 14 (`0x000E`). Embedding bits do not supply the missing EULA;
  historical OS/2 versions have specific multi-bit interpretation rules. See the
  [OpenType specification](https://learn.microsoft.com/en-us/typography/opentype/spec/os2#fstype).
  No embedding flags were changed or bypassed as a licensing solution.

The FontTools error is reproducible and now precisely localized:

| Observation | Value |
| --- | ---: |
| Glyph count | 385 |
| Declared `glyf` table length | 73,419 bytes |
| Final `loca` offset | 73,420 bytes |
| Difference | One trailing byte |

The next physical byte in the source file is zero. Adding one zero byte only to
an independent in-memory diagnostic outline buffer allows FontTools to parse
all 385 glyphs. This is consistent with a trailing padding/table-length issue,
not proof that an actual glyph outline is missing. FreeType can render the
original font. The existing same-face native-bounds fallback therefore remains;
no padding repair was added to the production renderer and no font was saved.

The technical cause is explained, not used to bypass the entitlement question.
Obtain the original authorized package/EULA and confirmation of intended use.
If a corrected font is needed, obtain an authorized verified copy and compare it
visually before approving replacement. Do not fetch an arbitrary Helvetica copy,
rewrite its embedding flags, or substitute another family without approval.

## Local Linux Possibility

Read-only environment checks found WSL 2 with only the `docker-desktop`
distribution, stopped, and Docker Desktop's `desktop-linux` client context.
The Linux engine is not running. No general-purpose WSL distribution was found.
Nothing was started, installed, pulled, or reconfigured.

Linux validation is possible here through the existing Docker installation once
its Linux engine is started. Use an isolated Python 3.13 Linux container and a
read-only repository mount, with separate writable test/report output. Do not bake
unresolved fonts into a distributable image. This observation is not a Linux test
result; such a run has not happened and is not a mandatory new scope item.

## Evidence and Checks

Local diagnostic metadata is saved under ignored
`config/default-poster-phase1/font-provenance-inspection.json`; the accompanying
one-off inspection script downloads references into memory, checks hashes, and
saves metadata only. Failed lookup attempts are retained rather than hidden.

The 129-case visual report and its original font inventory remain historical
snapshots of the comparison run. This document and `font_provenance.json` supersede
their earlier generic license labels, not their images, measurements, or user
visual acceptance. Newly generated inventories include the updated evidence.

Offline checks:

```powershell
py -3.13 -m unittest discover -s create_defaults/tests -v
git diff --check
```

New regressions cover offline evidence lookup, exact-hash binding, rejection of
stale evidence when a font hash changes, and original Helvetica same-face fallback
without altering its source bytes. No renderer or image-baseline update is needed
for a provenance-only change.

Executed results: all 41 tests passed in 27.488 seconds, including the Arabic
probe; whitespace checks passed. All 31 protected source hashes from the accepted
benchmark remain unchanged, covering fonts, fades, the PowerShell references, and
the native composer/text renderer. No commit, push, or production change occurred.
