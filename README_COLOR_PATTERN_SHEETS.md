# ChipteeAmz — Color / Pattern Google Sheets Sync (READ_ONLY)

## What was changed

Preserves all existing `Pending_Material`, `Approved_Rules`, and `History` tabs and material workflow. The **same** online Google Sheet receives four automatically-created tabs:

- `Pending_Color`: one row per exact offer/variant (ITEM). Employees confirm **actual item/garment color**. Design artwork color must not be confused with garment color.
- `Pending_Pattern`: one row per verified Shopify product (PRODUCT). Employees choose the actual design pattern or mark `NOT_APPLICABLE` when no relevant pattern exists.
- `Approved_Attributes`: permanent durable approved rules; do not delete. They continue to apply to future audit runs.
- `Attribute_History`: immutable-style append-only decision log for audit trail.

### Priority and evidence

1. Existing GMC real value or already-approved audited value is retained. `One color` is treated as missing.
2. The existing audit handles strong Shopify Variant Color and explicit Title Pattern or Color signals.
3. New workflow re-fetches verified Shopify Product Title, Product Type, Description and exact Variant Color via Shopify Admin GraphQL (up to **500 offers per run**, configurable). The fetched evidence is cached into `out/attribute_shopify_evidence.csv`.
4. If exact verified Shopify Variant Color is available, auto-approve that **exact shade** (not a palette inferred from artwork).
5. If no verified answer, create employee queue rows **only after successful Shopify re-fetch**. Unchecked rows stay backlogged, not incorrectly tagged as missing after checking Description. Optional candidate from product Title/Description is shown for staff review but never silently approved.
6. `Pending_Pattern` supports `status=NOT_APPLICABLE` to record that this product has no applicable pattern. This avoids requeueing forever, but does **not** send a placeholder Pattern to GMC.
7. Staff input: `confirmed_value` and `status=APPROVE`; or for Pattern only `status=NOT_APPLICABLE` (no value needed). All ID and provenance columns must not change.
8. The next run validates immutable IDs, commits to Approved_Attributes + History first, updates audited Color/Pattern, removes confirmed entries from Pending. Staff rule is automatically reapplied on every future run, even if GitHub cache expires.

No item has GMC/Shopify writes. Existing GMC values are never overwritten. Pattern decisions are product-scoped; Color decisions are item/variant-scoped. Do not extrapolate a review of `Blue Bowling Shirt` to all bowling shirts.

## Deploy

1. Existing shared spreadsheet secret `MATERIAL_SHEET_ID` and existing `MERCHANT_SERVICE_ACCOUNT_JSON` are reused. **No new secrets required** if existing Material Sheet works and Shopify secrets are present.
2. Upload this folder's files and commit to `chipteeamz-gmc-attributes` repository.
3. In GitHub Actions, run **GMC Attributes Employee Google Sheets Sync (Read Only)**. It restores existing audit, syncs Material, then re-fetches up to 500 unknown Color/Pattern offers, auto-approves verified Color Variant options, and writes the four new tabs.
4. Subsequent daily runs continue with further unknowns and immediately apply employees' confirmations. The same synchronization runs after each full GMC audit; existing checkpoint retained.
5. Download `attribute_sheet_sync_summary.json` and `attribute_shopify_refetch_summary.json` from artifacts to check progress.

Notes: Re-fetch happens in **batches** to avoid API throttling; unverified Shopify items and product types outside the original audit are not inferred. Description Pattern candidates need staff review. When pattern is `NOT_APPLICABLE`, keep the missing GMC attribute unchanged. Do not turn on GMC Write automatically.

## Tested offline

On `audit(10).csv` (4,500 offers): 1,260 Color offers and 3,945 Pattern offers are missing approved values among Shopify-verified rows. Pattern queue groups multiple variants of the same product; **up to 3,842 unique product rows** would eventually require review if Shopify re-fetch finds no usable explicit evidence. These are *backlog counts*, not proof that all have already been checked against current Shopify descriptions. Actual first-run queue sizes depend on Shopify re-fetch results and may be smaller. Tests pass without any external API call; the user must execute GitHub workflow to sync online.
