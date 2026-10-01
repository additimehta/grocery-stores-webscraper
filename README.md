# Grocery Stores Webscraper

A small Python scraper for a grocery price comparison side project. It collects product prices and saves the cheapest matching results to a CSV.

Currently set up for Loblaws, with rules for 1 L and 4 L milk and cheddar cheese. Still a work in progress.

## Setup

Requires Python 3.10+.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m playwright install chromium
```

## Run

```bash
python scraper.py --headed
```

Results are saved to `output/StorePrices.csv`.

Edit `products.json` to change product rules and `stores.json` for store settings. Additional websites need their own store adapter.
