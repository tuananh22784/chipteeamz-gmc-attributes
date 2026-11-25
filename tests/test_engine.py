import unittest,sys,os
sys.path.insert(0,os.path.dirname(os.path.dirname(__file__)))
from engine import extract,is_missing_color,parse_item
class TestEngine(unittest.TestCase):
 def test_real_example(self):
  e=extract('Custom Black and Pink Splatter Halftone Bowling Shirt', 'Made from lightweight 100% polyester fabric')
  self.assertEqual(e['color'],'Black/Pink')
  self.assertEqual(e['material'],'Polyester')
  self.assertFalse(e['pattern']) # multiple descriptors => needs review
 def test_false_material(self):
  self.assertEqual(extract('Custom golf shirt','Premium comfortable fabric')['material'],'')
 def test_placeholder(self):
  self.assertTrue(is_missing_color("'One color'"))
 def test_nested(self):
  d=parse_item({'offerId':'x','productAttributes':{'material':'Cotton'}})
  self.assertEqual(d['material'],'Cotton')
if __name__=='__main__':unittest.main()
