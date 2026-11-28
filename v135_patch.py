from pathlib import Path
p=Path('/mnt/data/gmc_v135_work/attribute_sheet_sync.py')
s=p.read_text()
s=s.replace('from material_sheet_sync import GoogleSheets,load_csv,export_csv','from material_sheet_sync import GoogleSheets,load_csv,export_csv')
marker='def evidence_map(out):'
insert='''def explicit_pattern_description(description):
    """Only product-specific explicitly labeled pattern, not incidental motifs.

    Single-line pattern fields are authoritative; broad marketing text is not.
    """
    d=plain(description)
    matches=[]
    for m in re.finditer(r'(?im)^\\s*(?:fabric\\s+)?(?:design\\s+)?pattern\\s*[:=-]\\s*([^\\n.;]{1,90})',d):
        names=[name for name,rx in PATTERNS.items() if re.search(rx,m.group(1),re.I)]
        if len(names)==1:matches.append(names[0])
    unique=list(dict.fromkeys(matches))
    return unique[0] if len(unique)==1 else ''

def strict_auto_candidates(rows,evidence):
    """Auto approve only explicit garment color or explicitly labeled pattern.
    Check source IDs and avoid overwriting existing values.
    """
    result={'COLOR':0,'PATTERN':0}
    for r in rows:
        e=evidence.get(r['id'],{})
        if r.get('shopify_status')!='SHOPIFY_VERIFIED' or e.get('evidence_status')!='VERIFIED':continue
        if str(e.get('product_id'))!=str(r.get('shopify_product_id')) or str(e.get('variant_id'))!=str(r.get('shopify_variant_id')):continue
        desc=e.get('description','')
        if is_missing(r,'COLOR'):
            value=explicit_color_description(desc)
            if value and SAFE_COLOR.fullmatch(value) and norm(value) not in AMBIGUOUS:
                r['approved_color']=value;r['proposed_color']=value
                r['color_qa']='COLOR_EXPLICIT_DESCRIPTION_VERIFIED'
                r['color_evidence']='SHOPIFY_DESCRIPTION_EXPLICIT_GARMENT_COLOR'
                clear_stale_reason(r,'COLOR');result['COLOR']+=1
        if is_missing(r,'PATTERN'):
            value=explicit_pattern_description(desc)
            if value and SAFE_PATTERN.fullmatch(value):
                r['approved_pattern']=value;r['proposed_pattern']=value
                r['pattern_qa']='PATTERN_EXPLICIT_DESCRIPTION_VERIFIED'
                r['pattern_evidence']='SHOPIFY_DESCRIPTION_EXPLICIT_PATTERN_FIELD'
                clear_stale_reason(r,'PATTERN');result['PATTERN']+=1
    return result

'''
s=s.replace(marker,insert+marker)
# Require evidence exact identity in existing automated selected_color
s=s.replace("if e.get('evidence_status')!='VERIFIED':continue\n        color=", "if e.get('evidence_status')!='VERIFIED' or str(e.get('product_id'))!=str(row.get('shopify_product_id')) or str(e.get('variant_id'))!=str(row.get('shopify_variant_id')):continue\n        color=")
# Add sheet safe operations methods (wrapped outside library)
marker='def init_tabs(sheet):'
insert='''def append_only(sheet,tab,rows,fields):
    if not rows:return
    sheet.call('POST','/values/'+tab+'!A1:append?valueInputOption=RAW&insertDataOption=INSERT_ROWS',
               json={'values':[[str(r.get(k,'')) for k in fields] for r in rows]})

def reconcile_pending(sheet,tab,snapshot,desired,fields):
    """Non-destructive reconcile. Refuse stale snapshots instead of clearing sheet.

    Existing rows remain unchanged, including all concurrent staff-entered values.
    Deletes only rows that became approved, after exact preflight re-read.
    This is optimistic validation, not a cross-API atomic transaction.
    """
    latest=sheet.get_tab(tab,fields)
    if latest!=snapshot:
        raise RuntimeError('CONCURRENT_SHEET_CHANGE: '+tab+' changed since read; retry later. No pending rows changed.')
    def identity(r):
        return key_of(r)
    expected={identity(r):r for r in desired}
    old_keys=[identity(r) for r in snapshot]
    if len(set(old_keys))!=len(old_keys):raise ValueError('DUPLICATE_PENDING_KEYS '+tab)
    removal=[i+1 for i,r in enumerate(snapshot) if identity(r) not in expected] # row 1-index excluding header
    additions=[r for r in desired if identity(r) not in set(old_keys)]
    # Append first: a failure cannot lose unhandled work. Duplicates are prevented on next retry.
    append_only(sheet,tab,additions,fields)
    if removal:
        # Protect against employee changes between append and removal.
        actual=sheet.get_tab(tab,fields)
        if actual[:len(snapshot)]!=snapshot:
            raise RuntimeError('CONCURRENT_SHEET_CHANGE_AFTER_APPEND: '+tab+'; not deleting pending rows')
        meta=sheet.call('GET','?fields=sheets.properties(sheetId,title)')
        sid=next(x['properties']['sheetId'] for x in meta['sheets'] if x['properties']['title']==tab)
        requests=[{'deleteDimension':{'range':{'sheetId':sid,'dimension':'ROWS','startIndex':i,'endIndex':i+1}}} for i in sorted(removal,reverse=True)]
        sheet.call('POST',':batchUpdate',json={'requests':requests})

'''
s=s.replace(marker,insert+marker)
# Replace section writes
s=s.replace("    rules=read(TAB_RULES);hist=read(TAB_HISTORY)\n", "    rules=read(TAB_RULES);hist=read(TAB_HISTORY)\n    original_rules=list(rules);original_hist=list(hist)\n")
s=s.replace("    write(TAB_RULES,rules,RULE_FIELDS);write(TAB_HISTORY,hist,HISTORY_FIELDS)","""    if local:
        write(TAB_RULES,rules,RULE_FIELDS);write(TAB_HISTORY,hist,HISTORY_FIELDS)
    else:
        # Append-only durable approvals. Reject concurrent approvals before append.
        if sheet.get_tab(TAB_RULES,RULE_FIELDS)!=original_rules or sheet.get_tab(TAB_HISTORY,HISTORY_FIELDS)!=original_hist:
            raise RuntimeError('CONCURRENT_RULE_CHANGE: retry sync; no overwrites')
        append_only(sheet,TAB_RULES,rules[len(original_rules):],RULE_FIELDS)
        append_only(sheet,TAB_HISTORY,hist[len(original_hist):],HISTORY_FIELDS)
""")
s=s.replace("    auto_count=auto_apply_verified_color(rows,evidence)\n    new_count=apply_rules(rows,rules)", "    auto_count=auto_apply_verified_color(rows,evidence)\n    strict_count=strict_auto_candidates(rows,evidence)\n    new_count=apply_rules(rows,rules)")
s=s.replace("        write(TAB_PENDING[a],newly,PENDING_FIELDS)","        if local:write(TAB_PENDING[a],newly,PENDING_FIELDS)\n        else:reconcile_pending(sheet,TAB_PENDING[a],old,newly,PENDING_FIELDS)")
s=s.replace("'auto_verified_variant_colors':auto_count,'evidence_cached'", "'auto_verified_variant_colors':auto_count,'auto_verified_explicit_description':strict_count,'evidence_cached'")
p.write_text(s)
