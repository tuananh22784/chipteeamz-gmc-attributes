"""Unified read-only approval report based on user-supplied fabric styles.

This module never calls Shopify or Merchant writes. It does not interpret unmapped styles by fuzzy matching.
"""
from __future__ import annotations
import collections
import csv
import json
import os
from pathlib import Path
from material_rules import normalized

ROOT = Path(__file__).resolve().parent
MASTER = ROOT / 'material_master.csv'
LEGACY_ALIASES = ROOT / 'material_aliases.csv'
CONFIRMATIONS = ROOT / 'style_confirmations.csv'
# Explicit direct user confirmation made in conversation, not present in 49-row review CSV.
ADDITIONAL = {'Women Polo Shirt': 'Women Short sleeve polo shirt'}
FIELD_ADDITIONS = ['material_rule_id','material_source','material_matched_subtype',
                   'material_decision','material_reason','material_component_1','material_component_2']
REVIEW_FIELDS = ['variant_style','confirmation','example_item_id','handling','resolved_target',
                 'resolved_material','rule_id','decision','note']
BASE_OUTPUTS = ['audit','approved_attributes','ready_for_qa','needs_review','candidates_review','auto_fix_eligible']
MATERIAL_REPORT_FIELDS=['id','language','feed_label','shopify_status','variant_style','current_material',
                        'matched_subtype','material_rule_id','material_source','material_candidate','material_decision','material_reason',
                        'material_component_1','material_component_2']


def read_csv(path):
    with open(path,encoding='utf-8-sig',newline='') as f:
        return list(csv.DictReader(f))


def rulebook():
    master={}
    for row in read_csv(MASTER):
        key=normalized(row['style'])
        if key in master and master[key]['fabric_composition']!=row['fabric_composition']:
            raise ValueError('Master fabric conflict for '+row['style'])
        master[key]=row
    if len(read_csv(MASTER))!=56:
        raise ValueError('Unexpected Fabric Master count; review source before release')
    aliases={}
    def register(alias,target,origin,scope='GLOBAL',item_id=''):
        key=normalized(alias)
        mt=master.get(normalized(target))
        if not mt:
            return False
        candidate=(mt['fabric_composition'],mt['rule_id'],mt['style'],origin,scope,item_id)
        if key in aliases:
            prev=aliases[key]
            if prev[0] != candidate[0] or prev[1]!=candidate[1]:
                raise ValueError('Fabric alias conflict: '+alias)
            if prev[4]=='ITEM_SCOPED' and scope=='GLOBAL':
                aliases[key]=candidate
        else:
            aliases[key]=candidate
        return True
    for row in read_csv(LEGACY_ALIASES):
        register(row['alias'],row['target_style'],'LEGACY_ALIAS')
    decisions=[]
    for row in read_csv(CONFIRMATIONS):
        alias=row['variant_style'].strip();target=row['user_confirmation'].strip()
        decision=''; note='';resolved='';material='';rid=''
        if not target:
            raise ValueError('Confirmation missing: '+alias)
        if 'tumbler cup' in normalized(target):
            decision='NON_APPAREL';note='Excluded from fabric mapping'
        elif '+' in alias:
            decision='MULTI_COMPONENT';note='Preserve separate component fabrics; do not flatten percentages'
        elif normalized(target)=='unisex premium t shirt':
            decision='COLOR_DEPENDENT_REVIEW';note='Fabric varies with color; needs exact color rules'
        elif normalized(alias)=='men short sleeve jersey':
            decision='CONFLICTING_PRODUCT_FAMILY';note='Cycling jersey title, user mapped to polo; require item-level review'
        else:
            found=master.get(normalized(target))
            if normalized(target)=='women short sleeve quarter zip':
                found=master.get(normalized('Women Quarter Zip'))
            if not found:
                decision='TARGET_NOT_IN_MASTER';note='Style identity confirmed but material not found in supplied master'
            else:
                scope='ITEM_SCOPED' if normalized(alias) in ('women','unisex') else 'GLOBAL'
                if scope=='ITEM_SCOPED':
                    # Do not introduce generic global aliases accidentally.
                    decision='ITEM_SCOPED_APPROVED'
                    note='Valid only for confirmed example offer ID'
                else:
                    decision='APPROVED_ALIAS'
                register(alias,found['style'],'USER_CONFIRMATION',scope,row['example_item_id'] if scope=='ITEM_SCOPED' else '')
                resolved=found['style'];material=found['fabric_composition'];rid=found['rule_id']
        decisions.append({'variant_style':alias,'confirmation':target,'example_item_id':row['example_item_id'],
                          'handling':row['handling'],'resolved_target':resolved,'resolved_material':material,
                          'rule_id':rid,'decision':decision,'note':note})
    for src,dst in ADDITIONAL.items():
        if not register(src,dst,'DIRECT_USER_CONFIRMATION'):
            raise ValueError('Direct user confirmation unresolved: '+src)
    assert len(decisions)==49, 'All 49 confirmations must have explicit disposition'
    # Make sure a generic alias cannot be accidentally attached to unrelated items.
    return master,aliases,decisions


def material_assessment(row, rules):
    master,aliases,_=rules
    current=(row.get('current_material') or '').strip()
    style=(row.get('variant_style') or '').strip()
    value={'material_rule_id':'','material_source':'','material_matched_subtype':'',
           'material_decision':'','material_reason':'','material_component_1':'','material_component_2':''}
    def finish(code,reason):
        value['material_decision']=code;value['material_reason']=reason
        return value,''
    if row.get('shopify_status')!='SHOPIFY_VERIFIED':
        return finish('SHOPIFY_UNVERIFIED','No verified matching Shopify variant')
    if current:
        return finish('KEEP_EXISTING','Never overwrite existing GMC material')
    if not style:
        return finish('REVIEW_MISSING_STYLE','Shopify variant style unavailable')
    norm=normalized(style)
    if 'tumbler cup' in norm:
        return finish('NON_APPAREL','Tumbler is not a fabric product')
    if norm in ('women','unisex') and row.get('id') not in {
       'shopify_US_7491079536738_42435989078114',
       'shopify_US_7492644077666_42447507325026'}:
        return finish('GENERIC_STYLE_REVIEW','Generic style cannot be assigned to other items')
    if norm in ('women','unisex'):
        record=aliases.get(norm)
        if not record:
            return finish('REVIEW_UNMAPPED_SUBTYPE','No per-item confirmation for generic style')
    if '+' in norm or norm in ('long sleeve + face shield','long sleeve upf + face shield'):
        value['material_component_1']='Long Sleeve UPF: 100% polyester'
        value['material_component_2']='Face Shield: 95% polyester+5% spandex'
        return finish('MULTI_COMPONENT_REVIEW','Distinct components; do not invent single weight-averaged fabric')
    if '/' in style:
        if norm in ('black labs / hoodie','deer shed / hoodie','duck / hoodie','grouse / hoodie','pheasant / hoodie','pheasant / zip up hoodie','short sleeve polo shirt / blue'):
            pass # Exact user-confirmed composite-name alias
        else:
            return finish('COMPOSITE_REVIEW','Slash style requires exact user-confirmed alias')
    if norm == 'men short sleeve jersey':
        return finish('CONFLICTING_PRODUCT_FAMILY','Example is cycling jersey while confirmation targets polo')
    if norm == 'unisex premium t shirt':
        return finish('COLOR_DEPENDENT_REVIEW','Fabric composition depends on actual color variant')
    # For confirmed targets absent in master, do not infer from similar clothing names.
    record=aliases.get(norm)
    if not record:
        m=master.get(norm)
        if m:
            record=(m['fabric_composition'],m['rule_id'],m['style'],'MASTER_EXACT','GLOBAL','')
    if not record:
        return finish('REVIEW_UNMAPPED_SUBTYPE','No exact master or confirmed alias with fabric')
    composition,rule_id,subtype,origin,scope,item_id=record
    if scope=='ITEM_SCOPED' and item_id!=row.get('id'):
        return finish('GENERIC_STYLE_REVIEW','Confirmation restricted to a single example item')
    value.update({'material_rule_id':rule_id,'material_source':'USER_FABRIC_COMPOSITION_MASTER',
                  'material_matched_subtype':subtype,'material_decision':'MASTER_APPROVED_READ_ONLY',
                  'material_reason':origin})
    return value,composition


def augment(row,rules):
    row=dict(row)
    m,composition=material_assessment(row,rules)
    row.update(m)
    if row.get('current_material') or row.get('shopify_status')!='SHOPIFY_VERIFIED':
        row['approved_material']=''
    elif composition:
        row['proposed_material']=composition
        row['material_evidence']='USER_FABRIC_COMPOSITION_MASTER: '+m['material_matched_subtype']+' ('+m['material_rule_id']+')'
        row['approved_material']=composition
        row['material_qa']='MATERIAL_MASTER_VERIFIED'
    else:
        row['approved_material']=''
        if row.get('material_qa')=='MATERIAL_MASTER_VERIFIED':
            row['material_qa']='MATERIAL_NEEDS_REVIEW'
    # Retain previously grounded Color & Pattern decisions, including DESCRIPTION_REVIEW.
    has_approved=any(row.get('approved_'+k) for k in ('color','pattern','material'))
    has_proposals=any(row.get('proposed_'+k) for k in ('color','pattern','material'))
    if not any([not row.get('current_pattern'),not row.get('current_material'),
                not row.get('current_color') or str(row.get('current_color')).strip("'\"").lower() in ('one color','one colour')]):
        row['qa_status']='NO_MISSING_FIELDS'
    elif has_approved:
        row['qa_status']='READY_FOR_QA'
    elif has_proposals:
        row['qa_status']='MATERIAL_OR_PATTERN_REVIEW'
    else:
        row['qa_status']='NEEDS_REVIEW'
    return row


def rebuild(out,only_migrate=False):
    out=Path(out)
    src=out/'audit.csv'
    if not src.exists():
        raise ValueError('Expected existing audit.csv; cannot rebuild')
    rules=rulebook()
    alias_review=out/'style_alias_validation.csv'
    with alias_review.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=REVIEW_FIELDS);w.writeheader();w.writerows(rules[2])
    with src.open(encoding='utf-8-sig',newline='') as f:
        fields=csv.DictReader(f).fieldnames
    final_fields=list(fields)+[x for x in FIELD_ADDITIONS if x not in fields]
    temp=src.with_suffix('.csv.tmp')
    count=collections.Counter()
    with src.open(encoding='utf-8-sig',newline='') as inp, temp.open('w',encoding='utf-8-sig',newline='') as dst:
        reader=csv.DictReader(inp); writer=csv.DictWriter(dst,fieldnames=final_fields,extrasaction='ignore');writer.writeheader()
        others={}
        if not only_migrate:
            for name in BASE_OUTPUTS[1:]:
                others[name]=open(out/(name+'.csv.tmp'),'w',encoding='utf-8-sig',newline='')
                ww=csv.DictWriter(others[name],fieldnames=final_fields,extrasaction='ignore')
                ww.writeheader();others[name]=(others[name],ww)
            for name in ('material_mapping_review','material_master_candidates'):
                fh=open(out/(name+'.csv.tmp'),'w',encoding='utf-8-sig',newline='')
                mw=csv.DictWriter(fh,fieldnames=MATERIAL_REPORT_FIELDS,extrasaction='ignore')
                mw.writeheader();others[name]=(fh,mw)
        try:
            for r in reader:
                row=augment(r,rules)
                writer.writerow(row)
                count['scanned']+=1
                if row['shopify_status']=='SHOPIFY_VERIFIED':count['shopify_verified']+=1
                else:count['shopify_unverified']+=1
                for key in ('color','pattern','material'):
                    cur=row['current_'+key]
                    missing=(not cur or str(cur).strip("'\"").lower() in ('one color','one colour')) if key=='color' else not cur
                    if missing:count['missing_'+key]+=1
                    if row.get('proposed_'+key):count['proposed_'+key]+=1
                    if row.get('approved_'+key):count['approved_'+key]+=1
                if any(row.get('proposed_'+k) for k in ('color','pattern','material')):count['has_proposals']+=1
                if any(row.get('approved_'+k) for k in ('color','pattern','material')):count['approved_items']+=1
                count[row['qa_status']]+=1
                count['material_decision_'+row['material_decision']]+=1
                if not only_migrate:
                    if any(row.get('proposed_'+k) for k in ('color','pattern','material')):
                        others['candidates_review'][1].writerow(row)
                    if any(row.get('approved_'+k) for k in ('color','pattern','material')):
                        others['approved_attributes'][1].writerow(row)
                        others['ready_for_qa'][1].writerow(row)
                    else:
                        others['needs_review'][1].writerow(row)
                    mapping={'id':row['id'],'language':row['language'],'feed_label':row['feed_label'],
                             'shopify_status':row['shopify_status'],'variant_style':row['variant_style'],
                             'current_material':row['current_material'],'matched_subtype':row['material_matched_subtype'],
                             'material_rule_id':row['material_rule_id'],'material_source':row['material_source'],
                             'material_candidate':row['approved_material'],'material_decision':row['material_decision'],
                             'material_reason':row['material_reason'],
                             'material_component_1':row['material_component_1'],'material_component_2':row['material_component_2']}
                    others['material_mapping_review'][1].writerow(mapping)
                    if row['material_decision']=='MASTER_APPROVED_READ_ONLY':
                        others['material_master_candidates'][1].writerow(mapping)
                    # auto_fix_eligible intentionally remains empty (header only)
        finally:
            for f,w in others.values():f.close()
    os.replace(temp,src)
    if not only_migrate:
        for name in [*BASE_OUTPUTS[1:],'material_mapping_review','material_master_candidates']:
            os.replace(out/(name+'.csv.tmp'),out/(name+'.csv'))
        prev={}
        if (out/'checkpoint.json').exists():
            cp=json.loads((out/'checkpoint.json').read_text())
            if cp.get('scanned') != count['scanned']:
                raise ValueError('Checkpoint and CSV count mismatch during unified rebuild')
            prev={'pages':cp.get('pages'),'completed':cp.get('completed'),
                  'next_page_token_present':bool(cp.get('next_page_token')),
                  'page_size':cp.get('page_size'),'account':cp.get('account')}
        summary=dict(count)
        summary.update(prev)
        summary['ready_for_qa']=count['READY_FOR_QA']
        summary['needs_review']=count['NEEDS_REVIEW']+count['MATERIAL_OR_PATTERN_REVIEW']
        summary.update({'mode':'READ_ONLY','auto_fix_eligible':0,'qa_policy':'UNIFIED_APPROVAL_READ_ONLY',
                        'fabric_master_styles':56,'style_confirmations':49,'fabric_approval_source':'USER_MASTER_EXACT_OR_USER_CONFIRMED_ALIAS',
                        'pattern_history_note':'Prior scan rows retain old Pattern evidence; description fallback for historical rows requires Shopify re-fetch'})
        (out/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
        msummary={'source':'Fabric Composition - Sheet1.csv + user Style confirmations',
                  'master_styles':56,'style_confirmations':49,'total_rows':count['scanned'],
                  'decisions':{k.removeprefix('material_decision_'):v for k,v in count.items() if k.startswith('material_decision_')},
                  'write_mode':'READ_ONLY'}
        (out/'material_mapping_summary.json').write_text(json.dumps(msummary,indent=2,ensure_ascii=False),encoding='utf-8')
    return dict(count)

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument('--out',default='out')
    p.add_argument('--migrate',action='store_true')
    a=p.parse_args();print(json.dumps(rebuild(a.out,only_migrate=a.migrate),indent=2))
