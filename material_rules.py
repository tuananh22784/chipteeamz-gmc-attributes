"""Read-only subtype-to-composition enrichment. Does not change the V1.3 audit schema/checkpoint."""
import argparse
import collections
import csv
import json
import re
import unicodedata
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def normalized(value):
    s=unicodedata.normalize('NFKC',str(value or '')).translate(str.maketrans({'’':"'",'‘':"'",'–':'-','—':'-'})).lower().strip()
    s=re.sub(r"\bmen\s*'s\b",'men',s)
    s=re.sub(r"\bwomen\s*'s\b",'women',s)
    s=re.sub(r'\bman\b','men',s)
    s=re.sub(r'\bkids\b','kid',s)
    s=re.sub(r'\blong sleeves\b','long sleeve',s)
    s=re.sub(r'\bshort sleeves\b','short sleeve',s)
    s=re.sub(r'\bzip[ -]?up\b','zip up',s)
    s=re.sub(r'\bquarter[ -]?zip\b','quarter zip',s)
    s=re.sub(r'\bt[ -]?shirt\b','t shirt',s)
    return re.sub(r'\s+',' ',s).strip()

def load_rules(master=ROOT/'material_master.csv',aliases=ROOT/'material_aliases.csv'):
    result={}
    with open(master,encoding='utf-8-sig',newline='') as f:
        for row in csv.DictReader(f):
            key=normalized(row['style'])
            if key in result and result[key]['fabric_composition']!=row['fabric_composition']:
                raise ValueError('Conflicting fabric rules for '+key)
            result[key] = {**row, 'match_type':'MASTER_EXACT'}
    with open(aliases,encoding='utf-8-sig',newline='') as f:
        for row in csv.DictReader(f):
            key=normalized(row['alias'])
            record={'style':row['target_style'],'rule_id':row['rule_id'],
                    'fabric_composition':row['fabric_composition'],'source_row':'',
                    'match_type':'ALIAS_EXACT'}
            if key in result and result[key]['fabric_composition']!=record['fabric_composition']:
                raise ValueError('Conflicting alias fabric rule '+key)
            result[key]=record
    return result

REPORT_FIELDS=['id','language','feed_label','shopify_status','variant_style','current_material',
               'v13_proposed_material','matched_subtype','material_rule_id','source_row',
               'material_source','material_candidate','material_decision','material_reason']

def assess(row,rules):
    style=(row.get('variant_style') or '').strip()
    current=(row.get('current_material') or '').strip()
    result={
        'id':row.get('id',''), 'language':row.get('language',''), 'feed_label':row.get('feed_label',''),
        'shopify_status':row.get('shopify_status',''), 'variant_style':style,
        'current_material':current,'v13_proposed_material':row.get('proposed_material',''),
        'matched_subtype':'','material_rule_id':'','source_row':'',
        'material_source':'','material_candidate':'','material_decision':'','material_reason':''}
    if row.get('shopify_status') != 'SHOPIFY_VERIFIED':
        result.update(material_decision='REVIEW_UNVERIFIED_SHOPIFY',material_reason='Product and variant identity not verified')
        return result
    if current:
        result.update(material_decision='KEEP_EXISTING',material_reason='Existing GMC material preserved; no overwrite')
        return result
    if not style:
        result.update(material_decision='REVIEW_MISSING_STYLE',material_reason='No verified Shopify style option')
        return result
    # Combined styles, e.g. Long sleeves UPF + Face shield, cannot be represented by one composition.
    if '+' in style or '/' in style or ',' in style:
        result.update(material_decision='REVIEW_COMPOSITE_STYLE',material_reason='One variant style names multiple components or has multiple selections')
        return result
    rule=rules.get(normalized(style))
    if not rule:
        result.update(material_decision='REVIEW_UNMAPPED_SUBTYPE',material_reason='No exact approved style or explicit alias')
        return result
    result.update(matched_subtype=rule['style'],material_rule_id=rule['rule_id'],
                  source_row=rule['source_row'],material_source='USER_FABRIC_COMPOSITION_MASTER',
                  material_candidate=rule['fabric_composition'],
                  material_decision='MASTER_VERIFIED_READ_ONLY',
                  material_reason='Exact style or approved alias ('+rule['match_type']+')')
    return result

def process(audit_path,out_dir):
    out=Path(out_dir);out.mkdir(parents=True,exist_ok=True)
    rules=load_rules()
    counts=collections.Counter()
    with open(audit_path,encoding='utf-8-sig',newline='') as f, \
         open(out/'material_mapping_review.csv','w',encoding='utf-8-sig',newline='') as g, \
         open(out/'material_master_candidates.csv','w',encoding='utf-8-sig',newline='') as h:
        writer=csv.DictWriter(g,fieldnames=REPORT_FIELDS);writer.writeheader()
        candidate_writer=csv.DictWriter(h,fieldnames=REPORT_FIELDS);candidate_writer.writeheader()
        for row in csv.DictReader(f):
            finding=assess(row,rules)
            writer.writerow(finding)
            counts[finding['material_decision']]+=1
            if finding['material_decision']=='MASTER_VERIFIED_READ_ONLY':
                candidate_writer.writerow(finding)
    summary={'source':'Fabric Composition - Sheet1.csv','master_styles':56,
             'explicit_aliases':sum(1 for r in rules.values() if r['match_type']=='ALIAS_EXACT'),
             'total_rows':sum(counts.values()),'decisions':dict(counts),
             'write_mode':'READ_ONLY','note':'Does not alter audit.csv or Shopify/GMC. Candidate names are composition values from supplied sheet.'}
    (out/'material_mapping_summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
    return summary

def main():
    p=argparse.ArgumentParser();p.add_argument('--audit',default='out/audit.csv');p.add_argument('--out',default='out')
    args=p.parse_args();print(json.dumps(process(args.audit,args.out),indent=2))
if __name__=='__main__':main()
