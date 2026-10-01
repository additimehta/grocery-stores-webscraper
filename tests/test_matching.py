import json
import unittest
from pathlib import Path
from matching import parse_size, select_cheapest
from stores.loblaws import single_price

RULES = {p['id']: p for p in json.loads(Path('products.json').read_text())}


def product(size, price, name='2% Milk', **changes):
    result = dict(name=name, brand='Test', product_id='a', size=size,
                  price=price, currency='CAD', available=True)
    result.update(changes)
    return result


class MatchingTests(unittest.TestCase):
    def test_milk_sizes_and_types(self):
        candidates = [product('2 l', '1.00'), product('1 l', '3.64'),
                      product('4 l', '6.44'), product('1 l', '0.99', 'Almond Milk')]
        self.assertEqual(select_cheapest(candidates, RULES['milk_1_litre'])[0]['price'], '3.64')
        self.assertEqual(select_cheapest(candidates, RULES['milk_4_litres'])[0]['price'], '6.44')

    def test_cheddar_uses_normalized_price(self):
        candidates = [product('400 g', '4.00', 'Mild Cheddar Cheese'),
                      product('800 g', '7.00', 'Old Cheddar Cheese')]
        chosen, price = select_cheapest(candidates, RULES['block_cheese_500_grams'])
        self.assertEqual(chosen['size'], '800 g')
        self.assertEqual(str(price), '4.375')
        self.assertEqual(chosen['price'], '7.00')

    def test_cheddar_exclusions(self):
        candidates = [product('300 g', '1', 'Cheddar Cheese'),
                      product('900 g', '1', 'Cheddar Cheese'),
                      product('500 g', '1', 'Shredded Cheddar Cheese'),
                      product('500 g', '1', 'Jalapeno Cheddar Cheese')]
        self.assertIsNone(select_cheapest(candidates, RULES['block_cheese_500_grams']))

    def test_units_and_multipacks(self):
        self.assertEqual(parse_size('1 l, $0.36/100ml'), (1000, 'ml'))
        self.assertEqual(parse_size('0.5 kg'), (500, 'g'))
        self.assertEqual(parse_size('1 dozen'), (12, 'count'))
        self.assertIsNone(parse_size('4 x 1 l'))

    def test_invalid_unavailable_currency(self):
        for updates in [{'price':'NaN'}, {'price':'0'}, {'available':False}, {'currency':'USD'}]:
            self.assertIsNone(select_cheapest([product('1 l','2.00',**updates)] if 'price' not in updates
                else [product('1 l',updates['price'])], RULES['milk_1_litre']))

    def test_offer_conditions(self):
        self.assertIsNone(single_price({'regular':'$3.00', 'offer_text':'MIN 2'}))
        self.assertIsNone(single_price({'sale':'$2.00', 'non_member':'$4.00'}))
        self.assertEqual(str(single_price({'sale':'sale: $2.99'})), '2.99')
