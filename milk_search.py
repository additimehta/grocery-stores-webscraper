"""Find the cheapest collected regular 2% milk for each configured size."""
import argparse
import csv
import json
import re
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlencode, urlparse

# These selectors were inspected on the live Loblaws search page.
EXTRACT_CARDS = r'''() => {
  const text = (root, id) => root.querySelector(`[data-testid="${id}"]`)?.textContent.trim() || '';
  return [...document.querySelectorAll('[data-testid="product-title"]')].map(title => {
    const link = title.closest('a');
    const details = link?.parentElement;
    const tile = details?.parentElement;
    if (!link || !tile) return null;
    const button = tile.querySelector('[data-testid="atc-button"]');
    return {
      name: title.textContent.trim(), brand: text(details, 'product-brand'),
      size: text(details, 'product-package-size'),
      regular: text(details, 'regular-price'), sale: text(details, 'sale-price'),
      non_member: text(details, 'non-members-price'),
      offer_text: text(details, 'price-product-tile'),
      card_text: tile.textContent,
      available: !!button && !button.disabled,
      product_id: title.id, product_url: link.href.split('?')[0],
      image_url: tile.querySelector('[data-testid="product-image"] img')?.src || ''
    };
  }).filter(Boolean);
}'''
FIELDS = ['scraped_at', 'retailer', 'store', 'category', 'size', 'price',
          'currency', 'brand', 'name', 'product_id', 'product_url', 'image_url',
          'selection_scope']


def normalize_name(name):
    return re.sub(r'\s+', ' ', name.strip().casefold())


def size_ml(label):
    # Only the package size before the comma, never the unit-price denominator.
    label = label.split(',')[0].strip().casefold()
    match = re.fullmatch(r'(\d+(?:\.\d+)?)\s*(ml|l|litres?|liters?)', label)
    if not match:
        return None  # Ambiguous multi-packs are not silently treated as one carton.
    amount = Decimal(match[1]) * (1 if match[2] == 'ml' else 1000)
    return int(amount) if amount == amount.to_integral_value() else None


def single_price(card):
    # Skip membership/multi-buy offers instead of mistaking their conditional price
    # for what anybody can pay for one package.
    if card.get('non_member') or re.search(
        r'\b(min\s*\d|members?|buy\s*\d|\d+\s*for\b|\d+\s*/\s*\$|subscribe)\b',
        card.get('card_text', '') + ' ' + card.get('offer_text', ''), re.I
    ):
        return None
    price_text = card.get('sale') or card.get('regular', '')
    match = re.fullmatch(r'(?:sale\s*:?\s*)?\$\s*(\d+(?:\.\d{2})?)', price_text, re.I)
    if not match:
        return None
    price = Decimal(match[1])
    return price if price > 0 else None


def select_cheapest(cards, rules, store):
    allowed = {normalize_name(name) for name in rules['allowed_names']}
    winners = {}
    for card in cards:
        if not card.get('available') or normalize_name(card['name']) not in allowed:
            continue
        size = size_ml(card['size'])
        if size not in rules['sizes_ml']:
            continue
        price = single_price(card)
        if price is None:
            continue
        # Deterministic tie break across brands/products with the same price.
        key = (price, card['brand'], card['product_id'])
        if size not in winners or key < winners[size][0]:
            winners[size] = (key, card)
    timestamp = datetime.now(timezone.utc).isoformat()
    rows = []
    for size in rules['sizes_ml']:
        if size not in winners:
            continue
        key, card = winners[size]
        rows.append(dict(zip(FIELDS, [timestamp, 'Loblaws', store, rules['category'],
            f'{size // 1000} litre' + ('s' if size != 1000 else ''),
            format(key[0], '.2f'), 'CAD', card['brand'], card['name'],
            card['product_id'], card['product_url'], card['image_url'],
            'cheapest_among_collected_search_results'])))
    return rows


def write_output(path, rows):
    # Never replace a previous result with an empty or incomplete selection.
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.csv.tmp')
    with temp.open('w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    temp.replace(path)


def load_rules(path):
    rules = json.loads(Path(path).read_text())
    if rules.get('website', '').rstrip('/') != 'https://www.loblaws.ca':
        raise ValueError('Only https://www.loblaws.ca is implemented')
    if rules.get('sizes_ml') != [1000, 4000]:
        raise ValueError('This milk workflow currently supports sizes_ml [1000, 4000]')
    if not rules.get('allowed_names') or not all(isinstance(x, str) for x in rules['allowed_names']):
        raise ValueError('allowed_names must contain product names')
    if not isinstance(rules.get('max_scrolls'), int) or not 1 <= rules['max_scrolls'] <= 50:
        raise ValueError('max_scrolls must be between 1 and 50')
    if not isinstance(rules.get('search'), str) or not rules['search'].strip():
        raise ValueError('A search term is required')
    return rules


def collect_cards(page, rules):
    url = rules['website'] + '/en/search?' + urlencode({'search-bar': rules['search']})
    response = page.goto(url, wait_until='domcontentloaded', timeout=45000)
    if response and response.status >= 400:
        raise ValueError(f'Search returned HTTP {response.status}')
    page.locator('[data-testid="product-title"]').first.wait_for(timeout=30000)
    store_locator = page.locator('[data-testid="iceberg-fulfillment-trigger"]')
    store_locator.wait_for(timeout=30000)
    store = store_locator.inner_text().strip()
    if not store:
        raise ValueError('Could not identify the selected store')
    if rules.get('expected_store') and store.casefold() != rules['expected_store'].casefold():
        raise ValueError(f"Expected {rules['expected_store']}, but page selected {store}")
    cards = {}
    stable = 0
    for _ in range(rules['max_scrolls']):
        previous = len(cards)
        for card in page.evaluate(EXTRACT_CARDS):
            url = urlparse(card['product_url'])
            if url.hostname in {'www.loblaws.ca', 'loblaws.ca'} and '/p/' in url.path:
                cards[card['product_url']] = card
        stable = stable + 1 if len(cards) == previous else 0
        if stable >= 3:
            break
        page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
        page.wait_for_timeout(2000)
    if store_locator.inner_text().strip() != store:
        raise ValueError('Store changed during collection; refusing mixed-store output')
    return list(cards.values()), store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rules', default='milk_rules.json')
    parser.add_argument('--output', default='output/StorePrices.csv')
    parser.add_argument('--headed', action='store_true')
    args = parser.parse_args()
    rules = load_rules(args.rules)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not args.headed)
        try:
            page = browser.new_page(locale='en-CA')
            cards, store = collect_cards(page, rules)
        finally:
            browser.close()
    rows = select_cheapest(cards, rules, store)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.with_suffix('.candidates.json').write_text(
        json.dumps({'store': store, 'cards': cards, 'selected': rows}, indent=2), encoding='utf-8')
    if len(rows) != len(rules['sizes_ml']):
        raise ValueError('Not every size has a qualifying product. See candidates JSON; previous CSV unchanged.')
    write_output(output, rows)
    print(f'Collected {len(cards)} distinct products at {store}. Wrote {len(rows)} selected rows to {output}.')
    print('These are the cheapest qualifying collected results, not a guarantee of complete store coverage.')
    for row in rows:
        print(f"{row['category']} {row['size']}: {row['brand']} {row['name']} CAD {row['price']}")


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(f'Scrape failed: {error}', file=sys.stderr)
        sys.exit(1)
