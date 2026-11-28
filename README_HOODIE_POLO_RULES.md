# GMC V1.3.2 – Hoodie Description & Polo Title Rules

## New rules (user confirmed 2026-11-27)

- When Shopify **Variant Style** is absent, inspect stored product title.
- Unqualified **Polo** title -> `Men Short sleeve polo shirt` -> `100% polyester` (material master); explicit long sleeves, sleeveless or zip modifiers are NOT overridden.
- Unqualified **Hoodie** title -> Shopify native **Default Product Description** must be fetched and Product/Variant IDs reverified via Shopify API.
  - If nonempty, verified Description contains whole word `cotton` (case-insensitive): `Hoodie` -> `Cotton`.
  - If nonempty, verified Description lacks whole word `cotton`: `220g air layer Hoodie` -> `100% polyester`.
  - If description missing, failed API request, different variant/product: keep `REVIEW_MISSING_STYLE`.
- Never infer 'no cotton' just because `audit.csv` has no stored Description. A missing value is not an absence of cotton.
- Never touch existing GMC Material, or anything in GMC, Shopify or Simprosys. This is READ_ONLY.
- Other ambiguous descriptions e.g. generic Shirt/Jersey remain to review.

## Recheck EXACT existing GMC 4,500 item scan without advancing checkpoint

1. Upload all files into same GitHub repository root.
2. Actions -> **GMC Recheck Existing Styles (No New Page)** -> Run workflow.
3. Workflow restores latest `out/` snapshot, re-fetches only missing-style Hoodie descriptions from Shopify via `SHOPIFY_ADMIN_TOKEN`, re-evaluates old audit, then exports reports.
4. Download artifact `hoodie-polo-style-recheck-<run id>`.
5. Inspect `missing_style_summary.json`, `missing_style_after_hoodie_polo.csv`, `style_description_evidence.csv` and `summary.json`.
6. This workflow does not call Merchant API and does not modify `out/checkpoint.json`.

## Normal GMC Audit

Existing `.github/workflows/audit.yml` also invokes `refresh_hoodie_descriptions.py` after audit page is read and before unified re-enrichment, so any new Hoodie missing Style is handled by exact Shopify description on future scans.

## Offline evaluation

`python unified_rules.py --out ./existing_audit_folder`
`python export_pending_styles.py --out ./existing_audit_folder`

Without Shopify API secrets and fresh descriptions, the offline run only resolves the 1 generic Polo (60 -> 59 pending styles; 28 Hoodie remain waiting for Shopify; 30 Shirt and 1 Jersey remain unresolved). Do NOT interpret the 28 pending as a rule failure: they require description reads.

## Other protections

- Recheck fetch stores classification only (`YES`, `NO`, `UNKNOWN`), not product description HTML.
- User's master and aliases remain unchanged.
- No GMC Write API path is present.
- Developer-approved color/pattern logic and page checkpoint remain unchanged.
