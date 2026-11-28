"""Fetch verified Shopify descriptions for unknown Color/Pattern; no writes to Shopify/GMC.
Rate-limit volume with --limit. Existing evidence cache survives incremental runs.
"""
import argparse,csv,json,re,collections
from pathlib import Path
from live import shopify_graphql
from material_sheet_sync import load_csv,export_csv
from engine import plain,is_missing_color

FIELDS=['item_id','product_id','variant_id','shopify_title','product_type','description','selected_color','selected_options','evidence_status']
OFFER=re.compile(r'^shopify_[A-Za-z]{2}_(\d+)_(\d+)$')

def refetch(out,limit=500):
    out=Path(out);path=out/'attribute_shopify_evidence.csv'
    existing={r['item_id']:r for r in load_csv(path)} if path.exists() else {}
    rows=load_csv(out/'audit.csv')
    eligible=[r for r in rows if r.get('shopify_status')=='SHOPIFY_VERIFIED' and
              (is_missing_color(r.get('current_color')) and not r.get('approved_color') or
               not r.get('current_pattern') and not r.get('approved_pattern') and r.get('pattern_qa')!='STAFF_NOT_APPLICABLE')
              and r.get('id') not in existing and OFFER.fullmatch(r['id'])]
    selected=eligible[:max(0,limit)];pids=sorted({r['shopify_product_id'] for r in selected});vids=sorted({r['shopify_variant_id'] for r in selected})
    query='''query($ids:[ID!]!){nodes(ids:$ids){... on Product {__typename id legacyResourceId title descriptionHtml productType}
     ... on ProductVariant {__typename id legacyResourceId product{legacyResourceId} selectedOptions{name value}}}}'''
    nodes={}
    for kind,ids in (('Product',pids),('ProductVariant',vids)):
        for i in range(0,len(ids),40):
            data=shopify_graphql(query,{'ids':['gid://shopify/'+kind+'/'+x for x in ids[i:i+40]]})
            for n in data.get('nodes',[]):
                if n and n.get('legacyResourceId'):nodes[(kind,str(n['legacyResourceId']))]=n
    statuses=collections.Counter()
    for r in selected:
        item=r['id'];pid=r['shopify_product_id'];vid=r['shopify_variant_id']
        p=nodes.get(('Product',pid));v=nodes.get(('ProductVariant',vid));valid=p and v and str((v.get('product') or {}).get('legacyResourceId',''))==pid
        status='VERIFIED' if valid else 'NOT_VERIFIED'
        statuses[status]+=1
        if not valid:continue  # retry later; do not persist failure as authoritative evidence
        options=v.get('selectedOptions') or []
        colors=[str(o.get('value','')).strip() for o in options if str(o.get('name','')).casefold() in ('color','colour')]
        existing[item]={'item_id':item,'product_id':pid,'variant_id':vid,'shopify_title':p.get('title') or '',
                        'product_type':p.get('productType') or '', 'description':plain(p.get('descriptionHtml') or '')[:30000],
                        'selected_color':colors[0] if len(colors)==1 else '',
                        'selected_options':' / '.join(str(o.get('name',''))+':'+str(o.get('value','')) for o in options),
                        'evidence_status':status}
    export_csv(path,list(existing.values()),FIELDS)
    summary={'eligible_total':len(eligible),'fetched_now':len(selected),'cached_total':len(existing),'result':dict(statuses),'gmc_write':False}
    (out/'attribute_shopify_refetch_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    return summary
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',default='out');p.add_argument('--limit',type=int,default=500)
    args=p.parse_args();print(json.dumps(refetch(args.out,args.limit),indent=2))
