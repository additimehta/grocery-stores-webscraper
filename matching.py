"""Product matching and price comparisons, independent of the store website."""
import re
from decimal import Decimal, InvalidOperation


def normalize_name(name):
    return ' '.join(name.casefold().split())


def parse_size(label):
    """Return quantity and base unit. Ignore the unit-price text after a comma."""
    match = re.fullmatch(
        r'(\d+(?:\.\d+)?)\s*(ml|millilitres?|l|litres?|liters?|g|grams?|kg|kilograms?|ea|count|dozen|bags?)',
        label.split(',')[0].strip().casefold())
    if not match:
        return None
    amount, unit = Decimal(match[1]), match[2]
    if unit in ('l', 'litre', 'litres', 'liter', 'liters'):
        return amount * 1000, 'ml'
    if unit in ('kg', 'kilogram', 'kilograms'):
        return amount * 1000, 'g'
    if unit == 'dozen':
        return amount * 12, 'count'
    if unit in ('ea', 'count', 'bag', 'bags'):
        return amount, 'count'
    return amount, 'ml' if unit.startswith('m') else 'g'


def comparison_price(product, rule):
    """Return a comparable price, or None when a candidate does not qualify."""
    allowed = {normalize_name(name) for name in rule['allowed_names']}
    if not product.get('available') or normalize_name(product['name']) not in allowed:
        return None
    size = parse_size(product['size'])
    comparison = rule['comparison']
    if size is None or size[1] != comparison['unit'] or size[0] <= 0:
        return None
    try:
        price = Decimal(str(product['price']))
    except (InvalidOperation, ValueError):
        return None
    if not price.is_finite() or price <= 0 or product.get('currency') != 'CAD':
        return None
    amount = size[0]
    target = Decimal(str(comparison['amount']))
    if comparison['mode'] == 'exact':
        return price if amount == target else None
    lower = Decimal(str(comparison['min_amount']))
    upper = Decimal(str(comparison['max_amount']))
    if not lower <= amount <= upper:
        return None
    return price * target / amount


def select_cheapest(products, rule):
    """Compare unrounded prices; break ties by brand and product ID."""
    matches = []
    for product in products:
        price = comparison_price(product, rule)
        if price is not None:
            matches.append((price, product['brand'], product['product_id'], product))
    if not matches:
        return None
    price, _, _, product = min(matches, key=lambda item: item[:3])
    return product, price
