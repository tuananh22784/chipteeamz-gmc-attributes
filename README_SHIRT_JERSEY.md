# V1.3.2 Shirt/Jersey exact Shopify refetch

- Mode: read-only. **Does not create GMC update requests**. Existing GMC pagination checkpoint is not modified.
- Existing 49 style confirmations, 17 additional confirmations, hoodie/polo rules unchanged.
- `refresh_shirt_jersey.py` targets rows with `REVIEW_MISSING_STYLE` + `TITLE_INSUFFICIENT` / `AMBIGUOUS_JERSEY` only.
- Refetches Shopify Product Title, Product Type, native Description, Variant selectedOptions and exact Product/Variant IDs.
- Does not conflate **Shirt**, **T-shirt**, **Polo**, **Bowling Jersey**, **Cycling Jersey**. Description evidence is restricted to explicit labeled `Style:`, `Product Type:`, `Garment Type:` lines.
- Export `shirt_jersey_style_evidence.csv`, `shirt_jersey_refetch_summary.json` with explicit provenance and decision; the `unified_rules.py` rebuild applies only `EXPLICIT_STYLE` verified same Product/Variant ID, and only exact Material Master entries.
- Run GitHub Actions -> **GMC Recheck Shirt & Jersey (No New GMC Page)**.
- Requires valid Shopify Secrets and existing cache `out/audit.csv` + `out/checkpoint.json`. No new GMC page scanned.
- If Shopify Product Type/Description remain generic, unresolved items require manual verification, not a guessed fabric.
