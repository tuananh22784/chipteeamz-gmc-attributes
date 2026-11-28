import unittest
from pattern_title_description_rules import title_pattern,description_pattern
class TestV1354(unittest.TestCase):
 def test_multi_first(self):
  self.assertEqual(title_pattern('Splatter Halftone Bowling Shirt')[0],'Splatter')
  self.assertEqual(title_pattern('Argyle Plaid Shirt')[0],'Argyle')
 def test_species(self):
  self.assertEqual(title_pattern('Striped Bass Shirt')[0],'')
  self.assertEqual(title_pattern('Striped Bass Camouflage Fishing Jersey')[0],'Camouflage')
 def test_seo(self):
  self.assertEqual(description_pattern('This design appeals to abstract art lovers.')[0],'Abstract')
 def test_avoid_site_boilerplate(self):
  self.assertEqual(description_pattern('Browse our collection of abstract patterns.')[0],'')
 def test_reflective_stripes_not_pattern(self):
  self.assertEqual(description_pattern('Style: Sport. Anti-slip silicone strip. Back reflective stripes for night visibility.')[0],'')
 def test_title_first_conflict(self):
  self.assertEqual(title_pattern('Camouflage Abstract Shirt')[0],'Camouflage')
