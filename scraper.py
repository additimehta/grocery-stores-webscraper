"""Export selected Loblaws product pages to CSV (initial, unverified adapter)."""
import argparse
import csv
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

FIELDS = ["category", "name", "price", "currency", "size", "brand",
          "product_id", "image_url", "product_url", "retailer", "scraped_at"]


def product_objects(value):
    if isinstance(value, list):
        for item in value:
            yield from product_objects(item)
    elif isinstance(value, dict):
        types = value.get("@type", [])
        if "Product" in (types if isinstance(types, list) else [types]):
            yield value
        # Do not collect related products from arbitrary nested page data.
        yield from product_objects(value.get("@graph", []))


def parse_product(blocks, target):
    candidates = []
    for block in blocks:
        try:
            candidates.extend(product_objects(json.loads(block)))
        except (ValueError, TypeError):
            continue
    expected_id = urlparse(target["url"]).path.rstrip("/").split("/")[-1]
    matches = [p for p in candidates if str(p.get("sku", "")) == expected_id
               or str(p.get("productID", "")) == expected_id
               or urlparse(str(p.get("url", ""))).path.rstrip("/")
               == urlparse(target["url"]).path.rstrip("/")]
    if len(matches) == 1:
        product = matches[0]
    elif len(candidates) == 1:
        product = candidates[0]
        declared_id = product.get("sku") or product.get("productID")
        if declared_id and str(declared_id) != expected_id:
            raise ValueError("Page product ID does not match the requested product")
    else:
        raise ValueError("No unambiguous Product JSON-LD found; page adapter needs inspection")
    offers = product.get("offers", [])
    offers = offers if isinstance(offers, list) else [offers]
    # Do not substitute aggregate low prices or invent a missing price.
    priced = [o for o in offers if isinstance(o, dict) and o.get("price") is not None]
    if len(priced) != 1:
        raise ValueError("Expected one explicit product offer; found missing or ambiguous prices")
    offer = priced[0]
    price = float(offer["price"])
    if not math.isfinite(price) or price < 0 or not product.get("name"):
        raise ValueError("Invalid product name or price")
    brand = product.get("brand", "")
    if isinstance(brand, dict):
        brand = brand.get("name", "")
    image = product.get("image", "")
    if isinstance(image, list):
        image = image[0] if image else ""
    if isinstance(image, dict):
        image = image.get("url", "")
    size = product.get("size", "")
    if not isinstance(size, (str, int, float)):
        size = ""
    return dict(zip(FIELDS, [target.get("category", ""), product["name"],
        format(price, ".2f"), offer.get("priceCurrency", ""), size, brand,
        product.get("sku") or product.get("productID", ""), image, target["url"],
        "Loblaws", datetime.now(timezone.utc).isoformat()]))


def write_csv(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def load_targets(path):
    targets = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(targets, list) or not targets:
        raise ValueError("Products file must contain a nonempty JSON list")
    for target in targets:
        if not isinstance(target, dict):
            raise ValueError("Each product must contain a URL")
        url = urlparse(target.get("url", ""))
        if (url.scheme != "https" or url.hostname not in {"www.loblaws.ca", "loblaws.ca"}
                or "/p/" not in url.path):
            raise ValueError("Use HTTPS Loblaws product URLs containing /p/")
    return targets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--products", default="products.json")
    parser.add_argument("--output", default="output/GroceryData.csv")
    parser.add_argument("--headed", action="store_true", help="Show the browser")
    args = parser.parse_args()
    targets = load_targets(args.products)
    from playwright.sync_api import sync_playwright

    rows, errors = [], []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not args.headed)
        try:
            page = browser.new_page(locale="en-CA")
            for index, target in enumerate(targets):
                if index:
                    time.sleep(2)
                try:
                    response = page.goto(target["url"], wait_until="domcontentloaded", timeout=30000)
                    if response and response.status >= 400:
                        raise ValueError(f"HTTP {response.status}; site may be blocking access")
                    page.wait_for_function('''() => [...document.querySelectorAll(
                        'script[type="application/ld+json"]')].some(s => s.textContent.includes('Product'))''',
                        timeout=20000)
                    blocks = page.locator('script[type="application/ld+json"]').all_text_contents()
                    rows.append(parse_product(blocks, target))
                    print(f"Saved: {rows[-1]['name']}")
                except Exception as error:
                    errors.append({"url": target["url"], "error": str(error)})
                    print(f"Failed: {target['url']}: {error}", file=sys.stderr)
        finally:
            browser.close()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.with_suffix(".errors.json").write_text(json.dumps(errors, indent=2), encoding="utf-8")
    if rows:
        write_csv(output, rows)
        print(f"Exported {len(rows)}/{len(targets)} products to {output}")
    else:
        print("No products extracted. Any existing CSV was left unchanged.", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, ImportError) as error:
        print(error, file=sys.stderr)
        sys.exit(1)
