# GMC Attributes V1.3.5 — Safe Color/Pattern and Sheets Sync

## Changes

- Preserves Material 56-master+17-confirmations, previously approved Color/Pattern/Material, 4,500-item scan checkpoint, and existing Google Sheet ID.
- Color auto approvals from an **exact Shopify Variant Color** or a single explicitly labeled **garment color** in Shopify Default Description. Decorative artwork colors are never automatically approved.
- Pattern auto approvals only if the Shopify Product Title explicitly describes one pattern as a `pattern`/`print`, or if Shopify Default Description has a labeled `Pattern: ...` field. Ambiguous or contradictory pattern evidence is sent to staff.
- Exact Product ID / Variant ID / verification status required before using Shopify evidence.
- Material / Color / Pattern Google Sheets rules and History now use **append-only** writes, rather than wiping and rebuilding the entire sheet. Pending rows are reconciled with a fresh read, appending new rows and deleting completed ones only when the snapshot matches. On concurrent edits, workflow aborts rather than clearing the sheet.
- New `attribute_auto_approval_evidence.csv` in GitHub artifact lists actual newly approved values and evidence. `attribute_shopify_evidence.csv` is also included for QA.
- Re-fetch continues for up to 500 verified Shopify offers per run, never alters GMC/Shopify.

## Important concurrency limitation

The Sheets API offers no atomic compare-and-swap transaction spanning multiple API calls. Snapshot validation significantly reduces edit-loss risk but cannot eliminate an edit racing within the narrow interval before deleting rows. For a strict guarantee, use a dedicated Apps Script LockService-based review UI and ensure all editors submit through that UI, or avoid deleting rows and archive them instead. This version uses the user's requested delete-after-approval behavior with checks.

## Installation

1. Back up current GitHub files, latest `out/` artifact and Google Sheets tabs.
2. Upload all contents of this ZIP into the root of `chipteeamz-gmc-attributes`, preserving `.github/workflows/`.
3. Keep the existing GitHub secrets. No new Sheet or secret required.
4. Trigger **GMC Attributes Employee Google Sheets Sync (Read Only)**. By default, fetches 500 new missing Color/Pattern offers per daily run and applies existing approved staff rules.
5. Verify artifact reports `attribute_shopify_refetch_summary.json`, `attribute_sheet_sync_summary.json`, `attribute_auto_approval_evidence.csv`, and `audit.csv`. Check `CONCURRENT_SHEET_CHANGE` log if staff edits overlap the job; rerun after the editing window.
6. Continue the regular `GMC Attributes V1.3.2 Unified Read-Only` scan with `scan_mode=resume`. This upgrade does not modify checkpoint schema.

## Offline checks performed

- 93 tests pass, including new patterns/colors, anti-artwork inference, evidence identity guard, conflict handling, and Sheets concurrency preflight.
- Reprocessing real `audit(10).csv` (4,500 unique items) with no live Shopify evidence preserved **3,230 approved Color, 544 approved Pattern, and 4,416 approved Material**. In that dry run it creates no new approvals, appropriately.
- A separate **synthetic evidence test** using two real audit IDs and fabricated text verified that an explicitly labeled Color/Pattern is approved while artwork-only color text stays Pending. Synthetic test results must not be interpreted as real Shopify product evidence.
- This container did not access the live Google Sheet or Shopify API. Online connection and concurrent editing behavior remain to be validated on GitHub.

## GMC write mode

**OFF**. This package does not add a Merchant API write path.
