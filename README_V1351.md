# ChipteeAmz V1.3.5.1 — Color/Pattern evidence consistency (read-only)

Scope: **targeted patch** on top of V1.3.5; no change to Fabric Master, Material approvals, prior Variant Color rules, GMC writing, or pagination.

## Why
The old V1.3.5 assigned `PATTERN_EXPLICIT_DESCRIPTION_VERIFIED` even when the actual evidence was `SHOPIFY_TITLE_EXPLICIT_PATTERN`. It also produced an approval CSV without the actual supporting text or rule ID. These are code defects, not staff data mistakes.

## Changes
1. Auto-approval from Shopify Title now has `PATTERN_EXPLICIT_TITLE_VERIFIED`; from Description has `PATTERN_EXPLICIT_DESCRIPTION_VERIFIED`.
2. Every newly auto-approved Color/Pattern includes `evidence_source`, `evidence_text`, and `rule_id`. Internal validation refuses new auto-approvals if status/source/rule/value do not match.
3. Previous V1.3.5 mislabelled Pattern rows are **reconciled only once** against verified cached Shopify Title and exact Product ID + Variant ID. Verified rows retain the value and have their label corrected. If title evidence is insufficient/missing, the specific Pattern is quarantined as proposed-only for re-fetch/review. Audit decisions are not based on product title shortcuts or inferred image colors.
4. `legacy_pattern_source_reconciliation.csv` shows each corrected/quarantined item. This is included in the GitHub artifact.
5. Unchanged: staff tabs, Material rules, Shopify GraphQL read-only fetch up to 500 items/run, and existing GMC write disabled.

## Deploy
Back up current GitHub artifact and Google Sheet. Upload the repository files in this ZIP (excluding `__pycache__`). Run existing workflow `GMC Attributes Employee Google Sheets Sync (Read Only)`. Inspect `attribute_sheet_sync_summary.json`, `attribute_auto_approval_evidence.csv`, and `legacy_pattern_source_reconciliation.csv`.

## Evidence availability
Offline QA was able to cross-check prior 18 new approval rows and Audit title text: 6 Color Variant cases did not contradict source, 11 Argyle titles explicitly said Pattern, 1 title merely said `Argyle Outfit` (plus `Leopard`) and must be validated with original Shopify title. This is **not** a live Shopify validation. New code uses exact Shopify evidence cached by the GitHub workflow.

## Tests and safety
Run `python -m unittest discover -s tests -q` (101 tests on this build). GMC write remains disabled. No claim is made that the large remaining Pending list can be resolved without evidence — the system retains staff review for truly ambiguous Color/Pattern.
