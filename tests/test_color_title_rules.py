import unittest
from color_title_rules import decide_color
class TestTitleColor(unittest.TestCase):
 def test_blue_flame(self):self.assertEqual(decide_color('Blue Flame Bowling Shirt')[0],'Blue')
 def test_variant_suffix(self):self.assertEqual(decide_color('Bowling Polo Shirt, Polo / XL / Blue')[0],'Blue')
 def test_aop_gradient_palette(self):self.assertEqual(decide_color('Black and red gradient Womens golf polo shirts')[0],'Black/Red')
 def test_black_labrador(self):self.assertEqual(decide_color('Black Labrador Hunting Shirt')[0],'')
 def test_gloves_background(self):self.assertEqual(decide_color('Golf gloves with blue watercolor background')[0],'')
 def test_shopify_title_mismatch(self):self.assertEqual(decide_color('Black and blue leopard Bowling Jersey','Different red animal shirt')[0],'')
 def test_four_colors_ambiguous(self):self.assertEqual(decide_color('Blue Turquoise Flame pattern Black and White Kid golf polos shirts')[0],'')
 def test_unverified(self):self.assertEqual(decide_color('Blue Flame Bowling Shirt',verified=False)[0],'')
if __name__=='__main__':unittest.main()
