"""Refetch only unresolved Shirt/Jersey from Shopify; no GMC/Shopify writes.

Evidence must identify exact Shopify product + variant. Description/type matching is
conservative: generic 'shirt', 'jersey', theme, or a material keyword alone is insufficient.
"""
from __future__ import annotations
import argparse,csv,json,re,collections
from pathlib import Path
from live import shopify_descriptions
from engine import plain

EVIDENCE_FILE='shirt_jersey_style_evidence.csv'
FIELDS=['id','shopify_product_id','shopify_variant_id','status','product_type','shopify_title','variant_style','resolved_style','decision','evidence_source','evidence_excerpt']

def classify(shopify_title,product_type,description,variant_style=''):
    """Return exact Master subtype only for reliable matches, else review."""
    # No broad assumptions about bowling vs cycling jerseys or all shirts being cotton.
    if variant_style:
        return '', 'VARIANT_STYLE_FOUND_REVIEW', 'Shopify now exposes a style option; manually reconcile with audit'
    title=(shopify_title or '').lower()
    typ=(product_type or '').lower().strip()
    desc=plain(description or '').lower()
    candidates=[]
    # Product type is stronger than marketing title; description only if a labeled statement.
    for source,text in [('PRODUCT_TYPE',typ),('SHOPIFY_TITLE',title)]:
        if not text:continue
        # Need product-category evidence instead of an incidental word in advertising copy.
        if re.search(r'\b(cycling jersey|bike jersey|bicycle jersey)\b',text):
            candidates.append(('Men Short Sleeve Cycling Jersey',source+' cycling jersey')) if re.search(r'\b(men|male)\b',text) and re.search(r'\bshort[ -]?sleeve\b',text) else None
        if re.search(r'\b(bowling jersey|bowling jerseys)\b',text):
            return '', 'BOWLING_JERSEY_REVIEW', source+' bowling jersey: no equivalent fabric master'
        if re.search(r'\b(t[- ]shirts?|tee shirts?|tshirts?)\b',text):
            candidates.append(('T-shirt',source+' t-shirt'))
        if re.search(r'\b(short[ -]?sleeve polo|polo shirt)\b',text) and not re.search(r'\b(long[ -]?sleeve|sleeveless)\b',text):
            candidates.append(('Men Short sleeve polo shirt',source+' polo'))
        if re.search(r'\b(crew[ -]?neck sweatshirt|standard sweatshirt)\b',text):
            candidates.append(('Sweatshirt',source+' sweatshirt'))
    # Description is lower reliability; accept only labeled style/type fields.
    for match in re.finditer(r'(?im)(?:^|[\n\r])\s*(?:product\s*type|garment\s*type|style)\s*:\s*([^\n\r]{1,100})',desc):
        text=match.group(1)
        if re.search(r'\b(t[- ]shirts?|tee shirts?|tshirts?)\b',text):candidates.append(('T-shirt','LABELED_DESCRIPTION t-shirt'))
        if re.search(r'\bshort[ -]?sleeve polo\b',text):candidates.append(('Men Short sleeve polo shirt','LABELED_DESCRIPTION polo'))
        if re.search(r'\bcrew[ -]?neck sweatshirt\b',text):candidates.append(('Sweatshirt','LABELED_DESCRIPTION sweatshirt'))
    unique={c[0] for c in candidates}
    if len(unique)==1:
        return candidates[0][0], 'EXPLICIT_STYLE', '; '.join(c[1] for c in candidates)
    if len(unique)>1:
        return '', 'CONFLICTING_STYLE_REVIEW', '; '.join(c[1] for c in candidates)
    return '', 'NO_VERIFIED_SUBTYPE', 'No explicit matching garment subtype in product type/title/labeled description'

def fetch(out):
    out=Path(out)
    pending=[]
    with (out/'audit.csv').open(encoding='utf-8-sig',newline='') as f:
        for x in csv.DictReader(f):
            if x.get('material_decision')=='REVIEW_MISSING_STYLE' and x.get('style_resolution_status') in ('TITLE_INSUFFICIENT','AMBIGUOUS_JERSEY'):
                pending.append(x)
    records=[{'offerId':r['id'],'productAttributes':{}} for r in pending]
    for s in range(0,len(records),40):shopify_descriptions(records[s:s+40])
    results=[]
    for r,p in zip(pending,records):
        verified=(p.get('_shopify_status')=='SHOPIFY_VERIFIED' and str(p.get('_shopify_product_id'))==str(r['shopify_product_id']) and str(p.get('_shopify_variant_id'))==str(r['shopify_variant_id']))
        typ=p.get('_shopify_product_type','')
        title=p.get('_shopify_title','')
        desc=(p.get('productAttributes') or {}).get('description','')
        style=p.get('_variant_style','')
        if verified:
            subtype,decision,why=classify(title,typ,desc,style)
        else:
            subtype,decision,why='', 'UNVERIFIED_SHOPIFY','Exact product and variant not verified'
        results.append({'id':r['id'],'shopify_product_id':r['shopify_product_id'],'shopify_variant_id':r['shopify_variant_id'],
                        'status':'SHOPIFY_VERIFIED' if verified else p.get('_shopify_status','NOT_VERIFIED'),
                        'product_type':typ,'shopify_title':title,'variant_style':style,
                        'resolved_style':subtype,'decision':decision,'evidence_source':'SHOPIFY_EXACT_VARIANT' if verified else '',
                        'evidence_excerpt':why})
    path=out/EVIDENCE_FILE
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows(results)
    counts=collections.Counter(x['decision'] for x in results)
    summary={'targeted':len(results),'decisions':dict(counts),'gmc_write':False,'checkpoint_modified':False}
    (out/'shirt_jersey_refetch_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))
    return results
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',default='out');fetch(p.parse_args().out)
