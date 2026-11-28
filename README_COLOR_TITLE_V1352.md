# Color title and all-over-print extension (offline-safe)

- Preserves all previously approved Color, Material, Pattern.
- Adds `color_title_rules.py` to the existing Color/Pattern sync, **not** the GMC writer.
- Reads verified GMC/Shopify Title and item data; does not treat `Black Labrador` as black garment.
- A trailing selected color in a verified GMC variant Title (e.g. `/ Blue`) can be accepted.
- A color immediately modifying a named garment/design (e.g. `Blue Flame Bowling Shirt`) is a candidate only in sufficiently clear context.
- AOP/gradient uses a **combined color palette** when 2-3 distinct, explicit colors are named; never guesses the primary color from multiple colors.
- Avoids overwriting existing Color or accepting mismatched Shopify/GMC product titles.
- Does not replace verified variant Color. Missing or unverified product matches remain for review.
- Emits `color_title_rule_decisions.csv` and `auto_verified_title_colors` in sync summary.
- Remains READ_ONLY; no Merchant Center update, Shopify write or Google Sheets write in offline recheck.

## Validated offline against latest supplied audit
`4,500` items; existing approved Color `3,242`; new Title-qualified approved `1`;
new approved `3,243`; remaining `1,257` (`27.93%`).

Only **one newly eligible** entry means the other missing Color items do not meet the narrow unambiguous Title rule in the available data. Expand source coverage / visual audit rather than guess.

The recheck artifacts in the separate ZIP are created offline, do not mutate GitHub checkpoint.
