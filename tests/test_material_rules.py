import unittest
from material_rules import load_rules,assess

class MaterialRulesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.rules=load_rules()
    def find(self,style,verified='SHOPIFY_VERIFIED',material=''):
        return assess({'id':'test','variant_style':style,'shopify_status':verified,'current_material':material},self.rules)
    def test_long_sleeve_upf(self):
        self.assertEqual(self.find('Long sleeves UPF')['material_candidate'],'100% polyester')
    def test_basic_hoodie_is_cotton(self):
        self.assertEqual(self.find('Hoodie')['material_candidate'],'Cotton')
    def test_air_layer_hoodie_is_polyester(self):
        self.assertEqual(self.find('220g air layer Hoodie')['material_candidate'],'100% polyester')
    def test_zip_hoodie_not_assumed_cotton_or_air_layer(self):
        self.assertEqual(self.find('Zip up hoodie')['material_decision'],'REVIEW_UNMAPPED_SUBTYPE')
    def test_face_shield(self):
        self.assertEqual(self.find('Face Shield')['material_candidate'],'95% polyester+5% spandex')
    def test_leggings(self):
        self.assertEqual(self.find('Leggings')['material_candidate'],'96% polyester+4% spandex')
    def test_tshirt_upf_and_plain_differ(self):
        self.assertEqual(self.find('T-shirt UPF')['material_candidate'],'100% polyester')
        self.assertEqual(self.find('T-shirt')['material_candidate'],'Cotton')
    def test_no_inference_compound(self):
        self.assertEqual(self.find('Long sleeves UPF + Face shield')['material_decision'],'REVIEW_COMPOSITE_STYLE')
    def test_unverified_block(self):
        self.assertEqual(self.find('Hoodie',verified='UNMATCHED_OFFER_ID')['material_decision'],'REVIEW_UNVERIFIED_SHOPIFY')
    def test_existing_material_untouched(self):
        self.assertEqual(self.find('Hoodie',material='Linen')['material_decision'],'KEEP_EXISTING')
    def test_no_guess(self):
        self.assertEqual(self.find('Women Polo shirt')['material_decision'],'REVIEW_UNMAPPED_SUBTYPE')
if __name__=='__main__':unittest.main()
