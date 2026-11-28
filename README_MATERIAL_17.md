# V1.3.2 additional 17 material confirmations (read-only)

This package extends the previously tested V1.3.2 Unified Engine, **without changing Google Merchant/Shopify auth, Merchant pagination, or checkpoint schema**.

## Included authoritative rules
- The original 56-row fabric master is preserved, with four additional exact compositions from the user: women long-sleeve cycling jersey, women short-sleeve cycling jersey, men short-sleeve cycling jersey (each 96% polyester / 4% spandex), and Hat BWB (100% polyester).
- All 17 supplementary confirmations are preserved verbatim in `style_confirmations_additional.csv` and verified at runtime. Pocket variants are mapped to existing fabric masters when expressly confirmed by the user.
- `Women` and `Kid` generic styles are restricted to exact, user-confirmed item IDs. Never apply to other products.
- `Unisex Premium T-shirt` is color-dependent: solid colors 100% cotton; Ash Grey 99% cotton / 1% polyester; Heather Grey 90% cotton / 10% polyester; other Heather colors 52% cotton / 48% polyester. Unrecognized or missing variant color stays under review. A color found only in a design title is not accepted for fabric decisions.
- `Female` was described as Standard Crew Neck Sweatshirt, but **no fiber composition was provided**. It remains under `REVIEW_UNMAPPED_SUBTYPE` rather than guessing.
- Multi-component sets remain separate, with no invented weighted blend. Existing Merchant material is never overwritten.

## Recalculate offline
Copy the latest `audit.csv` (4500 rows in the validation package) into a fresh working directory, then run:

```bash
python unified_rules.py --out /path/to/working-directory
```

This recomputes material rule output and writes CSV and JSON reports; it **does not contact or mutate GMC or Shopify**. For this offline QA, no checkpoint file is supplied; the original GitHub checkpoint is unaffected.

## Live deployment
Upload the repository files (including the new CSV) and commit. The GitHub Actions workflow remains READ_ONLY. Take a copy of existing GitHub `out/` artifact and checkpoint before updating. Verify that Resume reads the existing checkpoint, and do not run concurrent resumptions.

## Verified offline with 4500 item IDs
Old approved material: 4230; new: 4267 (+37). No previously approved material lost, no item IDs changed. All 17 new confirmation entries explicitly classified. `Female` remains under review. This is an offline calculation only and does not demonstrate successful future GMC writes.
