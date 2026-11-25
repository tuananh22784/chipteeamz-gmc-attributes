import unittest
from engine import extract, is_missing_color, report, plain, color_mentions
from pathlib import Path
from tempfile import TemporaryDirectory
import csv
import json

class EngineTests(unittest.TestCase):
    def test_real_design(self):
        r = extract('Custom Black and Pink Splatter Halftone Bowling Shirt', 'Made from lightweight 100% polyester fabric')
        self.assertEqual(r['proposed_color'], 'Black/Pink')
        self.assertEqual(r['proposed_pattern'], '')
        self.assertEqual(r['proposed_material'], 'Polyester')
        self.assertIn('multiple_patterns', r['review_reason'])

    def test_compound_color(self):
        r = extract('Navy Blue Red Geometric Dart Shirt', 'material: polyester')
        self.assertEqual(r['proposed_color'], 'Navy Blue/Red')
        self.assertEqual(r['proposed_pattern'], 'Geometric')

    def test_no_pattern_from_generic_description(self):
        r = extract('Funny Duck Swing Golf Polo', 'Pattern type: print. Make splatter designs available for other products.')
        self.assertEqual(r['proposed_pattern'], '')

    def test_flag_stripes_ambiguous(self):
        r = extract('Red American Flag Striped Bowling Shirt', '')
        self.assertEqual(r['proposed_pattern'], '')
        self.assertIn('pattern_flag_ambiguous', r['review_reason'])

    def test_multimaterial_block(self):
        r = extract('Unisex T-Shirt', 'Solid colors: 100% Cotton. Heather colors: 52% Cotton 48% Polyester.')
        self.assertEqual(r['proposed_material'], '')

    def test_color_option(self):
        r = extract('Custom shirt', '', selected_color='Forest Green')
        self.assertEqual(r['proposed_color'], 'Forest Green')

    def test_placeholder(self):
        self.assertTrue(is_missing_color("'One color'"))
        self.assertTrue(is_missing_color(''))
        self.assertFalse(is_missing_color('Black'))

    def test_html(self):
        self.assertEqual(plain('<p>100% <b>Polyester</b></p>'), '100% Polyester')

    def test_unverified_not_shown_as_shopify(self):
        data = [{'offerId': 'invalid', 'productAttributes': {'title':'Red shirt', 'description':'100% polyester'}}]
        with TemporaryDirectory() as folder:
            summary = report(data, folder, source='live')
            self.assertEqual(summary['shopify_unverified'], 1)
            self.assertEqual(summary['auto_fix_eligible'], 0)
            with (Path(folder)/'audit.csv').open(encoding='utf-8-sig', newline='') as f:
                row = next(csv.DictReader(f))
                self.assertEqual(row['shopify_status'], 'NOT_VERIFIED')
                self.assertEqual(row['proposed_material'], '')
                self.assertEqual(row['qa_status'], 'NEEDS_REVIEW')

if __name__ == '__main__':
    unittest.main()
