# ChipteeAmz — Employee-confirmed Material queue

This is a **Google Sheets** integration (a shared online Excel-like spreadsheet), not Microsoft Excel Online. All Google Merchant Center operations remain **READ_ONLY**. The sync applies confirmed material to the local audit and saves approval history in Google Sheets. It does not push material to GMC or change Shopify.

## Initial setup (one time)

1. Upload the three tabs from `material_employee_review_template.xlsx` into a **new Google spreadsheet**. Name sheets exactly `Pending_Material`, `Approved_Rules`, `History`.
2. Google Cloud project: enable **Google Sheets API**. Share the spreadsheet with `chipteeamz-gmc-audit@chipteeamz-cj-github.iam.gserviceaccount.com` as **Editor**. This service account can edit *this spreadsheet only after sharing*.
3. Add GitHub Actions **Secret** `MATERIAL_SHEET_ID` with the spreadsheet ID from `https://docs.google.com/spreadsheets/d/<ID>/edit` (only ID, not full URL). Existing `MERCHANT_SERVICE_ACCOUNT_JSON` credential is reused with Sheets scope.
4. Add this package to `chipteeamz-gmc-attributes`. Run `GMC Material Employee Google Sheets Sync (Read Only)` manually the first time. It reuses your existing audit cache and does not fetch new GMC pages.
5. For future automatic runs, the workflow triggers daily 07:25 UTC (14:25 Vietnam time). On successful processing, confirmed entries disappear from `Pending_Material`, remain permanently in `Approved_Rules` and `History`.

## Staff instructions

Only edit: `scope`, `confirmed_style`, `confirmed_material`, `staff_note`, `status` in Pending. Leave IDs and evidence columns untouched. `scope` defaults to **ITEM**: material applies to *only this exact offer ID*. Use `STYLE` only when a clearly named canonical Style is identical across other products and does not depend on variation/color. Generic words `Shirt`, `Jersey`, `Women`, etc. cannot be global rules.

`confirmed_material`: `Cotton`, `100% Polyester`, `96% Polyester, 4% Spandex`, etc. Percentages must sum to 100; unsupported/free-text values are rejected for review. `confirmed_style`: actual garment subtype (e.g. `Standard T-Shirt`, `Short Sleeve Bowling Jersey`), not theme or design title. `status`: change to **APPROVE** after confirming. Other statuses stay pending.

**Important**: color-specific fabric (e.g. Heather) should remain ITEM scoped. Composite/multiple-component items should only be approved when the employee has an accurate single-material value for the offer; do not fabricate a weighted composition.

## Flow

1. Fetch pending and saved rules from Google Sheets.
2. Validate approved rows. Conflicts remain pending as `RULE_CONFLICT`.
3. Save confirmed decisions to `Approved_Rules`, append `History`.
4. Apply confirmed rules to local `audit.csv` (without altering checkpoint or writing GMC).
5. Refresh Pending with newly unresolved items; accepted rows disappear.

**Never delete `Approved_Rules` to clean up pending.** The persistent rules are the source of truth across GitHub Action cache expiry.

## Offline tests

Run `python -m unittest discover -s tests -q` and `python material_sheet_sync.py --out out --local` (the latter uses `out/Approved_Rules.csv`, `out/History.csv`, and `out/Pending_Material.csv` as a local stand-in and rewrites only local reports).

## Critical data provenance

The 4,500-row Audit is a historical snapshot. The template contains the unresolved **employee-actionable** cases only. Excludes 13 already holding GMC material, 10 Shopify-unverified, 6 non-apparel, and 34 multiple-component entries requiring a dedicated policy. Unknown types should not be automatically resolved as Cotton/Polyester without employee approval.

## Run with regular GMC audit

A separate daily workflow already processes the review sheet automatically. If you want *every* GMC audit run to process employee approvals immediately, add the same sync action after `python unified_rules.py --out out` and before the cache save step. Use `MATERIAL_SHEET_ID` and the existing service-account credential as in `.github/workflows/material-sheet-sync.yml`; do not embed a credential in source files. The scheduled workflow is sufficient for routine use even if the GMC pagination audit itself has not run that day.
