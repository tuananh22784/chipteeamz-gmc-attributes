# ChipteeAmz GMC Attribute Audit V1.2

**READ-ONLY – absolutely no GMC writes.** Simprosys main feed, Shopify Default Description and GMC `One Color` Attribute Rule are unchanged. EasySlide not used in V1.2. This is an auditable **candidate generator**, not an automated correction system.

## Deploy into existing GitHub repository

Unzip package and upload contents of `chipteeamz_gmc_v1_2` to the **repository root** (replace `engine.py`, `live.py`, `requirements.txt`, `.github/workflows/audit.yml`, `README.md`, `tests/test_engine.py`). Keep existing secrets:

- `GMC_ACCOUNT_ID`
- `SHOPIFY_SHOP_DOMAIN` = `premiumqualityblanket.myshopify.com`
- `SHOPIFY_ADMIN_TOKEN` (read_products)
- `MERCHANT_SERVICE_ACCOUNT_JSON`

In GitHub Actions, choose **GMC Attributes V1.2 Read-Only Audit**. Start with `page_size=500`, `max_pages=1`. Then test `max_pages=5` and review run times. **Do not run `max_pages=0` on the full store before load/performance QA.**

## Files in the workflow artifact

- `audit.csv`: all processed offers, verified Shopify status, variant options, current fields, candidates and snippets
- `ready_for_qa.csv`: verified offers with at least one candidate. **NOT APPROVED**.
- `candidates_review.csv`: all offers with candidates, equivalent to ready_for_qa for live runs
- `needs_review.csv`: missing fields but no verified candidates or failed ID match
- `auto_fix_eligible.csv`: **header only**, intentionally no auto-approval
- `summary.json`: counts, pages, completed flag
- `checkpoint.json`: next Merchant API page token and account, intended for explicit resume only; no secrets but may expire

## Scan pagination and resuming

A single workflow run pages through up to `max_pages` Merchant API pages, writing reports and checkpoint after every page. `max_pages=0` processes all pages until completion or GitHub job timeout. To resume in a **new run**, restore the previous artifact's **entire `out/` directory** (including `audit.csv`, `summary.json`, `checkpoint.json`) into the runner, and run:

```bash
python engine.py audit-live --out out --page-size 500 --max-pages 5 --resume
```

The bundled GitHub workflow **does not automatically restore artifacts between separate runs**. Thus, each ordinary click of Run workflow without restoration **starts at page 1**. Do not interpret separate default runs as coverage of the entire GMC catalog. If tokens expire, restart full scan from page 1. Consider a persistent store/queue for >1m offers in a later version.

## Correctness improvements vs V1.1

1. Exact Shopify variant fetched via ProductVariant node, not `variants(first: 100)`; verify it actually belongs to parsed Shopify Product ID.
2. Persist Shopify variant options and non-color/non-size style so material decisions can be reviewed for the correct subtype.
3. Explicit material and source snippets, conservative blocks for mixed/variant-dependent descriptions; style confirmation required for any material suggestion on apparel variants.
4. `READY_FOR_QA` separate from `NEEDS_REVIEW`. **Neither means safe for auto-write.**
5. Page-size/max-pages control, page-level output, checkpoint; safety cap by operator.
6. `One Color` remains a placeholder to flag; the existing GMC rule is untouched.

## Known limitations / next gate

- Pattern & multi-color names are proposals, not image-confirmed actual garment colors.
- Shopify description can be generic across variants; explicit material evidence is not guaranteed variant-specific.
- Legacy non-`shopify_US_product_variant` offer IDs remain `UNMATCHED_OFFER_ID` (no guessing).
- Shopify GraphQL product variant lookup may be rate-limited; huge scans need Bulk API/queue and incremental workflow in V1.3.
- The Merchant API page token is an opaque cursor and may expire. Restore *all* files if resuming; a token without prior audit output loses prior rows.
- Do not commit files containing customer or confidential details, any access key, or the Merchant Service Account JSON.

## Local tests

```bash
python -m unittest discover -s tests -v
python engine.py audit-export --zip your-gmc-export.zip --limit 500 --out out
```

Acceptance gate before any writes: independent human review of representative combinations (niche, subtype, color, variant), ID 100% matched, explicit pattern/material evidence, safe rule precedence versus `One Color`, dedicated rollback plan.
