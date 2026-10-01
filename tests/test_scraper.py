import csv
import json
import tempfile
import unittest
from pathlib import Path
from scraper import parse_product, write_csv


class ScraperTests(unittest.TestCase):
    def setUp(self):
        self.target = {"category": "test", "url": "https://www.loblaws.ca/en/test/p/123_EA"}
        self.product = {"@type": "Product", "sku": "123_EA", "name": 'Test, "eggs"',
                        "offers": {"price": "4.99", "priceCurrency": "CAD"}}

    def test_graph_and_csv_roundtrip(self):
        row = parse_product([json.dumps({"@graph": [self.product]})], self.target)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "products.csv"
            write_csv(path, [row])
            with path.open(newline="", encoding="utf-8") as handle:
                result = next(csv.DictReader(handle))
            self.assertEqual(result["name"], 'Test, "eggs"')
            self.assertEqual(result["price"], "4.99")
            self.assertEqual(result["size"], "")

    def test_missing_price_is_not_zero(self):
        self.product["offers"] = {}
        with self.assertRaises(ValueError):
            parse_product([json.dumps(self.product)], self.target)

    def test_wrong_product_rejected(self):
        self.product["sku"] = "456_EA"
        with self.assertRaises(ValueError):
            parse_product([json.dumps(self.product)], self.target)

    def test_app_shell_rejected(self):
        with self.assertRaises(ValueError):
            parse_product([], self.target)


if __name__ == "__main__":
    unittest.main()
