# M6 category coverage and package pins

Review candidate only; no exact contract approvals or production activation.

Implementation inventory SHA-256: `926de31d1df4ee90e911c4e91df81ee3ca914f5179df784ff3d41e9b716ada2a`.

All package versions are **1.0.0**. Category and selector names coincide. Stable package IDs are `defaults.<lowercase selector>.poster`, except `defaults.overlays.overlay`.

The 22 selectors comprise 21 poster categories and Overlays. Playlist remains the exact M3 package; 21 packages are added. There are 278 closed design variants, including 18 overlay branch variants with both sizes.

| Category / selector | Outputs | Closed variants | Policy / special source classes | Uses with accepted exceptions |
| --- | ---: | ---: | --- | ---: |
| Aspect | 9 | 2 | NOT_APPLICABLE, WHITE_ONLY | 9 |
| AudioLanguage | 188 | 8 | NOT_APPLICABLE | 188 |
| Awards | 4847 | 35 | WHITE_ONLY | 4847 |
| Based | 4 | 1 | NOT_APPLICABLE | 4 |
| Chart | 1182 | 36 | BOTH_REQUIRED | 1182 |
| ContentRating | 72 | 3 | NOT_APPLICABLE, WHITE_ONLY | 72 |
| Country | 608 | 56 | BOTH_REQUIRED, NOT_APPLICABLE | 608 |
| Decade | 31 | 17 | NOT_APPLICABLE, SPECIAL | 31 |
| Franchise | 118 | 2 | WHITE_ONLY | 118 |
| Genre | 275 | 28 | NOT_APPLICABLE, WHITE_ONLY | 275 |
| Network | 568 | 10 | BOTH_REQUIRED, NOT_APPLICABLE | 568 |
| Playlist | 9 | 1 | WHITE_ONLY | 9 |
| Resolution | 15 | 2 | NOT_APPLICABLE, WHITE_ONLY | 15 |
| Seasonal | 23 | 6 | WHITE_ONLY | 23 |
| Separators | 749 | 3 | SPECIAL, WHITE_ONLY | 705 |
| Streaming | 256 | 12 | BOTH_REQUIRED | 256 |
| Studio | 488 | 6 | NOT_APPLICABLE, SOURCE_PRESERVING | 488 |
| SubtitleLanguage | 188 | 8 | NOT_APPLICABLE | 188 |
| Universe | 20 | 3 | WHITE_ONLY | 20 |
| VideoFormat | 6 | 2 | SOURCE_PRESERVING | 6 |
| Year | 301 | 19 | NOT_APPLICABLE, SPECIAL | 301 |
| Overlays | 4122 | 18 | SOURCE_PRESERVING | 4122 |

## Exact package and membership hashes

The complete source/path/exception/companion mappings are in the corresponding `bulk/contracts/categories/data/rules/<lowercase selector>-v1.json` files. Every member pins its complete M2 record and effective-definition/job context.

| Selector | Contract SHA-256 | Rules / membership SHA-256 |
| --- | --- | --- |
| Aspect | `fc14d583c50d28e4f616c2aa853acdfcebdf1a4a9626500912791a8e3baa2b08` | `107bf773692b5794e58f527d49769e5381e1c83234924b915b3586c33816860f` |
| AudioLanguage | `bb3c4cb548bcf2cb1f5c4d5a0d1b310ef55509fa99dceed6c835bd8ddbc8072c` | `76648f8cac0e2e6305afa802cded8e953cc17b54a1e2e1cc4733f662f18306fe` |
| Awards | `7c0dd7e17e0c2053548d168359f3e6a676412ac8864577c191851013b407b1b9` | `3c96ef1d868785952ee296fe366d4b5982fece8cfa5c6ea668d4710f00ec6ece` |
| Based | `2fbcdbcfa7ead20213143fecfff7a39ab5ef3b86214f54eaf67225f9cc2f5103` | `a4f9ea7733e796236b0e14c97048f1f7152c1f34bf2d5d625d9160920124ca05` |
| Chart | `31e51f40fedc6c7b713bc8778c37fe4f2261b6190e7ff68b36088dbb08f0141f` | `f73656528575197bc7316e1e815b625a8ff04a46318e9e0cb0b0aa9f6d6f8de8` |
| ContentRating | `fb4494c27910daf618ae9c58e7df8a867a0836e4a1b40f7c64b46cff6ffbaef3` | `83377fe90d2c66045d478b967bd4e8a1d5117fc4bf0066aa0ebbf807a416334d` |
| Country | `bcfc3498f96b8412b016c1c93a600448fe591c485a5994f52798f14bb3ec99cd` | `3b442f0e58acc17202d6e08cdb810c6fbabdbc6fe86c554f6b032ada7e1f8f4b` |
| Decade | `e215dc4c5a41ea1fb51415f9ddf841033a066b2e3472ea648e28bffb8dedea8c` | `deedb60dfd6585ea297ffc3f9b31dac35b5d18110051f3d34caec993f3c73571` |
| Franchise | `3f95c0f4c80df9aba2934c5e1e4e50065bdd894e9202ec2f0a3aa5f80d19bf1b` | `30fcfcc089b4adf1fd5e67d2357cb6637e26cfc424e6d9434f25ab5dc0f7c0a0` |
| Genre | `ad2bb267b9fb0b0452fd92da9630f323f9ca86c80c169b930fbf8387d96a778a` | `13186ecaddf49c06741ddf70501ecf5985e0c07e3e71fdc99dbbd6d714deefd7` |
| Network | `fd090570f6b7976e064660dec91f9f8207980cbb9e6e7d6e2aeafa3cc7b05b0c` | `9ec1d48a4a39d93b3f1e00b43c41ad4c5fa5db574d2add3048ceebae90e90dab` |
| Playlist | `5047d834ecd3f8e5a0ed76ae24760b6947ae6b83e95198ce602e1715e445016b` | `f8dabde54206a85aee1a2eb769dc066d0de47b7792bdd7a34c22bde145590932` |
| Resolution | `4475c9bb450380395a2a2e982fcf72cb33f8453fe3d4665ea8a171e9f6570865` | `d5fe33a37e12cc75a3ab586e92311fe4546b32d168ab1710550c44f012a35298` |
| Seasonal | `1124fecbde06c2c78c8fba9772d16de65d9cc70ae0d29a8f203b931f2e2507c7` | `d5abaf859796e02c4c4ce6ad7caddae9f5c23c5d7dbc8f60625ca0b43791cbca` |
| Separators | `f846c148539eebf0bcdad47cb9b2c2e68c3e7517c8566b12acf40dc7426e3331` | `3fe151a12839e3dfb14fe3185bd32d4429c672200aa5ac67a15d43f7cefb8206` |
| Streaming | `89869d979fa4236590f9195eb216838feab1a63662fb35a78cc49a9c863566de` | `8dbacbad75d63f508a7e9b4287a68f3adbf8619c59f3dfafadf277ab76eb6ab4` |
| Studio | `d675c3b036fc8a44741552d8c8cf32587b986aa3302343f666da510ea83e35fd` | `b6e558af362322977052ac60d0c71eea38bd456627d25bc295c48287f2e39ca9` |
| SubtitleLanguage | `dc899a0611b93ea461fb5af6ef79abf2fa6d7fab27c41bf1fb17c5b83bce9e45` | `ccd4ccda98955292a4531a18e599622970ae907323d532a110c5d1b6b95adfdd` |
| Universe | `e85fd297c7e3d537134de23221919d20ff7a2500ca3409c650d8448962b6809c` | `08c9c9a55ec0aca9aef8af4ff2bcea3013eb4e2eb5c6bd8fc9ef0fd1ff782aa3` |
| VideoFormat | `c872e26f91424b8eb87f7f48bac8d741eac5d479f6a61dadec01951e06c97c4f` | `e10d8ce292153156962292cce0187c06575e4f8b36a2e00174ee665ad207f962` |
| Year | `9536beb851ef832f64493e7467f544db9ad77b07234f9f5dd53613bdb6fc5926` | `0b7e5b818c9c332f9571a2997438332318ae9c9a20fba6c15f474b4c09c3d7c8` |
| Overlays | `b79d5aa935a349137718109adb56dbc4a67b7bc760fc3917eccba595cb5fa551` | `b3d25b2c4286ad7d7a0afa0c6710218afd38952863bdea1a5a26e26a324ec0ae` |

Public membership is 14,077: 9,955 posters and 4,122 overlays. The two remaining records are private Awards intermediates. Compatibility outcomes and receipt accounting are recorded separately in [the M6 report](PHASE2_M6_IMPLEMENTATION.md); package existence is not evidence of approval.
