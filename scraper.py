"""Collect configured products, select comparable prices, and export CSV."""
import argparse
import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from matching import select_cheapest
from stores import loblaws

ADAPTERS = {'loblaws': loblaws}
FIELDS = ['scraped_at', 'retailer', 'store', 'category', 'reference_size',
          'comparison_price', 'package_size', 'package_price', 'currency',
          'brand', 'name', 'product_id', 'product_url', 'image_url', 'selection_scope']


def load_config(products_path, stores_path):
    catalog = json.loads(Path(products_path).read_text())
    stores = json.loads(Path(stores_path).read_text())
    products = [product for product in catalog if product.get('enabled')]
    if not products or not stores:
        raise ValueError('Enable at least one product and configure at least one store.')
    if len({p['id'] for p in catalog}) != len(catalog):
        raise ValueError('Product IDs must be unique.')
    for product in products:
        if not product.get('allowed_names') or not product.get('search'):
            raise ValueError(f"Missing matching rules for {product['id']}")
        comparison = product['comparison']
        if comparison['mode'] not in ('exact', 'normalized') or comparison['unit'] not in ('ml', 'g', 'count'):
            raise ValueError(f"Invalid comparison for {product['id']}")
        if comparison['amount'] <= 0:
            raise ValueError('Comparison amounts must be positive.')
        if comparison['mode'] == 'normalized':
            if not 0 < comparison['min_amount'] <= comparison['max_amount']:
                raise ValueError('Invalid package size range.')
    for store in stores:
        if store['adapter'] not in ADAPTERS:
            raise ValueError(f"No adapter implemented for {store['adapter']}")
        if store['website'].rstrip('/') != 'https://www.loblaws.ca':
            raise ValueError('The Loblaws adapter only supports https://www.loblaws.ca')
        if not isinstance(store.get('max_scrolls', 12), int) or not 1 <= store.get('max_scrolls', 12) <= 50:
            raise ValueError('max_scrolls must be between 1 and 50.')
    return products, stores


def make_row(product, price, rule, retailer, store):
    return dict(zip(FIELDS, [datetime.now(timezone.utc).isoformat(), retailer,
        store, rule['category'], rule['source_size'], format(price, '.2f'),
        product['size'].split(',')[0].strip(), product['price'], product['currency'],
        product['brand'], product['name'], product['product_id'],
        product['product_url'], product['image_url'], 'cheapest_among_collected_search_results']))


def write_csv(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.csv.tmp')
    with temporary.open('w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def collect(page, products, stores):
    rows, audit, errors = [], [], []
    for store in stores:
        adapter = ADAPTERS[store['adapter']]
        searches = {}
        selected_store = None
        for rule in products:
            query = rule['search']
            if query not in searches:
                if searches:
                    time.sleep(2)
                candidates, location = adapter.search(page, store, query)
                if selected_store is not None and location.casefold() != selected_store.casefold():
                    raise ValueError('Store changed between searches; refusing mixed-store output.')
                selected_store = location
                searches[query] = candidates
                audit.append({'retailer': store['id'], 'store': location,
                              'search': query, 'products': candidates})
            match = select_cheapest(searches[query], rule)
            if match is None:
                errors.append(f"{store['id']}: no qualifying match for {rule['id']}")
                continue
            product, price = match
            rows.append(make_row(product, price, rule, store['id'], selected_store))
    return rows, audit, errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--products', default='products.json')
    parser.add_argument('--stores', default='stores.json')
    parser.add_argument('--output', default='output/StorePrices.csv')
    parser.add_argument('--headed', action='store_true')
    parser.add_argument('--check-config', action='store_true')
    args = parser.parse_args()
    products, stores = load_config(args.products, args.stores)
    print(f'{len(products)} enabled product rules, {len(stores)} store(s).')
    if args.check_config:
        return
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not args.headed)
        try:
            rows, audit, errors = collect(browser.new_page(locale='en-CA'), products, stores)
        finally:
            browser.close()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.with_suffix('.audit.json').write_text(json.dumps(
        {'searches': audit, 'selected': rows, 'errors': errors}, indent=2), encoding='utf-8')
    if errors:
        raise ValueError('; '.join(errors) + '. Previous CSV unchanged. See audit JSON.')
    write_csv(output, rows)
    print(f'Wrote {len(rows)} rows to {output}. Prices reflect collected results only.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(f'Scrape failed: {error}', file=sys.stderr)
        sys.exit(1)
