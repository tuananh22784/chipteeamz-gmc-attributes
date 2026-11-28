"""Google Sheets employee material review queue. Safe, idempotent, no GMC writes.

Tabs Pending_Material, Approved_Rules, History. Approved rules are stored persistently
in the online spreadsheet, never solely in ephemeral GitHub Actions cache.
"""
from __future__ import annotations
import argparse,csv,json,os,re,hashlib,datetime
from pathlib import Path
import requests
from material_rules import normalized as style_norm

PENDING_FIELDS=['item_id','shopify_product_id','shopify_variant_id','product_title','variant_style','resolved_style','material_decision','review_reason','scope','confirmed_style','confirmed_material','staff_note','status']
RULE_FIELDS=['rule_key','scope','item_id','style_key','confirmed_style','confirmed_material','source','approved_at']
HISTORY_FIELDS=PENDING_FIELDS+['rule_key','processed_at']
REVIEW_DECISIONS={'REVIEW_MISSING_STYLE','REVIEW_UNMAPPED_SUBTYPE','GENERIC_STYLE_REVIEW','COMPOSITE_REVIEW','CONFLICTING_PRODUCT_FAMILY','COLOR_DEPENDENT_REVIEW'}
DANGEROUS_STYLES={'shirt','shirts','jersey','jerseys','women','female','kid','kids','unisex','clothing','other',''}


def norm(text):
    return re.sub(r'[^a-z0-9]+',' ',str(text or '').lower()).strip()

def load_csv(path):
    with open(path,encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def export_csv(path,rows,fields):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)

def source_rows(audit):
    for r in load_csv(audit):
        if r.get('approved_material') or r.get('current_material') or r.get('shopify_status')!='SHOPIFY_VERIFIED':continue
        if r.get('material_decision') not in REVIEW_DECISIONS:continue
        yield r

def build_pending(audit,old_pending=(),rules=()):
    existing={r.get('item_id'):r for r in old_pending if r.get('item_id')}
    known={r['rule_key'] for r in rules}
    result=[]
    for r in source_rows(audit):
        item=r['id'];old=existing.get(item,{})
        style=r.get('style_resolved') or r.get('variant_style') or ''
        entry={'item_id':item,'shopify_product_id':r.get('shopify_product_id',''),
               'shopify_variant_id':r.get('shopify_variant_id',''),'product_title':r.get('title',''),
               'variant_style':r.get('variant_style',''),'resolved_style':style,
               'material_decision':r.get('material_decision',''),'review_reason':r.get('material_reason',''),
               'scope':old.get('scope') or 'ITEM',
               'confirmed_style':old.get('confirmed_style',''), 'confirmed_material':old.get('confirmed_material',''),
               'staff_note':old.get('staff_note',''),'status':old.get('status') or 'PENDING'}
        if rule_key(entry) in known:continue
        result.append(entry)
    return result

def rule_key(p):
    if p.get('scope','ITEM').strip().upper()=='STYLE':
        return 'STYLE:'+style_norm(p.get('confirmed_style') or p.get('resolved_style'))
    return 'ITEM:'+p['item_id']

def normalize_material(text):
    s=' '.join(str(text or '').strip().split())
    if len(s)>180 or not s:return ''
    if not re.fullmatch(r'[A-Za-z0-9%.,+ /()&-]+',s):return ''
    if s.lower() in ('yes','no','cotton?','polyester?','unknown','n/a','na','tbd','?'):return ''
    # Require meaningful fabric name and either composition percentage or known cotton shorthand.
    if not re.search(r'(?i)\b(cotton|polyester|spandex|nylon|rayon|linen|viscose|acrylic|wool|silk|elastane|polyamide)\b',s):return ''
    perc=[int(n) for n in re.findall(r'(?<!\d)(\d{1,3})\s*%',s)]
    if perc and sum(perc)!=100:return ''
    if not perc and s.casefold() not in ('cotton','polyester','nylon','wool','silk','linen'):return ''
    return s

def validate_pending(p):
    item=p.get('item_id','').strip()
    if not re.fullmatch(r'shopify_[A-Za-z]{2}_\d+_\d+',item):return 'INVALID_ITEM_ID'
    if p.get('status','').strip().upper() not in ('APPROVE','CONFIRMED'):return 'WAITING_FOR_STAFF'
    material=normalize_material(p.get('confirmed_material'))
    if not material:return 'INVALID_MATERIAL'
    style=(p.get('confirmed_style') or p.get('resolved_style') or '').strip()
    if not style:return 'STYLE_REQUIRED'
    scope=p.get('scope','ITEM').strip().upper()
    if scope not in ('ITEM','STYLE'):return 'INVALID_SCOPE'
    if scope=='STYLE':
        if norm(style) in DANGEROUS_STYLES:return 'GENERIC_STYLE_NOT_GLOBAL'
        if style_norm(style)!=style_norm(p.get('resolved_style')):return 'STYLE_SCOPE_MUST_MATCH_VERIFIED_STYLE'
    return 'VALID'

def ingest(pending,existing_rules,history):
    """Pure transaction: rule persistence before removing pending; reject conflicts."""
    seen={r['rule_key']:r for r in existing_rules if r.get('rule_key')}
    remaining=[];new_rules=[];new_history=[];stats={}
    stamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
    for p in pending:
        p=dict(p);v=validate_pending(p); key=rule_key(p)
        if v!='VALID':
            if v!='WAITING_FOR_STAFF':p['status']=v
            remaining.append(p);stats[v]=stats.get(v,0)+1;continue
        new={'rule_key':key,'scope':p.get('scope','ITEM').strip().upper(),
             'item_id':p['item_id'] if p.get('scope','ITEM').strip().upper()=='ITEM' else '',
             'style_key':style_norm(p.get('confirmed_style') or p.get('resolved_style')),
             'confirmed_style':p.get('confirmed_style') or p.get('resolved_style'),
             'confirmed_material':normalize_material(p['confirmed_material']),
             'source':'GOOGLE_SHEETS_STAFF','approved_at':stamp}
        old=seen.get(key)
        if old and (norm(old['confirmed_material'])!=norm(new['confirmed_material']) or norm(old['confirmed_style'])!=norm(new['confirmed_style'])):
            p['status']='RULE_CONFLICT';remaining.append(p);stats['RULE_CONFLICT']=stats.get('RULE_CONFLICT',0)+1;continue
        if not old:
            seen[key]=new;new_rules.append(new)
        if not any(h.get('rule_key')==key and h.get('item_id')==p['item_id'] for h in history+new_history):
            new_history.append({**p,'rule_key':key,'processed_at':stamp})
        stats['APPROVED']=stats.get('APPROVED',0)+1
    return remaining,existing_rules+new_rules,history+new_history,stats

class GoogleSheets:
    """Sheets API v4, using existing GCP service-account secret with Sheets scope."""
    def __init__(self,spreadsheet_id):
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request
        path=os.environ['GOOGLE_APPLICATION_CREDENTIALS']
        cred=service_account.Credentials.from_service_account_file(path,scopes=['https://www.googleapis.com/auth/spreadsheets'])
        cred.refresh(Request())
        self.token=cred.token;self.id=spreadsheet_id
    def call(self,method,url,**kw):
        r=requests.request(method,'https://sheets.googleapis.com/v4/spreadsheets/'+self.id+url,
                           headers={'Authorization':'Bearer '+self.token},timeout=90,**kw)
        if not r.ok:raise RuntimeError('Sheets API '+str(r.status_code)+': '+r.text[:350])
        return r.json() if r.content else {}
    def get_tab(self,tab,fields):
        data=self.call('GET','/values/'+tab+'!A1:Z100000').get('values',[])
        if not data:return []
        if data[0][:len(fields)]!=fields:raise ValueError(tab+' headers wrong; do not overwrite user sheet')
        return [dict(zip(fields,row+['']*(len(fields)-len(row)))) for row in data[1:] if any(str(v).strip() for v in row)]
    def set_tab(self,tab,rows,fields):
        data=[fields]+[[str(r.get(k,'')) for k in fields] for r in rows]
        # Replace values only, never delete a worksheet or its formatting.
        self.call('POST','/values/'+tab+'!A1:Z100000:clear',json={})
        self.call('PUT','/values/'+tab+'!A1?valueInputOption=RAW',json={'values':data})
    def verify_tabs(self):
        d=self.call('GET','?fields=sheets.properties.title')
        titles={x['properties']['title'] for x in d.get('sheets',[])}
        needed={'Pending_Material','Approved_Rules','History'}
        if not needed.issubset(titles):raise ValueError('Missing spreadsheet tabs: '+str(sorted(needed-titles)))

def sync(out,spreadsheet_id=None,local_only=False):
    out=Path(out); audit=out/'audit.csv'; assert audit.exists(),audit
    if local_only:
        pending=load_csv(out/'Pending_Material.csv') if (out/'Pending_Material.csv').exists() else []
        approved=load_csv(out/'Approved_Rules.csv') if (out/'Approved_Rules.csv').exists() else []
        history=load_csv(out/'History.csv') if (out/'History.csv').exists() else []
    else:
        sheet=GoogleSheets(spreadsheet_id or os.environ['MATERIAL_SHEET_ID'])
        sheet.verify_tabs()
        pending=sheet.get_tab('Pending_Material',PENDING_FIELDS)
        approved=sheet.get_tab('Approved_Rules',RULE_FIELDS)
        history=sheet.get_tab('History',HISTORY_FIELDS)
    # Do not accept edited offer/product identities from staff. ID fields are immutable.
    by_id={r['id']:r for r in load_csv(audit)}
    for p in pending:
        source=by_id.get(p.get('item_id'))
        if not source or (source.get('shopify_product_id')!=p.get('shopify_product_id') or
                          source.get('shopify_variant_id')!=p.get('shopify_variant_id')):
            raise ValueError('Pending row has unknown or modified Shopify IDs: '+str(p.get('item_id')))
    # Historical approvals rely on original Shopify evidence. Fail closed if a cache
    # snapshot lacks those files, rather than silently dropping approved materials.
    existing=by_id.values()
    needs_hoodie=any(r.get('style_resolution_source')=='SHOPIFY_DESCRIPTION' and r.get('approved_material') for r in existing)
    needs_shirt=any(r.get('style_resolution_source')=='SHOPIFY_EXACT_VARIANT_REFETCH' and r.get('approved_material') for r in existing)
    if needs_hoodie and not (out/'style_description_evidence.csv').exists():
        raise ValueError('Missing Hoodie Shopify evidence; refusing destructive audit rebuild')
    if needs_shirt and not (out/'shirt_jersey_style_evidence.csv').exists():
        raise ValueError('Missing Shirt/Jersey Shopify evidence; refusing destructive audit rebuild')
    remaining,rules,hist,stats=ingest(pending,approved,history)
    # Persist history + rules BEFORE clearing Pending; restart is idempotent.
    if local_only:
        export_csv(out/'Approved_Rules.csv',rules,RULE_FIELDS)
        export_csv(out/'History.csv',hist,HISTORY_FIELDS)
    else:
        sheet.set_tab('Approved_Rules',rules,RULE_FIELDS)
        sheet.set_tab('History',hist,HISTORY_FIELDS)
    # Export rules snapshot for unified audit; rules survive GitHub cache expiry in Sheets.
    export_csv(out/'sheet_approved_rules.csv',rules,RULE_FIELDS)
    # Rebuild existing audit using the persistent staff rules before generating pending.
    from unified_rules import rebuild
    rebuild(out)
    new_pending=build_pending(audit,remaining,rules)
    if local_only:export_csv(out/'Pending_Material.csv',new_pending,PENDING_FIELDS)
    else:sheet.set_tab('Pending_Material',new_pending,PENDING_FIELDS)
    report={'pending_before':len(pending),'approved_rules':len(rules),'new_rules':len(rules)-len(approved),
            'pending_after':len(new_pending),'status':stats,'gmc_write':False}
    (out/'material_sheet_sync_summary.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',default='out');p.add_argument('--sheet-id');p.add_argument('--local',action='store_true')
    args=p.parse_args();print(json.dumps(sync(args.out,args.sheet_id,args.local),indent=2))
