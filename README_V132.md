# ChipteeAmz GMC Attribute Audit V1.3.2 — Unified Rules (READ ONLY)

## Scope

- Reuses V1.3.1 Google Merchant API and Shopify Admin API integration.
- All 56 rows are preserved **verbatim** from `Fabric Composition - Sheet1.csv` in `material_master.csv`.
- All 49 individual user confirmations from `chipteeamz_styles_need_confirmation (1).csv` are recorded in `style_confirmations.csv`; each is either approved as an exact alias or has an explicit exception decision.
- The user also confirmed `Women Polo Shirt` => `Women Short sleeve polo shirt`, and `Women's Short Sleeve Quarter-Zip` => `Women Quarter Zip` => `100% polyester`.
- Material uses exact Shopify variant style / explicitly verified alias, not fuzzy matching.
- History gets a unified Material QA and Material approval in `audit.csv`, without changing the existing checkpoint or scanning order.
- **There is no Merchant or Shopify write API call in this package.**

## Deployment

1. Back up the *latest* GitHub Actions artifact containing `out/audit.csv` and `out/checkpoint.json` (8 pages / 4,000 items at time of preparation).
2. Copy the **contents** of `chipteeamz_gmc_v1_3` into the root of your existing private repository `chipteeamz-gmc-attributes`, retaining `.github/workflows/audit.yml`.
3. Keep GitHub Secrets and Cloud credentials unchanged. Never add credential JSON to repository files.
4. Run Actions → `GMC Attributes V1.3.2 Unified Read-Only` with `scan_mode=resume`, `page_size=500`, `max_pages=1`.
5. This run first restores the V1.3 cache and then runs `unified_rules.py` on *all previously scanned rows*. Its CSV schema is extended before the resume so the same checkpoint remains valid. After the extra page it rebuilds all reports with the new rules.
6. If checkpoint cannot be restored, workflow refuses to resume. Do not switch to `new` until you've preserved the current artifact and planned a fresh scan.

## Reports

`audit.csv`: original columns plus `material_rule_id`, `material_source`, `material_matched_subtype`, `material_decision`, `material_reason`, `material_component_1`, `material_component_2`. `approved_material` is now material from the verified Master where eligible.

`approved_attributes.csv`: rows with at least one `approved_color`, `approved_pattern`, or `approved_material`. Approval is **read-only rule approval**, not a GMC write.

`ready_for_qa.csv`: rows with at least one approved attribute.

`needs_review.csv`: rows without an approved attribute. Status may be `NEEDS_REVIEW` or `MATERIAL_OR_PATTERN_REVIEW`.

`material_mapping_review.csv`, `material_master_candidates.csv`, `material_mapping_summary.json`: consistent with the unified audit (the old independent 19-alias report is retired).

`style_alias_validation.csv`: one disposition for each of the 49 confirmations.

`summary.json`: unified metrics; `checkpoint.json` remains schema 3 with the existing cursor.

## Material safety rules

- Never overwrite a nonempty GMC material.
- Explicit style aliases only. A missing destination material remains `REVIEW_UNMAPPED_SUBTYPE` / `TARGET_NOT_IN_MASTER`.
- Generic `Women` and `Unisex` may only apply to explicitly confirmed example offer IDs; they are never generalized across the catalog.
- `Unisex Premium T-shirt` is color-dependent and remains review. No generic 100% cotton assertion.
- `Tumbler Cup` is not a fabric product and is excluded.
- `Men Short Sleeve Jersey` example is a cycling jersey but user mapped it to polo; keep it under conflict review until product-family validity is confirmed.
- `Long sleeves UPF + Face Shield` preserves `Long Sleeve UPF: 100% polyester` and `Face Shield: 95% polyester+5% spandex` separately; **no invented weight-averaged single garment percentage**.
- For variants with a confirmed exact design-label/style alias (e.g. `Deer shed / Hoodie`), mapping is permitted only for that exact string, never for arbitrary strings with `/`.

## Pattern & Color

Color and Pattern retained from the existing verified rule approvals. Title is the first source for pattern; Shopify Description fallback is only used for new pages, and any such results remain `PATTERN_DESCRIPTION_REVIEW`. Rebuilding historical 4,000 rows does **not** magically recover missing Shopify descriptions: to re-evaluate old rows for Description patterns, a separate Shopify re-fetch is required.

## Validate offline with the existing 4,000-item audit

```
python -m unittest discover -s tests -v
mkdir -p out
cp /path/to/audit.csv out/audit.csv
cp /path/to/checkpoint.json out/checkpoint.json
python unified_rules.py --out out
```

Do not upload private account export data to a public GitHub repository.
