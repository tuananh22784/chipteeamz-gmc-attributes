"""Unified read-only approval report based on user-supplied fabric styles.

This module never calls Shopify or Merchant writes. It does not interpret unmapped styles by fuzzy matching.
"""
from __future__ import annotations
import collections
import csv
import json
import os
import re
from pathlib import Path
from material_rules import normalized

ROOT = Path(__file__).resolve().parent
MASTER = ROOT / 'material_master.csv'
LEGACY_ALIASES = ROOT / 'material_aliases.csv'
CONFIRMATIONS = ROOT / 'style_confirmations.csv'
ADDITIONAL_CONFIRMATIONS = ROOT / 'style_confirmations_additional.csv'
# Explicit direct user confirmation made in conversation, not present in 49-row review CSV.
ADDITIONAL = {'Women Polo Shirt': 'Women Short sleeve polo shirt'}
FIELD_ADDITIONS = ['material_rule_id','material_source','material_matched_subtype',
                   'material_decision','material_reason','material_component_1','material_component_2',
                   'style_resolution_source','style_resolution_status','style_resolution_evidence','style_resolved']
REVIEW_FIELDS = ['variant_style','confirmation','example_item_id','handling','resolved_target',
                 'resolved_material','rule_id','decision','note']
BASE_OUTPUTS = ['audit','approved_attributes','ready_for_qa','needs_review','candidates_review','auto_fix_eligible']
DESCRIPTION_EVIDENCE='style_description_evidence.csv'
MATERIAL_REPORT_FIELDS=['id','language','feed_label','shopify_status','variant_style','current_material',
                        'matched_subtype','material_rule_id','material_source','material_candidate','material_decision','material_reason',
                        'material_component_1','material_component_2',
                        'style_resolution_source','style_resolution_status','style_resolution_evidence','style_resolved']


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
    if len(read_csv(MASTER))!=60:
        raise ValueError('Expected 56 original + 4 newly confirmed master materials')
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
    # All 17 additional confirmations must be explicitly validated and resolved.
    additions=read_csv(ADDITIONAL_CONFIRMATIONS)
    if len(additions)!=17:
        raise ValueError('Expected exactly 17 additional confirmed styles')
    additional_decisions=[]
    scoped={}
    color_dependent={}
    for ar in additions:
        a=ar['variant_style'].strip(); d=ar['mapping_decision'].strip()
        target=ar['resolved_subtype'].strip(); raw=ar['resolved_material'].strip()
        item=ar['example_item_id'].strip()
        decision=d
        if d in ('MATCH_EXISTING_MASTER','NEW_STYLE_MATERIAL'):
            record=master.get(normalized(target))
            if not record or normalized(record['fabric_composition'])!=normalized(raw):
                raise ValueError('Material confirmation not in master or conflicting: '+a)
            # allow overrides of old alias only if the user supplied a new explicit confirmation.
            old=aliases.get(normalized(a))
            if old and old[0]!=record['fabric_composition']:
                raise ValueError('Conflicting alias from prior confirmation: '+a)
            register(a,target,'ADDITIONAL_USER_CONFIRMATION')
        elif d=='ITEM_SCOPED_ONLY':
            if not item or not raw or not target:
                raise ValueError('Item-scoped rule incomplete: '+a)
            scoped[item]={'style':a,'material':raw,'target':target}
        elif d=='COLOR_DEPENDENT':
            color_dependent[normalized(a)]=raw
        elif d=='SUBTYPE_CONFIRMED_MATERIAL_PENDING':
            if raw:
                raise ValueError('Pending subtype unexpectedly has material: '+a)
        else:
            raise ValueError('Unrecognized additional confirmation disposition: '+d)
        additional_decisions.append({'style':a,'target':target,'material':raw,'decision':decision,'example_item_id':item})
    for src,dst in ADDITIONAL.items():
        if not register(src,dst,'DIRECT_USER_CONFIRMATION'):
            raise ValueError('Direct user confirmation unresolved: '+src)
    assert len(decisions)==49, 'All 49 confirmations must have explicit disposition'
    # Make sure a generic alias cannot be accidentally attached to unrelated items.
    return master,aliases,decisions,scoped,color_dependent,additional_decisions


def title_style_fallback(row):
    """Conservative fallback for variants lacking Style option.

    Source is the stored GMC title, not a fresh Shopify product-title request.
    Never use a vague 'shirt', 'jersey', or unqualified 'hoodie' to assert fabric.
    """
    title=(row.get('title') or '').strip()
    t=title.lower().replace('–','-').replace('—','-')
    t=re.sub(r'\s+',' ',t)
    def ret(style,status,evidence):
        return style,status,evidence
    if not t:
        return ret('', 'MISSING_TITLE', '')
    if re.search(r'\b(canvas|tumbler|ceramic mug|coffee mug|poster|wall art|sticker|blanket|pillow|ornament)\b',t) and not re.search(r'\b(t-shirt|t shirt|sweatshirt|hoodie|polo shirt)\b',t):
        return ret('','NON_APPAREL_TITLE','non-apparel product category')
    if re.search(r'\b(hoodie|hooded sweatshirt|pullover)\b',t):
        if re.search(r'\b220\s*g\s*air\s*layer\b',t):
            return ret('220g air layer Hoodie','TITLE_EXPLICIT','220g air layer hoodie')
        return ret('','HOODIE_NEEDS_DESCRIPTION','hoodie requires verified Shopify description to check cotton')
    if re.search(r'\b(quarter[- ]?zip|1/4[- ]?zip)\b',t):
        if re.search(r'\bquarter[- ]?zip sweatshirt\b',t):
            return ret('Quarter Zip Sweatshirt','TITLE_EXPLICIT','quarter zip sweatshirt')
        return ret('','AMBIGUOUS_QUARTER_ZIP','quarter zip subtype is not exact')
    if re.search(r'\b(crew neck sweatshirt|sweatshirts?)\b',t):
        if re.search(r'\b220\s*g\s*air\s*layer\b',t):
            return ret('220g air layer Sweatshirt','TITLE_EXPLICIT','220g air layer sweatshirt')
        if re.search(r'\b(standard crew neck sweatshirt|crew neck sweatshirt|sweatshirt)\b',t):
            return ret('Sweatshirt','TITLE_EXPLICIT','sweatshirt')
    if re.search(r'\b(long[ -]?sleeve|long[ -]?sleeves)\b',t):
        if re.search(r'\b(upf\s*\d*\+?|sun protection|uv protection)\b',t):
            if re.search(r'\b(polo|quarter[- ]?zip|cycling|jersey|face shield)\b',t):
                return ret('','AMBIGUOUS_UPF_STYLE','UPF style overlaps another subtype')
            return ret('Long Sleeve UPF','TITLE_EXPLICIT','long sleeve UPF')
        if re.search(r'\b(polo|quarter[- ]?zip|cycling|jersey|face shield)\b',t):
            return ret('','AMBIGUOUS_LONG_SLEEVE','long sleeves overlap another subtype')
        return ret('Long sleeves','TITLE_EXPLICIT','long sleeves')
    if re.search(r'\b(t[- ]?shirts?|tees?)\b',t):
        if re.search(r'\b(upf\s*\d*\+?|sun protection|uv protection)\b',t):
            return ret('T-shirt UPF','TITLE_EXPLICIT','t-shirt UPF')
        if re.search(r'\b(cycling jersey|jersey with|polyester|performance jersey)\b',t):
            return ret('','AMBIGUOUS_TSHIRT','t-shirt wording overlaps different product family')
        if re.search(r"\b(women'?s|ladies|woman's|female)\s+(?:standard\s+)?t[- ]?shirt\b",t):
            return ret('Women T-shirt','TITLE_EXPLICIT','women t-shirt')
        return ret('T-shirt','TITLE_EXPLICIT','t-shirt')
    if re.search(r'\b(polo shirt|polo shirts|polo)\b',t):
        # User-confirmed policy: unqualified Polo = short sleeve Polo shirt.
        if re.search(r'\b(long[ -]?sleeve|sleeveless|quarter[- ]?zip|1/4[- ]?zip|zip[- ]?up)\b',t):
            return ret('','AMBIGUOUS_POLO','Polo title has a modifier requiring a distinct subtype')
        return ret('Men Short sleeve polo shirt','TITLE_EXPLICIT_USER_POLO_RULE','user-confirmed default short sleeve polo shirt')
    if re.search(r'\b(jersey|jerseys)\b',t):
        return ret('','AMBIGUOUS_JERSEY','jersey title does not uniquely identify fabric')
    return ret('', 'TITLE_INSUFFICIENT', 'no unambiguous apparel subtype in title')


def description_evidence(out):
    """Read only previously fetched, item-specific Shopify description classification."""
    result={}
    evidence_path=Path(out)/DESCRIPTION_EVIDENCE
    if not evidence_path.exists():
        return result
    for x in read_csv(evidence_path):
        if x.get('status') == 'SHOPIFY_VERIFIED' and x.get('cotton_present') in ('YES','NO'):
            result[x['id']]=x
    return result


def material_assessment(row, rules, evidence=None):
    master,aliases,_,scoped,color_dependent,_=rules
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
    if style:
        value.update({'style_resolution_source':'SHOPIFY_VARIANT','style_resolution_status':'VARIANT_STYLE',
                      'style_resolution_evidence':'Variant Style option','style_resolved':style})
    else:
        inferred, status, title_evidence = title_style_fallback(row)
        value.update({'style_resolution_source':'GMC_TITLE_FALLBACK', 'style_resolution_status':status,
                      'style_resolution_evidence':title_evidence, 'style_resolved':inferred})
        if status=='NON_APPAREL_TITLE':
            return finish('NON_APPAREL','Product title identifies non-apparel')
        if status=='HOODIE_NEEDS_DESCRIPTION':
            ev=(evidence or {}).get(row.get('id'))
            if not ev or ev.get('shopify_product_id') != row.get('shopify_product_id') or ev.get('shopify_variant_id') != row.get('shopify_variant_id'):
                return finish('REVIEW_MISSING_STYLE','HOODIE_DESCRIPTION_REQUIRED: verified Shopify description not cached')
            if ev['cotton_present']=='YES':
                style='Hoodie'
                value.update({'style_resolution_source':'SHOPIFY_DESCRIPTION',
                              'style_resolution_status':'HOODIE_COTTON_IN_DESCRIPTION',
                              'style_resolution_evidence':'Exact word cotton found in verified Shopify description',
                              'style_resolved':style})
            else:
                style='220g air layer Hoodie'
                value.update({'style_resolution_source':'SHOPIFY_DESCRIPTION',
                              'style_resolution_status':'HOODIE_NO_COTTON_IN_DESCRIPTION',
                              'style_resolution_evidence':'Nonempty verified Shopify description lacks exact word cotton; user rule',
                              'style_resolved':style})
        else:
            if status not in ('TITLE_EXPLICIT','TITLE_EXPLICIT_USER_POLO_RULE'):
                return finish('REVIEW_MISSING_STYLE','No safe title mapping: '+status+'; '+title_evidence)
            style=inferred

    norm=normalized(style)
    if row.get('id') in scoped:
        match=scoped[row['id']]
        if normalized(style)==normalized(match['style']):
            value.update({'material_rule_id':'USER_ITEM_'+row['id'],
                          'material_source':'USER_CONFIRMED_ITEM_SCOPED',
                          'material_matched_subtype':match['target'],
                          'material_decision':'MASTER_APPROVED_READ_ONLY',
                          'material_reason':'ITEM_SCOPED_USER_CONFIRMATION'})
            return value,match['material']
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
    if norm in color_dependent:
        opts=(row.get('variant_options') or '')
        m=re.search(r'(?:^|\s*/\s*)Color\s*:\s*([^/]+)',opts,flags=re.I)
        if not m:
            return finish('COLOR_DEPENDENT_REVIEW','Variant color option is missing')
        variant_color=m.group(1).strip().lower()
        if variant_color=='ash grey' or variant_color=='ash gray':
            comp='99% cotton, 1% polyester'
        elif variant_color in ('heather grey','heather gray'):
            comp='90% cotton, 10% polyester'
        elif 'heather' in variant_color:
            comp='52% cotton, 48% polyester'
        else:
            # Only known solid names are approved; unknown colors require QA.
            solids={'black','white','navy','red','blue','royal blue','pink','green','yellow','purple','orange','maroon','brown','natural','cream','turquoise','teal','forest green','kelly green','military green','charcoal','charcoal grey','charcoal gray'}
            if variant_color not in solids:
                return finish('COLOR_DEPENDENT_REVIEW','Unknown solid/heather classification: '+variant_color)
            comp='100% cotton'
        value.update({'material_rule_id':'USER_COLOR_DEPENDENT_TEE',
                      'material_source':'USER_CONFIRMED_COLOR_COMPOSITION',
                      'material_matched_subtype':'Unisex Premium T-shirt',
                      'material_decision':'MASTER_APPROVED_READ_ONLY',
                      'material_reason':'VARIANT_COLOR:'+variant_color})
        return value,comp
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


def augment(row,rules,evidence=None):
    row=dict(row)
    m,composition=material_assessment(row,rules,evidence)
    row.update(m)
    if row.get('current_material') or row.get('shopify_status')!='SHOPIFY_VERIFIED':
        row['approved_material']=''
    elif composition:
        row['proposed_material']=composition
        row['material_evidence']='USER_FABRIC_COMPOSITION_MASTER: '+m['material_matched_subtype']+' ('+m['material_rule_id']+')'
        row['approved_material']=composition
        row['material_qa']='MATERIAL_MASTER_VERIFIED'
        stale={'material_not_explicit_or_ambiguous','material_needs_review','material_unknown','material_unverified'}
        parts=[p for p in (row.get('review_reason') or '').split(';') if p.strip().lower() not in stale]
        row['review_reason']=';'.join(parts)
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
    evidence=description_evidence(out)
    alias_review=out/'style_alias_validation.csv'
    with alias_review.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=REVIEW_FIELDS);w.writeheader();w.writerows(rules[2])
    with (out/'additional_confirmation_validation.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['style','target','material','decision','example_item_id']);w.writeheader();w.writerows(rules[5])
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
                row=augment(r,rules,evidence)
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
                             'material_component_1':row['material_component_1'],'material_component_2':row['material_component_2'],
                             'style_resolution_source':row.get('style_resolution_source',''),
                             'style_resolution_status':row.get('style_resolution_status',''),
                             'style_resolution_evidence':row.get('style_resolution_evidence',''),
                             'style_resolved':row.get('style_resolved','')}
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
        summary['style_title_fallback']=True
        summary.update({'mode':'READ_ONLY','auto_fix_eligible':0,'qa_policy':'UNIFIED_APPROVAL_READ_ONLY',
                        'fabric_master_styles':60,'style_confirmations':49,'additional_style_confirmations':17,'fabric_approval_source':'USER_MASTER_EXACT_OR_USER_CONFIRMED_ALIAS',
                        'pattern_history_note':'Prior scan rows retain old Pattern evidence; description fallback for historical rows requires Shopify re-fetch'})
        (out/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
        msummary={'source':'Fabric Composition - Sheet1.csv + user Style confirmations',
                  'master_styles':60,'style_confirmations':49,'additional_style_confirmations':17,'total_rows':count['scanned'],
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
