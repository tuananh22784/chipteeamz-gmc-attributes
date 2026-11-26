# ChipteeAmz GMC Attribute Audit V1.3 (READ-ONLY)

## Purpose
Reads products from Google Merchant API (`products.list`) and verifies **exact Shopify product + variant** via Shopify Admin GraphQL. Detects missing/placeholder `color`, missing `pattern`, and missing `material` without modifying Shopify, Simprosys or GMC.

**V1.3 policy confirmed by the merchant:** The native Shopify Product Title correctly describes the design. Explicit, unambiguous colors and patterns in that verified title are classified as attribute-level `*_TITLE_VERIFIED`. Shopify Color Option can be `COLOR_VARIANT_VERIFIED`. Material extracted from shared product descriptions is **never auto-approved** in V1.3 (regardless of variant); manual subtype verification is required.

`approved_color`, `approved_pattern`, and `approved_attributes.csv` are **read-only preapproval proposals** for review and future controlled supplemental feed integration. `auto_fix_eligible.csv` stays empty; no writes exist in this package.

## Install / upgrade

- Replace the files in your existing GitHub repo (`engine.py`, `live.py`, `requirements.txt`, `tests/test_engine.py`, `.github/workflows/audit.yml`, `README.md`). Do not delete GitHub Secrets or recreate Google credentials.
- Existing GitHub Secrets: `MERCHANT_SERVICE_ACCOUNT_JSON`, `GMC_ACCOUNT_ID`, `SHOPIFY_SHOP_DOMAIN`, `SHOPIFY_ADMIN_TOKEN`.
- Go to Actions > **GMC Attributes V1.3 Read-Only Audit** > Run workflow.
- First run: `scan_mode=new`, `page_size=500`, `max_pages=1`. Select `resume` on the next run with **same page_size**. Increase max_pages after verifying output.
- Each run uploads a full report artifact and attempts to preserve a snapshot via GitHub Actions cache (`actions/cache/restore` + `actions/cache/save`). Snapshot is restored automatically for Resume.
- On Resume, missing/corrupt/incompatible checkpoint or CSV means **fail closed** (no silent restart). If the Merchant API rejects an expired `pageToken`, start a fresh scan; never skip ahead by guessed offsets.

## Outputs

- `out/summary.json` — cumulative counts, `pages`, `completed`, `approved_color`, `approved_pattern`, `approved_material` (always zero in V1.3), `scanned`.
- `out/checkpoint.json` — latest committed page cursor/account/page size/schema.
- `out/audit.csv` — item attributes, evidence, independent `color_qa`, `pattern_qa`, `material_qa`, and `approved_*` fields.
- `out/candidates_review.csv` — items with any proposal.
- `out/ready_for_qa.csv` — verified Shopify items with proposals.
- `out/needs_review.csv` — unverified/unmatched/no usable proposal.
- `out/approved_attributes.csv` — verified color/pattern attribute-level read-only proposals; **not sent to GMC**.
- `out/auto_fix_eligible.csv` — header only; GMC write remains disabled.

## Checkpoint considerations

- GitHub Actions cache is **not permanent storage** and is subject to capacity limits, eviction, and cache restore failures. Report artifacts also have finite retention; download them for durable archival. V1.3 does not use a GitHub repository commit, external object storage, or a database for checkpointing.
- The output grows with every run; for millions of SKUs consider external durable storage + partitioned reports in the next iteration. GitHub hosted runner time, cache capacity, Shopify rate limits, API cursor validity and artifact size constrain large scans.
- One scan must use a consistent API account and page size. Concurrent runs are serialized using GitHub Actions `concurrency`. Only one scan snapshot is continued per branch.
- If a run dies while writing CSVs before a checkpoint commit, Resume will reject a checkpoint / CSV row count mismatch rather than silently skip items. Recover by new scan or manual checkpoint reconciliation.
- Merchant pagination is of a **changing live catalog**, not a guaranteed immutable snapshot; uniqueness check prevents duplicates but cannot guarantee zero omissions if products are added/removed during a long audit. A subsequent reconciliation pass is advised.

## Local tests

```bash
python -m pip install -r requirements.txt
python -m py_compile engine.py live.py
python -m unittest discover -s tests -v
```

## Known limitations

- `pattern` remains unknown when not explicit in Title. Do not assign `Solid` / `Printed` in bulk.
- Color mentions can include artwork accents; V1.3 relies on merchant confirmation of Title design accuracy. More than three distinct detected colors are flagged ambiguous. American flag stripes are conservatively excluded as a primary `Striped` pattern.
- Material must be subtype validated before any write. Even `Material: Polyester` in shared description isn't enough alone.
- Two legacy Offer ID shapes from earlier audits remain unmatched, do not generate candidates for them.
- Do not delete the GMC `One Color` attribute rule yet. Such a rule may override future supplemental attributes; resolve only at the controlled write stage.

## Fabric Composition Master mapping (user-supplied, read-only add-on)

* `material_master.csv`: 56 style-to-fabric rows transcribed from the user's uploaded "Fabric Composition - Sheet1.csv". Original composition strings kept verbatim (notably `Cotton` does **not** imply `100% Cotton`).
* `material_aliases.csv`: limited explicit name-normalization aliases only. New unknown styles are not inferred.
* `material_rules.py`: post-processes *cumulative* `out/audit.csv` after each run and writes `out/material_mapping_review.csv`, `out/material_master_candidates.csv`, `out/material_mapping_summary.json`. Does **not** change the existing audit CSV schema or checkpoint schema 3 and **never** calls GMC write endpoints.
* The GitHub workflow calls `material_rules.py` after the main read-only audit. Existing cached `out/` (7 pages) is preserved on Resume.
* Compound styles such as `Long sleeves UPF + Face shield` are sent for review. A generic `Hoodie` is `Cotton`; `220g air layer Hoodie` is `100% polyester`. Generic `Zip up hoodie` is not assumed to be the 220g variant.
* Master candidates need a final review of the user's intended variant nomenclature prior to any GMC supplemental feed writes.

### Local reprocess without calling APIs

```bash
python material_rules.py --audit /path/to/audit.csv --out out
```

### Resume on GitHub

Keep `scan_mode=resume`, `page_size=500` to continue the existing scan. The workflow name changes, but the cache key prefix remains `gmc-v13-`, so the 7-page state can be restored. No change to `engine.py` or `live.py` is required.


## Pattern Description fallback (V1.3.1)

- Priority: verified Shopify Product Title first, verified Shopify native Product Description second.
- Only explicit pattern names in design-related statements can create a description-derived proposal.
- A description-derived pattern is marked `PATTERN_DESCRIPTION_REVIEW` and **approved_pattern remains blank** until QA. Title-derived patterns retain `PATTERN_TITLE_VERIFIED`.
- General marketing text, multiple conflicting patterns, vague `Printed`, and ambiguous flag stripes are not inferred. `Argyle` is now supported.
- The existing audit CSV columns and checkpoint schema stay unchanged, so `resume` continues safely. **Important: previously saved rows are not retroactively re-extracted, and the historic audit CSV does not store full Shopify descriptions.** To apply the new fallback to older 3,500 rows, perform a deliberate fresh scan or implement a separate Shopify re-enrichment pass; do not expect `resume` to recalculate old rows.
- Fabric rules remain read-only. Also includes the previously user-confirmed mapping of `Women's Short Sleeve Quarter-Zip` variants to `Women Quarter Zip` (100% polyester).
