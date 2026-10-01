import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scraper import collect, load_config, make_row, write_csv
from matching import select_cheapest


class ScraperTests(unittest.TestCase):
    def test_config_catalog(self):
        products, stores = load_config('products.json', 'stores.json')
        self.assertEqual(len(products), 3)
        self.assertEqual(stores[0]['adapter'], 'loblaws')

    def test_shared_search_and_csv_roundtrip(self):
        rules, stores = load_config('products.json', 'stores.json')
        candidates = [dict(name='2% Milk', brand='Brand, "A"', size=f'{litres} l',
            price=price, currency='CAD', available=True, product_id=str(litres),
            product_url='https://www.loblaws.ca/en/milk/p/test', image_url='')
            for litres, price in [(1,'3.64'), (4,'6.44')]]
        milk = [p for p in rules if p['category'] == 'Milk']
        with patch('scraper.loblaws.search', return_value=(candidates, 'Store')) as search:
            rows, audit, errors = collect(None, milk, stores)
        self.assertEqual(search.call_count, 1)
        self.assertEqual(errors, [])
        self.assertEqual(len(rows), 2)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'output.csv'
            write_csv(path, rows)
            with path.open(newline='') as file:
                result=list(csv.DictReader(file))
            self.assertEqual(result[0]['brand'], 'Brand, "A"')
            self.assertEqual(result[0]['package_price'], '3.64')

    def test_missing_result_reported(self):
        products, stores = load_config('products.json', 'stores.json')
        with patch('scraper.loblaws.search', return_value=([], 'Store')):
            rows, audit, errors = collect(None, products[:1], stores)
        self.assertFalse(rows)
        self.assertEqual(len(errors), 1)
