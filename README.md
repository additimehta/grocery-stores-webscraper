# Grocery Stores Webscraper

A small Python starter for collecting selected grocery products into a CSV for the CS348 project. No frontend, API server, or database is required.

## Status

On October 1, 2026, the sample eggs page loaded in the available cloud browser and exposed Product JSON-LD. Passing that live-page JSON-LD through the Python parser and CSV writer correctly exported Grade A Large Eggs, Burnbrae Farms, CAD 6.98, product ID, and image URL. The page showed Loblaws Baseline Road as the selected store.

This verifies the sample page's data format and the Python parsing/export stages, not the full standalone Playwright command. Local Chromium installation failed in the development environment, so browser startup and navigation through the Python script still need a local end-to-end test. The page displays 18 ea, but its JSON-LD omits size, so the current parser leaves size blank. Other product pages and store selection are not verified. No scraped dataset is included.

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
