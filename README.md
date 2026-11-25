# ChipteeAmz GMC Attribute Auditor V1.0 – safe baseline

## What works today
- Audit uploaded **GMC export TSV ZIP** without credentials: `python engine.py audit-export --zip "biker products_...zip" --limit 5000 --out out`
- Live read-only GMC audit via Merchant API `products.list`, Shopify GraphQL `nodes(ids:...)`, verified Shopify native `descriptionHtml`.
- Exports `audit.csv`, `candidates_review.csv` and `summary.json`. No writing to GMC by default.
- Separately guarded `push-reviewed` subcommand uses a verified **supplemental API source only**, requires `approved=yes`, `source=Shopify_verified`, explicit confirmation string, and separate review. **Do not use it until rules and IDs are tested in GMC.**

## Important limits of V1
1. This is a conservative **candidate extraction** system, **not a validated AI vision classifier**. Text mentions of colors can refer to logos or artwork rather than fabric; candidates need QA. The `confidence=candidate_review` flag explicitly prohibits treating rows as automatically approved.
2. Shopify is the source of truth. Export-only audit labels `GMC_export_description_(verify_against_Shopify)` because GMC processed description may differ; it is useful for diagnosing gaps, not safe for direct upload.
3. Shopify `nodes` queries only the first 100 variants per product. Products with more than 100 variants need paginated bulk operation before large-scale deployment.
4. The current code handles offer IDs matching `shopify_US_<product_id>_<variant_id>`. Other IDs are left unresolved and should be audited separately. It does not manufacture IDs.
5. Sample run limit defaults to 500. Scale to millions only after checkpointing, retries, incremental processing, deduplication and database persistence are added.
6. **Never** delete the GMC `One Color` rule globally before testing source priority. This system does not modify any rules.
7. Material parsing is conservative but not a replacement for specific variant fabric specification. EasySlide is NOT ingested in V1.
8. Product descriptions are NEVER overwritten. The optional uploader sends only color, pattern, material.

## Configure read-only online audit
1. Create a private GitHub repo. Upload all project files (including `.github/workflows/audit.yml`).
2. In Google Cloud enable Merchant API; create a service account and grant it access to your Merchant Center account. Store the service-account JSON as `MERCHANT_SERVICE_ACCOUNT_JSON` GitHub secret. **Do not send credentials over chat.**
3. In Shopify create an app with `read_products` Admin API permission; store token as `SHOPIFY_ADMIN_TOKEN` secret.
4. GitHub repo secrets: `GMC_ACCOUNT_ID` (Merchant Center ID), `SHOPIFY_SHOP_DOMAIN` (`premiumqualityblanket.myshopify.com`), plus the two above.
5. Actions > GMC Attributes Read-Only Audit > Run workflow. It audits max 500 items; examine artifacts and confirm extracted descriptions match Shopify.
6. After QA and mapping tests, raise `--limit`, add persistent checkpoint/full inventory matching, and run control group for GMC source priorities.

## Optional guarded upload – NOT enabled by the scheduled workflow
Require `GMC_SUPPLEMENTAL_DATASOURCE=accounts/<ID>/dataSources/<ID>` referencing a **supplemental API** data source linked to Simprosys primary source. Build a separately approved CSV from candidate rows and add columns `approved` and `source` with values `yes`, `Shopify_verified` only after QA. The importer replaces **all attributes in an existing supplemental item input** with supplied attributes; therefore do not use it for partial changes without merging the prior supplemental attributes first.

`python engine.py push-reviewed --csv reviewed.csv --confirm I_UNDERSTAND_THIS_WRITES_TO_GMC`

## Official docs
- https://developers.google.com/merchant/api/guides/products/add-manage
- https://developers.google.com/merchant/api/guides/data-sources/api-sources
- https://developers.google.com/merchant/api/reference/rest/products_v1/accounts.products/list
- https://shopify.dev/docs/api/admin-graphql

## GitHub first-run safeguard
- Workflow is manually triggered (`workflow_dispatch`) in this repository-ready package. Enable the daily cron only after API access and mapping QA succeed.
- Do not upload `merchant-credentials.json`, downloaded key files, or any `.env` containing secrets.
