"""Read Loblaws search cards and the selected store."""
import re
from decimal import Decimal
from urllib.parse import urlencode, urlparse

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

def search(page, store_config, search_term):
    url = store_config['website'] + '/en/search?' + urlencode({'search-bar': search_term})
    response = page.goto(url, wait_until='domcontentloaded', timeout=45000)
    if response and response.status >= 400:
        raise ValueError(f'Search returned HTTP {response.status}')
    page.locator('[data-testid="product-title"]').first.wait_for(timeout=30000)
    store_locator = page.locator('[data-testid="iceberg-fulfillment-trigger"]')
    store_locator.wait_for(timeout=30000)
    store = store_locator.inner_text().strip()
    if not store:
        raise ValueError('Could not identify the selected store')
    if store_config.get('expected_store') and store.casefold() != store_config['expected_store'].casefold():
        raise ValueError(f"Expected {store_config['expected_store']}, but page selected {store}")
    cards = {}
    stable = 0
    for _ in range(store_config.get('max_scrolls', 12)):
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
    products = []
    for card in cards.values():
        price = single_price(card)
        if price is not None:
            products.append({
                'name': card['name'], 'brand': card['brand'],
                'size': card['size'], 'price': str(price), 'currency': 'CAD',
                'available': card['available'], 'product_id': card['product_id'],
                'product_url': card['product_url'], 'image_url': card['image_url'],
            })
    return products, store
