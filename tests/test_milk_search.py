import copy
import json
import unittest
from pathlib import Path
from milk_search import select_cheapest, single_price, size_ml

RULES = json.loads((Path(__file__).parents[1] / 'milk_rules.json').read_text())


def card(size='1 l', price='$3.64', **changes):
    result = dict(name='2% Milk', brand='Neilson', size=size, regular=price,
                  sale='', non_member='', offer_text=price, card_text=price,
                  available=True, product_id='test', product_url='https://www.loblaws.ca/en/test/p/test', image_url='')
    result.update(changes)
    return result


class MilkTests(unittest.TestCase):
    def test_live_observed_prices_separate_sizes(self):
        # Names, package sizes and prices observed on the live search, Oct 1 2026.
        rows = select_cheapest([card('4 l, $0.16/100ml', '$6.44'),
            card('1 l, $0.36/100ml', '$3.64'), card('2 l, $0.27/100ml', '$5.48')], RULES, 'Loblaws Baseline Road')
        self.assertEqual([(r['size'], r['price']) for r in rows], [('1 litre', '3.64'), ('4 litres', '6.44')])
        self.assertTrue(all(r['store'] == 'Loblaws Baseline Road' for r in rows))

    def test_cheapest_brand_wins_per_size(self):
        rows = select_cheapest([card(), card(price='$2.99', brand='Other'),
                               card('4 l', '$6.44')], RULES, 'Test store')
        self.assertEqual(rows[0]['brand'], 'Other')
        self.assertEqual(rows[1]['price'], '6.44')

    def test_exclude_wrong_types(self):
        for name in ['1% Milk', '3.25% Milk', '2% Chocolate Milk', '2% Almond Milk',
                     '2% Lactose Free Milk', '2% Organic Milk', '2% Microfiltered Milk', '2% Protein Milk']:
            with self.subTest(name=name):
                self.assertEqual(select_cheapest([card(name=name)], RULES, 'Store'), [])

    def test_size_normalization(self):
        self.assertEqual(size_ml('1000 ml, $0.36/100ml'), 1000)
        self.assertEqual(size_ml('4 litres'), 4000)
        self.assertIsNone(size_ml('4 x 1 l'))
        self.assertIsNone(size_ml('unknown'))

    def test_conditional_offers_and_invalid_prices(self):
        for text in ['$3.25 MIN 2', '2 for $5.00', '$2.00 members only', '$0.00', '']:
            with self.subTest(text=text):
                self.assertIsNone(single_price(card(price=text, offer_text=text, card_text=text)))
        self.assertIsNone(single_price(card(non_member='$4.00')))

    def test_unconditional_sale(self):
        self.assertEqual(str(single_price(card(sale='sale: $2.99', offer_text='sale: $2.99 was $3.64'))), '2.99')

    def test_unavailable_and_missing_size(self):
        self.assertEqual(select_cheapest([card(available=False), card(size='')], RULES, 'Store'), [])


if __name__ == '__main__':
    unittest.main()
