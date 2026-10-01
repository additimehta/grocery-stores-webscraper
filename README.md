# Grocery Stores Webscraper

Python + Playwright scripts for collecting store prices into CSV for CS348. No frontend or API server is needed.

## Setup (Mac, Python 3.10+)

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m playwright install chromium
```

## Milk search workflow

```bash
python milk_search.py --headed
```

The input is `milk_rules.json`. Supply the website, search term, accepted product names and package sizes, rather than individual product URLs. Only the Loblaws website adapter is implemented.

The default rules select regular 2% dairy milk in **1 L and 4 L** sizes. Brands can differ. The cheapest qualifying package is selected separately for each size. Exact accepted names prevent almond milk, chocolate milk, cream, other fat percentages, and specialty milk such as organic, lactose-free, protein-enriched or microfiltered products from slipping through. This is deliberately conservative: legitimate products with different names may also be excluded. Extend `allowed_names` after reviewing their actual listings.

## How the implementation works

1. `load_rules()` reads and validates `milk_rules.json`.
2. `collect_cards()` opens the Loblaws milk search in Chromium. Playwright runs the site's JavaScript. It reads the selected store from the page, then extracts the product cards using inspected `data-testid` attributes. It scrolls to collect more cards, deduplicates by product URL, and stops after three unchanged scans or the configured scroll limit.
3. `size_ml()` reads only the package size before the comma. It converts `1 l` and `1000 ml` to 1000, and `4 l` to 4000. Unit prices such as `$0.16/100ml` are not package sizes. Unknown sizes and ambiguous multi-packs are rejected.
4. `single_price()` reads the displayed sale price when present, otherwise the regular price. It rejects visible membership and multi-buy conditions, non-member-price layouts, zero/missing/ambiguous prices. Unconditional single-package sales are allowed. This is a conservative text-based check, not a general promotions engine.
5. `select_cheapest()` checks availability, exact accepted product name, package size and price. It maintains a separate minimum for each size. It uses Python `Decimal` for price comparisons and a stable brand/product-ID tie break.
6. `write_output()` writes two selected rows to `output/StorePrices.csv` using Python's built-in `csv` module. The actual store, timestamp, product name, brand, size, price, URL and selection scope are included. Collected cards are saved separately in `output/StorePrices.candidates.json` for inspection.

If either size has no qualifying result, the command fails and leaves the previous CSV unchanged. It does not invent a price or silently replace missing 1 L milk with another size. Check the terminal exit status rather than assuming an older CSV is fresh.

## Store and coverage

The script records whichever store the website selected; it does not choose a local store automatically. Set `expected_store` to an exact store name to fail if the page selects a different store. Leaving it `null` accepts the store shown on the page and records its name.

The result means **cheapest qualifying product among collected search cards**, not a verified minimum across the entire store. Search ranking, pagination, lazy loading, promotions and availability can affect coverage. The script scrolls but does not implement every possible pagination control. Membership or multi-buy products are skipped entirely even when a usable regular price might exist. Store names are not yet normalized to database store IDs.

`StorePrices.csv` is intentionally separate from the existing national monthly `GroceryData.csv`. A current store quote and a Canada monthly figure describe different things. Import them into appropriate MySQL tables; do not overwrite the national dataset with store quotes.

## Verification

On October 1, 2026, the live cloud browser loaded the milk search for Loblaws Baseline Road. The implemented card-extraction selectors returned Neilson 2% Milk at 1 L / CAD 3.64, 2 L / CAD 5.48 and 4 L / CAD 6.44. Selection tests using these observed names/sizes/prices retain 1 L and 4 L and exclude 2 L. These observations are not promises of current or local prices.

```bash
python -m unittest discover -s tests
```

Tests cover separate size groups, cross-brand minimum selection, wrong milk types, unit normalization, conditional offers, sales and unavailable products. The original product-page parser tests also remain.

The full standalone Python browser launch/navigation/scroll sequence has **not** been tested end to end in the development environment because its Chromium download failed. Live selector inspection and Python selection tests verify those stages separately. Test the command locally before relying on automated collection.

## Original product-URL script

`python scraper.py --headed` still runs the original `products.json` URL workflow and writes `output/GroceryData.csv`. Its sample eggs page's Product JSON-LD was verified separately in the cloud browser. It does not apply the milk constraints. Use `milk_search.py` for the new constrained search.
