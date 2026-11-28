import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from attribute_sheet_sync import strict_auto_candidates,validate_auto_evidence,auto_apply_verified_color,reconcile_legacy_pattern_source
class TestEvidenceIntegrity(unittest.TestCase):
 def base(self):
  return {'id':'shopify_US_10_20','shopify_product_id':'10','shopify_variant_id':'20','shopify_status':'SHOPIFY_VERIFIED','current_color':'One color','current_pattern':'','approved_color':'','approved_pattern':'','review_reason':'pattern_not_explicit_in_title'}
 def evidence(self,**kw):
  e={'product_id':'10','variant_id':'20','evidence_status':'VERIFIED','shopify_title':'Argyle Pattern Bowling Shirt','description':'Garment color: Navy Blue.'}
  e.update(kw);return {'shopify_US_10_20':e}
 def test_title_source_and_real_text(self):
  r=self.base();trace={};count=strict_auto_candidates([r],self.evidence(),trace)
  self.assertEqual(count,{'COLOR':1,'PATTERN':1})
  self.assertEqual(r['pattern_qa'],'PATTERN_EXPLICIT_TITLE_VERIFIED')
  self.assertEqual(trace[(r['id'],'PATTERN')]['evidence_text'],'Argyle Pattern Bowling Shirt')
  changes=[]
  for a in ('COLOR','PATTERN'):
   t=trace[(r['id'],a)];changes.append({'item_id':r['id'],'attribute':a,'qa_status':r[a.lower()+'_qa'],'new_value':r['approved_'+a.lower()],**t})
  validate_auto_evidence([r],changes)
 def test_description_source_not_title(self):
  r=self.base();trace={};strict_auto_candidates([r],self.evidence(shopify_title='Bowling Shirt',description='Pattern: plaid. Garment color: Black.'),trace)
  self.assertEqual(r['pattern_qa'],'PATTERN_EXPLICIT_DESCRIPTION_VERIFIED')
  self.assertEqual(trace[(r['id'],'PATTERN')]['evidence_source'],'DESCRIPTION')
 def test_conflicting_sources_block(self):
  r=self.base();trace={};x=strict_auto_candidates([r],self.evidence(description='Pattern: plaid.'),trace)
  self.assertEqual(x['PATTERN'],0)
 def test_mismatch_raises(self):
  r=self.base();trace={};strict_auto_candidates([r],self.evidence(),trace)
  change={'item_id':r['id'],'attribute':'PATTERN','qa_status':'PATTERN_EXPLICIT_DESCRIPTION_VERIFIED','new_value':'Argyle',**trace[(r['id'],'PATTERN')]}
  with self.assertRaisesRegex(ValueError,'AUTO_EVIDENCE_MISMATCH'):validate_auto_evidence([r],[change])
 def test_variant_still_works(self):
  r=self.base();trace={};count=auto_apply_verified_color([r],self.evidence(selected_color='Forest'),trace)
  self.assertEqual(count,1)
  self.assertEqual(r['approved_color'],'Forest')
  self.assertEqual(trace[(r['id'],'COLOR')]['evidence_source'],'VARIANT')
 def test_repair_previous_title_label_with_actual_shopify_evidence(self):
  r=self.base();r.update(approved_pattern='Argyle',pattern_qa='PATTERN_EXPLICIT_DESCRIPTION_VERIFIED',pattern_evidence='SHOPIFY_TITLE_EXPLICIT_PATTERN')
  report=reconcile_legacy_pattern_source([r],self.evidence())
  self.assertEqual(r['approved_pattern'],'Argyle')
  self.assertEqual(r['pattern_qa'],'PATTERN_EXPLICIT_TITLE_VERIFIED')
  self.assertEqual(report[0]['decision'],'REPAIRED_LABEL_WITH_SHOPIFY_TITLE')
 def test_quarantine_unverifiable_legacy_approval(self):
  r=self.base();r.update(approved_pattern='Argyle',pattern_qa='PATTERN_EXPLICIT_DESCRIPTION_VERIFIED',pattern_evidence='SHOPIFY_TITLE_EXPLICIT_PATTERN')
  report=reconcile_legacy_pattern_source([r],self.evidence(shopify_title='Yellow Argyle Outfit with Leopard'))
  self.assertEqual(r['approved_pattern'],'')
  self.assertEqual(r['proposed_pattern'],'Argyle')
  self.assertEqual(r['pattern_qa'],'PATTERN_SOURCE_RECHECK_REQUIRED')
  self.assertEqual(report[0]['decision'],'QUARANTINED_UNVERIFIED_TITLE_SOURCE')
 def test_identity_mismatch_blocks(self):
  r=self.base();trace={};count=strict_auto_candidates([r],self.evidence(variant_id='999'),trace)
  self.assertEqual(count,{'COLOR':0,'PATTERN':0})
  self.assertFalse(trace)
if __name__=='__main__':unittest.main()
