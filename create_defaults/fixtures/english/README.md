# English Comparison Fixture

Unmodified `defaults/en.yml` and original MIT `LICENSE` from
[Kometa-Team/Translations](https://github.com/Kometa-Team/Translations/tree/a7bddf45d0fb2cc37c794af05d5fb807880c9a80),
commit `a7bddf45d0fb2cc37c794af05d5fb807880c9a80`.

- `en.yml` SHA-256: `5fe987030981e83c35fab37192240afd596febf7f6f4d205a9c024a272ff390f`.
- `LICENSE` SHA-256: `ec4e791bbefa93c524a162a29c1ccb7cefb182225c0372aa913182874afaccb5`.

This is an offline fallback for fixture extraction and review tests, byte-identical
to the English cache used for the comparisons. A supplied local
`@translations/en.yml` takes precedence and its actual hash is recorded in reports.
No production translation download, definition, or selection behavior is changed.
Scoped Git attributes retain upstream whitespace and line endings unchanged;
the fixture and original license hashes are checked by the offline tests.
