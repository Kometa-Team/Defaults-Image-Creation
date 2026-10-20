# Overlay exact approval checkpoint

Proposal only. No new visual-policy or staging approval has been recorded.

Production baseline: `222a717e85e077a328ab0687b59441b2850c3124`.

Policy SHA-256 (canonical payload): `77fb3d8525722a0db87e44710e0ba9a1e450e891b83a8cfb1a986566f993d091`.

Complete candidate manifest SHA-256: `53f0379393f6e7a90f928d358a046e6b14296e15aa8546fcb3e1e2f22c106570`.

All 4,122 outputs have an explicit disposition. 4,122 exact Python files are proposed for one draft PR, approximately 14 technical batches. Includes 12 expected additions and 21 case-only renames.

| Exact population | Images |
| --- | ---: |
| edge_resampling_group_proposal | 1,668 |
| individual_exception | 1,433 |
| new_destination_decision | 12 |
| retained_individual_approval | 64 |
| strict_group_proposal | 945 |

## Review

[Compact measured-family review](maintainer-review/review.html) · [All profile/transform groups](focused-review/review.html) · [Complete remaining exceptions](individual-exceptions/review.html) · [Every dimension change, expected addition and case correction](geometry-and-mappings/review.html)

The compact gallery samples measured families and worst cases; it does not claim every exception has been individually inspected. Exact exception membership remains pending explicit maintainer acceptance. The 64 prior exact approvals are preserved without another review requirement.

## Proposed policy and calibration

Both black and white composites retain the original limits: RGB MAE ≤3, p99 ≤32, fraction changed by >16 ≤0.10, global luminance SSIM ≥0.98, region MAE ≤4 and edge MAE ≤6. The strict group additionally requires alpha MAE ≤1.5, identical dimensions and alpha≥16 bounds, alpha mass change ≤1%, no support outside a one-pixel neighborhood, opaque-core RGB/alpha MAE ≤1, opaque-core alpha error ≤16 and protected-interior alpha error ≤1/RGB MAE ≤1.

The separate edge-resampling proposal replaces the global-alpha bound only for its exact measured members: alpha differences must remain within a two-pixel edge band with maximum error 64, while the protected interior, bounds, mass, support and composite limits still pass. Tagged published ICC profiles require separate color-managed exception review; they are not silently waived.

The old screen rejected 38 of 64 accepted examples. Global alpha error and color/filter changes explain these rejections; the retained exact decisions are separate from tolerance qualification. The new rule does not admit every accepted positive. See calibration.json for each positive result. All eight deliberate defects fail both proposed screens; the exact positive control passes. Controls cover lost/faded alpha, displacement, crop, halo, a readability block, interior darkening and a one-pixel interior alpha hole.

## Exact decision required

Approve the policy hash and complete manifest hash above for draft staging, explicitly covering both proposed groups, the exact remaining exception population, the 12 confirmed expected additions and the 21 source-authoritative case-only renames. Retain the existing 64 decisions. This grants no merge or direct-master authorization. The uploader will refuse changed bytes, source context, membership or baseline.

All binary-different eligible outputs are uploaded even when visually equivalent. Only exact SHA-256 matches at the correct filename can be skipped. Every staged file must pass actual remote SHA-256 and Git-blob verification plus a complete tree audit.

## Calibration detail

Retained positives: 64; historical-screen rejections: 38. New strict screen admits 16/64 and the edge screen 46/64. The exact decisions remain valid for positives outside either screen. Failure counts overlap: alpha_mae: 38, changed_gt16: 2, p99: 2, region_mae: 7, rgb_mae: 11.

[Inspect all deliberate controls](negative-controls-review/review.html). Complete exception family/mode/ICC counts are recorded in measured-review-context.json.
