# ChipteeAmz GMC Attribute Auto-Audit V1.1

**READ ONLY. No Merchant API write code is shipped in V1.1.** Keep Simprosys as the primary feed; Shopify default description is authoritative when matched. Does not fetch EasySlide.

## Deploy (replace V1 files at repository root)
1. Download ZIP and extract it **before** uploading. Upload `.github/workflows/audit.yml`, `engine.py`, `live.py`, `requirements.txt`, and `tests/test_engine.py` to the same repository root as your existing V1 files. Delete or disable old V1 workflow `audit.yml` if necessary (the same path overwrites it). Do not upload the enclosing ZIP as a lone file.
2. Keep existing GitHub Secrets **unchanged**: `GMC_ACCOUNT_ID`, `SHOPIFY_SHOP_DOMAIN`, `SHOPIFY_ADMIN_TOKEN`, `MERCHANT_SERVICE_ACCOUNT_JSON`.
3. GitHub → Actions → **GMC Attributes V1.1 Read-Only Audit** → Run workflow. Start with `limit=500`.
4. Under workflow artifacts, download `gmc-attributes-v1-1-audit`; inspect `summary.json`, `audit.csv`, `candidates_review.csv`, `needs_review.csv`, `auto_fix_eligible.csv`.

## QA safeguards
- `SHOPIFY_VERIFIED` means **the Shopify product AND the exact variant ID** from the offer ID were found. Otherwise status is `UNMATCHED_OFFER_ID`, `SHOPIFY_NOT_FOUND`, `VARIANT_NOT_FOUND`, or `VARIANT_NOT_FOUND_OR_UNPAGINATED`.
- `description_source` claims Shopify only when `SHOPIFY_VERIFIED`. Other cases use `GMC_processed_description_or_unknown`. The extractor **does not use unverified description to propose materials**.
- `color_evidence`, `pattern_evidence`, `material_evidence` include short source snippets. Color extraction prefers Shopify `Color` option, then product title; compound colors such as Navy Blue are handled first.
- Pattern extraction uses product title or explicitly labeled pattern statement only, **not generic descriptions**. Multiple patterns and flag/stripe ambiguity remain for review.
- Material extraction only accepts explicit single material composition, and rejects multiple percentages/blends or variant-dependent examples. Never infer composition from sport/niche.
- **All** proposed values are `NEEDS_REVIEW` in V1.1; `auto_fix_eligible.csv` deliberately has headers but no rows. There is **no auto-fix/upload command**. Auto-approval requires a later validation policy with proven precision.
- Legacy non-Shopify offer IDs are not mapped from partial numbers or guessed IDs.
- Only the **first 100 Shopify variant nodes** are returned; products with more variants may be marked `VARIANT_NOT_FOUND_OR_UNPAGINATED`. Extend pagination before full-store scanning.
- Run only small sample first. `products.list` at GMC scale requires persistent checkpoints, quota management, scheduling and change tracking (not implemented in V1.1).
- Audit reports include customer-facing product titles; artifacts retention configured to 7 days. Never print credentials or JSON key to logs.

## What should improve compared to V1
- Honest Shopify match status in every row (the prior report incorrectly labeled all descriptions `Shopify_default_description_API`).
- Fewer false Pattern candidates from generic descriptions and compound Color duplicates.
- Material proposals require explicit compositions, with evidence.
- No silent auto-fix, no changes to `One Color` GMC rule, GMC product data, Shopify descriptions or Simprosys.

## Local verification
```bash
python -m unittest discover -s tests -v
python engine.py audit-export --zip "biker products_2026-11-19_05-23-03.zip" --limit 500 --out out
```

Next milestone: use 500-item QA to establish verified extraction accuracy and item/variant mapping coverage, then implement safer incremental scanning and controlled write-back in V1.2.
