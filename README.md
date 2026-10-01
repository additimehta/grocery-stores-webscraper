# Grocery Stores Webscraper

A shared Python scraper for the CS348 grocery-price project. Product rules live in JSON. Store-specific HTML extraction lives in an adapter. No frontend is required.

## Setup and run

Use Python 3.10 or newer. From this repository:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m playwright install chromium
python scraper.py --check-config
python scraper.py --headed
```

The milk-only script and original URL-list workflow have been replaced by this command.

## Files

- `scraper.py`: reads configuration, runs each search, selects results and writes CSV.
- `products.json`: 110 product/size entries extracted from the supplied Statistics Canada CSV, Table 18-10-0245-01. Historical prices are not copied. Three entries are enabled: milk 1 L, milk 4 L and cheddar block cheese. Milk 2 L is retained but disabled by preference. The other 106 entries need matching/comparison rules before enabling.
- `stores.json`: configured stores, website, optional expected location and scrolling limit.
- `stores/loblaws.py`: loads and reads Loblaws search cards with Playwright, returning a shared product format.
- `matching.py`: matches names, converts units and selects the lowest comparable price.

## How it works

1. Read enabled product rules and configured stores. Unknown store adapters fail clearly.
2. Open a store search page. Playwright runs the website's JavaScript and reads product cards. Searches are reused when several rules use the same term, so both milk sizes share one search.
3. Reject unavailable products, unknown/ambiguous prices and visibly conditional membership or multi-buy offers. Unconditional sales can qualify. The offer checks are conservative and based on the displayed card text.
4. Match against each rule's accepted names and size constraints. Exact names avoid including flavoured, shredded or specialty variants by accident, but may miss legitimate unfamiliar names. Review live names before extending a rule.
5. Compare prices with Decimal, before rounding. Select one product per enabled rule per configured store. Break price ties by brand and product ID.
6. Save results to `output/StorePrices.csv`. Save extracted eligible-price candidates, selected rows and unmatched rules in `output/StorePrices.audit.json`. If a rule has no match, do not replace an existing CSV. Navigation/browser failures also leave the CSV unchanged, but may occur before an audit file is written.

## Current product rules

Milk: regular 2% dairy milk, any brand, exact 1 L and 4 L packages compared separately. Exclude other fat percentages, plant-based/flavoured and specialty milk.

Cheese: plain cheddar blocks, any brand, 400–800 g packages, compared per 500 g. Accepted cheddar names are deliberately explicit. Shredded, sliced, flavoured and spreadable cheese names are not accepted.

Example: a 400 g block at $4 compares as $5 per 500 g. An 800 g block at $7 compares as $4.375 per 500 g, so the 800 g block wins even though its checkout price is higher. The exported comparison is rounded to cents; selection uses the unrounded value. The CSV retains both package price and comparison price.

To add another product, edit its entry in `products.json`, add `allowed_names` and `comparison`, and set `enabled` to true. An exact rule uses `mode: exact`, a base `unit` (`ml`, `g`, `count`) and `amount`. A normalized rule also needs `min_amount` and `max_amount`. No new product-specific Python file is needed. Weight-priced produce/meat still needs adapter work to distinguish $/kg from estimated package prices; those catalog entries remain disabled.

## Stores and limits

Only Loblaws has an implemented adapter. A new website needs its own `search(page, store_config, search_term)` function and registration in `ADAPTERS`; it must return the same fields as Loblaws. Configuration alone cannot teach the scraper a new website's HTML.

The Loblaws adapter records the selected location. Set `expected_store` in `stores.json` to fail if a different location is shown. It does not select a location automatically. Changing locations between searches fails rather than mixing prices.

Results mean cheapest among collected qualifying search cards, not a guaranteed minimum across the entire store. The adapter scrolls until results stop growing or the limit is reached; it does not handle every pagination pattern. Store names are not yet database IDs. The catalog's national monthly average prices and scraped store quotes must remain separate in MySQL.

## Verification

```bash
python -m unittest discover -s tests
```

The Loblaws selectors were inspected against live milk search cards on October 1, 2026. The shared comparison logic is tested for milk, cheddar normalization, exclusions, units, offer conditions, reused searches, missing matches and CSV escaping.

Full standalone browser execution remains unverified because the Chromium download failed in the development environment. Cheddar search has not been verified live. Automated tests use synthetic and previously observed sample values; they do not establish complete store coverage or current prices. Run locally before relying on collection.
