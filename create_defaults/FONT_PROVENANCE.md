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
| BoecklinsUniverse.ttf | Author publishes the family under OFL; current archive is a different release | Recover the bundled release's original package/license or obtain confirmation covering its hash |
| Monoton-Regular.ttf | Official Google Fonts OFL evidence; original official releases checked do not match this binary | Recover authoritative provenance for the bundled 371-glyph release |
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

Family-level OFL evidence is now established. It is not an exact-byte provenance
chain for the earlier bundled release. Retain that distinction until its original
package is recovered or permission covering the reviewed hash is confirmed.
Do not silently replace the bundled font with the author's current version or
attach the 2018 notice as proof that the older bytes matched that archive.

## Monoton

- File SHA-256: `1565b395f454d5c2642d0f411030051e7342fbaf6d5bfc5da5899c47ecd3511e`.
- Local file: 49,908 bytes, 371 glyphs, version 1.000, FontForge dated
  19-8-2011; copyright Vernon Adams; no embedded license fields.
- [Official Google Fonts metadata](https://raw.githubusercontent.com/google/fonts/main/ofl/monoton/METADATA.pb)
  identifies Vernon Adams, OFL, and the original source repository.
- A [pinned official OFL file](https://raw.githubusercontent.com/google/fonts/90abd17b4f97671435798b6147b698aa9087612f/ofl/monoton/OFL.txt)
  records the Monoton Reserved Font Name. Its SHA-256 is
  `585c6d2da8bcd8ffa651e0016f2e992a6891b625143a46a1dacf00699a817d9a`.
- The official font is 51,604 bytes / 373 glyphs, SHA-256
  `951c4cea65ffede784a7c9672feec5d329a7e1e12216c42d53ecf36c90d04dea`.
  It is not the bundled font. The original source commits
  `61aaa857ea2647b0fdbdae0b667a15c0ca67959b` and
  `2ff5c63ecce2d2d4f30b26806a74f1c2e9bae3c2` were checked as well; neither matches.

OFL family evidence is strong, but this audit does not certify where the different
bundled release originated. Retain the exact-release qualification and obtain its
original package/license. No newer font was substituted to make the audit pass.

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
