# Grocery Stores Webscraper

A small Python starter for collecting selected grocery products into a CSV for the CS348 project. No frontend, API server, or database is required.

## Status

Initial scaffold, not a verified working Loblaws scraper yet. A normal request returned a JavaScript app shell during investigation. The script uses Playwright and attempts to extract Product JSON-LD after rendering. Whether Loblaws provides that markup in a live browser still needs verification. If it does not, the extraction adapter needs to be updated using the actual page or product response. Chromium could not be installed in the development environment, so live scraping has not been tested. No real scraped dataset is included.

## Setup (Mac)

Use Python 3.10 or newer. From the repository folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m playwright install chromium
```

## Choose products

Edit `products.json` with exact Loblaws product page URLs and optional category labels. One real eggs URL is included as a starting point. This version does not search by product name or crawl categories.

```json
[
  {
    "category": "eggs",
    "url": "https://www.loblaws.ca/en/grade-a-large-eggs/p/20814294001_EA"
  }
]
```

## Run

```bash
python scraper.py --headed
```

Successful records go to `output/GroceryData.csv`. Failed pages go to `output/GroceryData.errors.json`, and any failure gives the command a nonzero exit status. A partial run exports only successful records. If all products fail, the previous CSV is preserved. Output files are ignored by Git.

CSV columns: category, name, price, currency, size, brand, product_id, image_url, product_url, retailer, scraped_at.

Missing optional fields stay blank. Missing or ambiguous prices cause an error instead of becoming zero. Prices are those exposed by the page's offer data; this starter does not select or verify a store, distinguish loyalty offers, or handle multi-buy pricing. Do not treat its output as prices for your local store until store selection is implemented and verified.

The browser visits products sequentially with a two-second pause. Access-denied responses and missing markup are reported; browser automation does not guarantee access to Loblaws.

## Check the parser and CSV export

```bash
python -m unittest discover -s tests
```

These tests use synthetic data. They do not verify Loblaws access or the live page format.
