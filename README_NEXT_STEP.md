# Next step: complete Shopify description evidence re-fetch (bounded batches)

This is an operational update only. The Color, Pattern (V1.3.5.4) and Material rules remain unchanged. Google Merchant Center writes remain disabled.

## Workflow
GitHub Actions > **GMC Attributes Employee Google Sheets Sync (Read Only)** > **Run workflow**.

- `refetch_batches = 1` (default, also used by schedule): fetch at most 500 eligible item rows.
- `refetch_batches = 2`: fetch at most 1,000 eligible item rows.
- `refetch_batches = 3`: fetch at most 1,500 eligible item rows. Recommended for the initial catch-up if GitHub Actions and Shopify API latency permit.

The program sequentially re-fetches Shopify Product/Variant title, product type, description and selected options into `out/attribute_shopify_evidence.csv`; then runs the existing Color/Pattern sheet sync **once**. It never scans a new GMC page. Audit and checkpoint hashes are verified after each fetch batch, and the full Audit persists through the existing workflow.

## Reports
The artifact now includes `refetch_batch_progress.json` with per-batch `eligible_total`, `fetched_now`, `cached_total`, `VERIFIED`, and `NOT_VERIFIED` counts. Also inspect `attribute_shopify_refetch_summary.json`, `attribute_sheet_sync_summary.json`, `attribute_auto_approval_evidence.csv`, and `summary.json`.

Note: `eligible_total` counts *currently eligible, not-yet-cached items* at the beginning of that batch; it is not a fixed population denominator. Not every cached item creates an approved Color/Pattern value. Pending rows can grow while the program finishes evidence collection. Do not interpret Pending as a GMC deficiency or as a task employees should do now.

## Safety and recovery
- Do not delete cache keys or the `out/` checkpoint while migrating this version.
- Do not run the GMC scan workflow; only the employee Google Sheets Sync workflow.
- If the Shopify request or Google Sheets sync fails, GMC is unchanged. The GitHub Actions cache/save runs only on success, so that run's uncommitted cache changes may need refetching; do not assume successful intermediate requests survived.
- After the batch is complete, inspect the latest artifact before extending to more products.
- All staff-edited Pending content remains subject to the existing non-destructive Google Sheets reconciliation checks.

## Validation performed offline
- 123 unit tests passed, including four new bounded-batch tests.
- The 4,500-item Audit baseline can be validated for unique ID count and protected against mutation.
- Live Shopify and Google Sheets API writes were not exercised in the build environment. They require the existing GitHub secrets and are executed by the workflow itself.
