import re, html, csv, json, io, zipfile, argparse, os, time, collections, sys
from html.parser import HTMLParser
from pathlib import Path

COLORS = ['black','white','navy','blue','red','pink','purple','green','yellow','orange','gold','silver','gray','grey','brown','beige','maroon','teal','turquoise','aqua','cream','khaki','olive','burgundy','coral','tan']
COLOR_ALIAS = {'grey':'gray'}
PATTERNS = [('camouflage',r'\b(?:camo|camouflage)\b'),('splatter',r'\b(?:splatter|paint splashes|paint splash)\b'),('halftone',r'\bhalftone\b'),('floral',r'\b(?:floral|flower pattern)\b'),('striped',r'\b(?:stripe|stripes|striped)\b'),('plaid',r'\bplaid\b'),('geometric',r'\bgeometric\b'),('tie-dye',r'\btie[- ]dye\b'),('polka dot',r'\bpolka[ -]?dot\b'),('checkered',r'\b(?:checkerboard|checkered)\b'),('leopard print',r'\bleopard[ -]?print\b'),('abstract',r'\babstract\b')]

class StripHTML(HTMLParser):
 def __init__(self): super().__init__(); self.parts=[]
 def handle_data(self,s): self.parts.append(s)
def plain(s):
 s=html.unescape(s or ''); p=StripHTML(); p.feed(s); return re.sub(r'\s+',' ',' '.join(p.parts)).strip()
def normalize_color(x): return COLOR_ALIAS.get(x.lower(),x.lower()).title()
def extract(title,description,variant='',tags=''):
 """Conservative extraction: exact color and pattern terms; material only explicit fabric statements. Never guesses from product category."""
 t=plain(title); d=plain(description); v=plain(variant)
 out={'color':'','pattern':'','material':'','confidence':'','evidence':'','review_reason':''}
 # Variant is often size or style; do not interpret a color mentioned merely in long model names as confirmed variant option.
 vt=re.search(r'\b(?:color|colour)\s*[:=]\s*([^,;|]+)',v,re.I)
 explicit = vt.group(1) if vt else ''
 title_first=t.split('|')[0].split(',')[0]
 color_area = explicit or title_first[:180]
 cmatches = []
 for m in re.finditer(r'\b(?:'+ '|'.join(COLORS)+r')\b',color_area,re.I):
  c=normalize_color(m.group().lower());
  if c not in cmatches: cmatches.append(c)
 if 1 <= len(cmatches) <= 3:
  out['color']='/'.join(cmatches); out['evidence']+='color:title_or_variant;';
 elif len(cmatches)>3: out['review_reason']+='color_many_candidates;'
 else: out['review_reason']+='color_not_in_title;'
 # Explicit design pattern, not generic graphic printing. For ambiguous >2 terms require review.
 matches=[name for name,regex in PATTERNS if re.search(regex,t+' '+d[:900],re.I)]
 if len(matches)==1: out['pattern']=matches[0].title();out['evidence']+='pattern:text;'
 elif len(matches)>1: out['review_reason']+='multiple_pattern_candidates;'
 else: out['review_reason']+='pattern_not_identified;'
 # Material statements only: '100% Polyester', 'made from polyester', 'material: cotton'. Avoid material if text speaks about multiple compositions.
 material_text=d[:5000]
 material_finds=set()
 for m in re.finditer(r'(?:\b(?:\d{1,3}\s*%\s*)?(?:polyester|cotton|spandex|nylon|rayon)\b)',material_text,re.I):
  token=m.group().lower();
  if re.search(r'\d+\s*%|(?:material|fabric|made|composition|blend)',material_text[max(0,m.start()-45):m.start()],re.I):
   mat=re.search(r'polyester|cotton|spandex|nylon|rayon',token,re.I).group().title(); material_finds.add(mat)
 if len(material_finds)==1:
  mat=next(iter(material_finds))
  # More than one percentage in description may encode multiple color-specific compositions; mark review.
  if len(re.findall(r'\d{1,3}\s*%\s*(?:polyester|cotton|spandex|nylon|rayon)',material_text,re.I)) <=1:
   out['material']=mat;out['evidence']+='material:description;'
  else: out['review_reason']+='material_multiple_compositions;'
 elif len(material_finds)>1: out['review_reason']+='material_multiple_fabrics;'
 else: out['review_reason']+='material_not_explicit;'
 # Does not infer composition from EasySlide or material by niche.
 complete=sum(bool(out[k]) for k in ('color','pattern','material'))
 out['confidence']='candidate_review' if complete else 'insufficient'
 return out

def parse_item(d):
 a=d.get('productAttributes') or {}; name=d.get('name','')
 return {'id':d.get('offerId') or d.get('id',''),'language':d.get('contentLanguage') or d.get('language','en'),'feed_label':d.get('feedLabel') or d.get('feed label','US'),'title':a.get('title') or d.get('title',''),'description':a.get('description') or d.get('description',''),'color':a.get('color') or d.get('color',''),'pattern':a.get('pattern') or d.get('pattern',''),'material':a.get('material') or d.get('material',''),'variant':d.get('variant option(name:value)',''),'shopify_product_id':d.get('shopify product id',''),'name':name}

def is_missing_color(s): return not (s or '').strip().strip("'\"") or (s or '').strip().strip("'\"").lower() in ('one color','one colour','onecolor')

def report(items,out_dir,limit=0,source='export'):
 out=Path(out_dir);out.mkdir(parents=True,exist_ok=True)
 cols=['id','language','feed_label','title','current_color','current_pattern','current_material','proposed_color','proposed_pattern','proposed_material','confidence','evidence','review_reason','shopify_product_id','description_source']
 counts=collections.Counter()
 with (out/'audit.csv').open('w',encoding='utf-8-sig',newline='') as fa,(out/'candidates_review.csv').open('w',encoding='utf-8-sig',newline='') as fc:
  aw=csv.DictWriter(fa,fieldnames=cols);cw=csv.DictWriter(fc,fieldnames=cols);aw.writeheader();cw.writeheader()
  for i,d in enumerate(items):
   if limit and i>=limit: break
   p=parse_item(d);counts['scanned']+=1
   missing={'color':is_missing_color(p['color']),'pattern':not p['pattern'].strip(),'material':not p['material'].strip()}
   for k,miss in missing.items():
    if miss: counts['missing_'+k]+=1
   if not any(missing.values()):counts['already_filled']+=1;continue
   e=extract(p['title'],p['description'],p['variant'])
   row={'id':p['id'],'language':p['language'],'feed_label':p['feed_label'],'title':p['title'],'current_color':p['color'],'current_pattern':p['pattern'],'current_material':p['material'],'proposed_color':e['color'] if missing['color'] else '', 'proposed_pattern':e['pattern'] if missing['pattern'] else '','proposed_material':e['material'] if missing['material'] else '', 'confidence':e['confidence'],'evidence':e['evidence'],'review_reason':e['review_reason'],'shopify_product_id':p['shopify_product_id'],'description_source':source}
   aw.writerow(row)
   if any(row['proposed_'+k] for k in ('color','pattern','material')):cw.writerow(row);counts['has_proposals']+=1
   if all(row['proposed_'+k] for k in ('color','pattern','material') if missing[k]): counts['all_missing_fields_proposed']+=1
 with (out/'summary.json').open('w',encoding='utf-8') as f:json.dump(dict(counts),f,indent=2)
 print(json.dumps(dict(counts),indent=2));return counts

def iterate_zip(path):
 with zipfile.ZipFile(path) as z:
  nm=next((n for n in z.namelist() if n.lower().endswith(('.csv','.tsv'))),None)
  if not nm: raise ValueError('No csv/tsv inside zip')
  with z.open(nm) as b:
   f=io.TextIOWrapper(b,encoding='utf-8-sig',newline='');r=csv.DictReader(f,delimiter='\t' if nm.endswith('.tsv') else ',')
   yield from r

def run():
 ap=argparse.ArgumentParser(description='ChipteeAmz GMC attributes - read-only by default')
 sub=ap.add_subparsers(dest='cmd',required=True)
 a=sub.add_parser('audit-export');a.add_argument('--zip',required=True);a.add_argument('--out',default='out');a.add_argument('--limit',type=int,default=5000)
 b=sub.add_parser('audit-live');b.add_argument('--out',default='out');b.add_argument('--limit',type=int,default=500)
 c=sub.add_parser('push-reviewed');c.add_argument('--csv',required=True);c.add_argument('--confirm',default='')
 p=ap.parse_args()
 if p.cmd=='audit-export':report(iterate_zip(p.zip),p.out,p.limit,source='GMC_export_description_(verify_against_Shopify)')
 elif p.cmd=='audit-live':
  from live import merchant_items,shopify_descriptions
  rows=list(merchant_items(p.limit))
  # Shopify is authoritative: replace GMC description via verified match to Shopify product ID
  shopify_descriptions(rows)
  report(rows,p.out,0,source='Shopify_default_description_API')
 elif p.cmd=='push-reviewed':
  if p.confirm!='I_UNDERSTAND_THIS_WRITES_TO_GMC':raise SystemExit('Blocked: review data first; explicit confirmation required')
  from live import push_reviewed
  push_reviewed(p.csv)
if __name__=='__main__':run()
