"""Read-only GMC Color/Pattern human-in-the-loop Google Sheets sync.

Existing Material tabs untouched. Rows are validated and persisted in Approved_Attributes
before being removed from Pending_*; no GMC / Shopify writes. Evidence is cached
for reprocessing. Staff rules are ITEM scoped for Color and PRODUCT scoped for Pattern.
"""
from __future__ import annotations
import argparse,csv,datetime,html,json,os,re
from pathlib import Path
from material_sheet_sync import GoogleSheets,load_csv,export_csv
from engine import color_mentions,description_pattern_candidates,PATTERNS,plain,is_missing_color

PENDING_FIELDS=['item_id','product_id','variant_id','product_title','variant_options','attribute','current_value','suggested_value','evidence','evidence_source','scope','confirmed_value','staff_note','status','validation_message']
RULE_FIELDS=['rule_key','attribute','scope','item_id','product_id','confirmed_value','source','approved_at']
HISTORY_FIELDS=PENDING_FIELDS+['rule_key','processed_at']
ATTRIBUTES=('COLOR','PATTERN')
TAB_PENDING={'COLOR':'Pending_Color','PATTERN':'Pending_Pattern'}
TAB_RULES='Approved_Attributes'
TAB_HISTORY='Attribute_History'
TAB_NAMES=[*TAB_PENDING.values(),TAB_RULES,TAB_HISTORY]
SAFE_COLOR=re.compile(r'^[A-Za-z][A-Za-z0-9 /&()+,.-]{1,75}$')
SAFE_PATTERN=re.compile(r'^[A-Za-z][A-Za-z0-9 /&()+,.-]{1,75}$')
AMBIGUOUS={'one color','one colour','unknown','n a','na','none','not sure','tbd','other','default title','yes','no'}

def norm(s):return re.sub(r'[^a-z0-9]+',' ',str(s or '').casefold()).strip()

def is_missing(row,attribute):
    a=attribute.lower()
    if attribute=='COLOR':return is_missing_color(row.get('current_color')) and not row.get('approved_color')
    return not str(row.get('current_pattern','')).strip() and not row.get('approved_pattern') and row.get('pattern_qa')!='STAFF_NOT_APPLICABLE'

def explicit_color_description(description):
    """Only labels explicitly describing product color, never arbitrary design color."""
    d=plain(description)
    segments=re.findall(r'(?i)\b(?:shirt color|garment color|base color|fabric color|color of (?:the )?(?:shirt|garment))\s*[:=-]\s*([^.;\n]{1,75})',d)
    found=[]
    for seg in segments:
        names=color_mentions(seg)
        if len(names)==1:found.append(names[0])
    unique=list(dict.fromkeys(found))
    return unique[0] if len(unique)==1 else ''

def candidate(row,attribute,evidence=None):
    """Propose; do NOT auto-approve ambiguous evidence."""
    key=attribute.lower()
    source=evidence or {}
    if row.get('proposed_'+key):
        return row.get('proposed_'+key,''),row.get(key+'_evidence',''),'AUDIT_'+row.get(key+'_qa','')
    title=source.get('shopify_title','') or row.get('title','')
    desc=source.get('description','')
    option=source.get('selected_color','')
    if attribute=='COLOR':
        if option and norm(option) not in AMBIGUOUS:
            return option,'Shopify verified Color variant: '+option,'SHOPIFY_VARIANT'
        # Title describing *garment color* can be suggested but requires staff review.
        match=re.search(r'(?i)\b(?:shirt|jersey|hoodie|polo|tee|t-shirt)\s+(?:in\s+)?(black|white|blue|red|green|pink|yellow|purple|navy|gray|grey)\b',title)
        if match:return match.group(1).title(),'Shopify title: '+title[:240],'SHOPIFY_TITLE_REVIEW'
        desc_color=explicit_color_description(desc)
        if desc_color:return desc_color,'Shopify description explicit garment color','SHOPIFY_DESCRIPTION_REVIEW'
    else:
        found=[name for name,rx in PATTERNS.items() if re.search(rx,title,re.I)]
        if len(found)==1:return found[0],'Shopify title: '+title[:240],'SHOPIFY_TITLE_REVIEW'
        suggested,ev,_=description_pattern_candidates(desc)
        if suggested:return suggested,ev,'SHOPIFY_DESCRIPTION_REVIEW'
    return '',('Checked Shopify product and description' if source else 'Audit only; Shopify description refetch required'),('SHOPIFY_CHECKED_NO_MATCH' if source else 'REFETCH_REQUIRED')

def evidence_map(out):
    path=Path(out)/'attribute_shopify_evidence.csv'
    return {r['item_id']:r for r in load_csv(path)} if path.exists() else {}

def build_pending(rows,attribute,old=(),rules=(),evidence=None):
    evidence=evidence or {}
    previous={r['item_id']:r for r in old if r.get('item_id')}
    saved={r['rule_key']:r for r in rules}
    group={}
    for r in rows:
        if r.get('shopify_status')!='SHOPIFY_VERIFIED' or not is_missing(r,attribute):continue
        # Do not ask employees to decide before Shopify Title/Description is re-fetched.
        if r['id'] not in evidence or evidence[r['id']].get('evidence_status')!='VERIFIED':
            # Preserve existing staff work if an evidence cache is missing.
            if r['id'] in previous:group[('COLOR:ITEM:'+r['id'] if attribute=='COLOR' else 'PATTERN:PRODUCT:'+r.get('shopify_product_id',''))]=previous[r['id']]
            continue
        item=r['id'];pid=r.get('shopify_product_id',''); vid=r.get('shopify_variant_id','')
        scope='ITEM' if attribute=='COLOR' else 'PRODUCT'
        key=('COLOR:ITEM:'+item if attribute=='COLOR' else 'PATTERN:PRODUCT:'+pid)
        if key in saved:continue
        # Pattern is product-level, one task per product, even if multiple variant IDs.
        if key in group:continue
        suggested,proof,src=candidate(r,attribute,evidence.get(item))
        prior=previous.get(item,{})
        entry={'item_id':item,'product_id':pid,'variant_id':vid,'product_title':r.get('title',''),
               'variant_options':r.get('variant_options',''),'attribute':attribute,
               'current_value':r.get('current_'+attribute.lower(),''),'suggested_value':suggested,
               'evidence':proof,'evidence_source':src,'scope':scope,
               'confirmed_value':prior.get('confirmed_value',''),'staff_note':prior.get('staff_note',''),
               'status':prior.get('status') or 'PENDING','validation_message':prior.get('validation_message','')}
        group[key]=entry
    return list(group.values())

def key_of(p):
    a=p.get('attribute','').upper(); s=p.get('scope','').upper()
    if a=='COLOR':return 'COLOR:ITEM:'+p.get('item_id','')
    return 'PATTERN:PRODUCT:'+p.get('product_id','')

def validate(p,source):
    a=p.get('attribute','').upper(); s=p.get('scope','').upper()
    if a not in ATTRIBUTES or s!=('ITEM' if a=='COLOR' else 'PRODUCT'):return 'INVALID_SCOPE_OR_ATTRIBUTE'
    if not source or source.get('shopify_product_id')!=p.get('product_id') or source.get('shopify_variant_id')!=p.get('variant_id'):
        return 'INVALID_IMMUTABLE_IDS'
    status=p.get('status','').strip().upper()
    if status not in ('APPROVE','NOT_APPLICABLE'):return 'WAITING_FOR_STAFF'
    if status=='NOT_APPLICABLE':
        return 'VALID' if a=='PATTERN' else 'NA_NOT_ALLOWED_FOR_COLOR'
    value=str(p.get('confirmed_value','')).strip()
    if not value or norm(value) in AMBIGUOUS:return 'MISSING_OR_GENERIC_VALUE'
    if not (SAFE_COLOR if a=='COLOR' else SAFE_PATTERN).fullmatch(value):return 'INVALID_VALUE'
    return 'VALID'

def ingest(pending,rules,history,by_id):
    existing={r['rule_key']:r for r in rules if r.get('rule_key')}
    remaining=[];newrules=[];newhistory=[];counts={}
    stamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
    for original in pending:
        p=dict(original);why=validate(p,by_id.get(p.get('item_id')))
        if why!='VALID':
            p['validation_message']='' if why=='WAITING_FOR_STAFF' else why
            remaining.append(p);counts[why]=counts.get(why,0)+1;continue
        a=p['attribute'].upper();status=p['status'].upper();key=key_of(p)
        value='NOT_APPLICABLE' if status=='NOT_APPLICABLE' else p['confirmed_value'].strip()
        old=existing.get(key)
        if old and norm(old['confirmed_value'])!=norm(value):
            p['validation_message']='RULE_CONFLICT';remaining.append(p);counts['RULE_CONFLICT']=counts.get('RULE_CONFLICT',0)+1;continue
        if not old:
            rule={'rule_key':key,'attribute':a,'scope':p['scope'],'item_id':p['item_id'] if a=='COLOR' else '',
                  'product_id':p['product_id'] if a=='PATTERN' else '', 'confirmed_value':value,'source':'GOOGLE_SHEETS_STAFF','approved_at':stamp}
            existing[key]=rule;newrules.append(rule)
        if not any(h.get('rule_key')==key for h in history+newhistory):
            newhistory.append({**p,'rule_key':key,'processed_at':stamp})
        counts['APPROVED']=counts.get('APPROVED',0)+1
    return remaining,rules+newrules,history+newhistory,counts

def clear_stale_reason(row,attribute):
    old=[x.strip() for x in str(row.get('review_reason','')).split(';') if x.strip()]
    if attribute=='COLOR': remove=('color_missing_or_ambiguous','ambiguous_variant_color')
    else: remove=('pattern_not_explicit_in_title','pattern_not_explicit_in_title_or_description','pattern_description_requires_qa')
    row['review_reason']='; '.join(x for x in old if x not in remove)

def apply_rules(rows,rules):
    """Only update missing attributes. Does not erase any known approval."""
    lookup={r['rule_key']:r for r in rules if r.get('rule_key')}
    changed=0
    for row in rows:
        if row.get('shopify_status')!='SHOPIFY_VERIFIED':continue
        for a in ATTRIBUTES:
            if not is_missing(row,a):continue
            k=('COLOR:ITEM:'+row['id']) if a=='COLOR' else ('PATTERN:PRODUCT:'+row.get('shopify_product_id',''))
            rule=lookup.get(k)
            if not rule:continue
            v=rule['confirmed_value'];key=a.lower()
            if v=='NOT_APPLICABLE':
                row['pattern_qa']='STAFF_NOT_APPLICABLE';row['pattern_evidence']='GOOGLE_SHEETS_STAFF: NOT_APPLICABLE';clear_stale_reason(row,'PATTERN');changed+=1
            else:
                row['proposed_'+key]=v;row['approved_'+key]=v;row[key+'_qa']='STAFF_VERIFIED'
                row[key+'_evidence']='GOOGLE_SHEETS_STAFF: '+k;clear_stale_reason(row,a);changed+=1
    return changed

def auto_apply_verified_color(rows,evidence):
    """A real Shopify Color option is authoritative. Never interpret artwork color."""
    changed=0
    for row in rows:
        if row.get('shopify_status')!='SHOPIFY_VERIFIED' or not is_missing(row,'COLOR'):continue
        e=evidence.get(row['id'],{})
        if e.get('evidence_status')!='VERIFIED':continue
        color=(e.get('selected_color') or '').strip()
        if not color or norm(color) in AMBIGUOUS or len(color)>70 or not SAFE_COLOR.fullmatch(color):continue
        # Only a verified exact Shopify variant Color option; preserve shade spelling.
        row['proposed_color']=color;row['approved_color']=color
        row['color_qa']='COLOR_SHOPIFY_VARIANT_REFETCH_VERIFIED'
        row['color_evidence']='SHOPIFY_VERIFIED_VARIANT_COLOR: '+color
        clear_stale_reason(row,'COLOR')
        changed+=1
    return changed

def recompute_summaries(out,rows):
    out=Path(out)
    # Correct attribute counters; no misleading claim that an item with material is fully approved.
    counts={}
    for a in ('color','pattern'):
        counts['approved_'+a]=sum(bool(r.get('approved_'+a)) for r in rows)
        counts['proposed_'+a]=sum(bool(r.get('proposed_'+a)) for r in rows)
        counts['not_applicable_'+a]=sum(r.get(a+'_qa')=='STAFF_NOT_APPLICABLE' for r in rows)
    p=out/'summary.json'
    data=json.loads(p.read_text()) if p.exists() else {}
    data.update(counts);data['gmc_write']=False;data['color_pattern_sheet_sync']=True
    p.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
    (out/'attribute_sheet_sync_summary.json').write_text(json.dumps(counts,indent=2),encoding='utf-8')

def save_audit(out,rows):
    path=Path(out)/'audit.csv'
    with path.open(encoding='utf-8-sig',newline='') as f:fields=csv.DictReader(f).fieldnames
    export_csv(path,rows,fields)
    for tab in ('approved_attributes','ready_for_qa','needs_review'):
        p=Path(out)/(tab+'.csv')
        if p.exists():
            subset=[r for r in rows if (any(r.get('approved_'+a) for a in ('color','pattern','material')))==(tab!='needs_review')]
            export_csv(p,subset,fields)

def init_tabs(sheet):
    d=sheet.call('GET','?fields=sheets.properties.title')
    have={x['properties']['title'] for x in d.get('sheets',[])}
    missing=[name for name in TAB_NAMES if name not in have]
    if missing:sheet.call('POST',':batchUpdate',json={'requests':[{'addSheet':{'properties':{'title':t}}} for t in missing]})
    # Only initialize blank new sheets. Do not overwrite existing employee edits.
    for t in missing:
        fields=PENDING_FIELDS if t.startswith('Pending_') else RULE_FIELDS if t==TAB_RULES else HISTORY_FIELDS
        sheet.set_tab(t,[],fields)

def sync(out,sheet_id=None,local=False):
    out=Path(out);audit=out/'audit.csv'
    rows=load_csv(audit);by_id={r['id']:r for r in rows}
    if len(by_id)!=len(rows):raise ValueError('Duplicate offer IDs in audit')
    if local:
        def read(name):return load_csv(out/(name+'.csv')) if (out/(name+'.csv')).exists() else []
        def write(name,vals,cols):export_csv(out/(name+'.csv'),vals,cols)
    else:
        sheet=GoogleSheets(sheet_id or os.environ.get('MATERIAL_SHEET_ID') or os.environ['ATTRIBUTE_SHEET_ID'])
        init_tabs(sheet)
        def read(name):return sheet.get_tab(name,PENDING_FIELDS if name.startswith('Pending_') else RULE_FIELDS if name==TAB_RULES else HISTORY_FIELDS)
        def write(name,vals,cols):sheet.set_tab(name,vals,cols)
    rules=read(TAB_RULES);hist=read(TAB_HISTORY)
    rest={};stats={};all_new=[]
    for a in ATTRIBUTES:
        tab=TAB_PENDING[a]
        old=read(tab)
        # Validate IDs against immutable source before writing any rule.
        for p in old:
            if p.get('item_id') not in by_id:raise ValueError('Unknown pending item ID: '+p.get('item_id',''))
        tail,rules,hist,count=ingest(old,rules,hist,by_id)
        rest[a]=tail;stats[a]={'pending_before':len(old),**count}
    # Persist rules and history before removing pending rows. Retry idempotently.
    write(TAB_RULES,rules,RULE_FIELDS);write(TAB_HISTORY,hist,HISTORY_FIELDS)
    export_csv(out/'sheet_approved_attribute_rules.csv',rules,RULE_FIELDS)
    evidence=evidence_map(out)
    auto_count=auto_apply_verified_color(rows,evidence)
    new_count=apply_rules(rows,rules)
    save_audit(out,rows);recompute_summaries(out,rows)
    for a in ATTRIBUTES:
        newly=build_pending(rows,a,rest[a],rules,evidence)
        write(TAB_PENDING[a],newly,PENDING_FIELDS)
        stats[a]['pending_after']=len(newly)
    stats.update({'rules_total':len(rules),'applied_staff_updates':new_count,'auto_verified_variant_colors':auto_count,'evidence_cached':len(evidence),
                  'still_waiting_shopify_check':{a:sum(is_missing(r,a) and r.get('shopify_status')=='SHOPIFY_VERIFIED' and r['id'] not in evidence for r in rows) for a in ATTRIBUTES},'gmc_write':False})
    (out/'attribute_sheet_sync_summary.json').write_text(json.dumps(stats,indent=2),encoding='utf-8')
    return stats

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',default='out');ap.add_argument('--sheet-id');ap.add_argument('--local',action='store_true')
    args=ap.parse_args();print(json.dumps(sync(args.out,args.sheet_id,args.local),indent=2))
