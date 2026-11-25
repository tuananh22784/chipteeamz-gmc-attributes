"""Production connectors. Calls to Merchant API are read-only except explicit push-reviewed.
Auth: GOOGLE_APPLICATION_CREDENTIALS service account authorized to Merchant Center,
or another ADC credential with content scope. Never commit credentials.
"""
import os,re,csv,time,json,requests
from urllib.parse import quote

def token():
 import google.auth
 from google.auth.transport.requests import Request
 creds,project=google.auth.default(scopes=['https://www.googleapis.com/auth/content'])
 creds.refresh(Request());return creds.token


def google_request(method, url, **kwargs):
    import requests
    import google.auth
    from google.auth.transport.requests import Request

    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/content"]
    )
    credentials.refresh(Request())

    headers = kwargs.pop("headers", {})
    headers["Authorization"] = f"Bearer {credentials.token}"

    
    # Support both relative and absolute Merchant API URLs
    if url.startswith("/"):
        url = url.lstrip("/")

    if not url.startswith(("https://", "http://")):
        url = "https://merchantapi.googleapis.com/" + url

    r = requests.request(
        method,
        url,
        headers=headers,
        timeout=60,
        **kwargs
    )


    if not r.ok:
        try:
            error_data = r.json().get("error", {})
            print("Merchant API HTTP status:", r.status_code)
            print("Merchant API error status:", error_data.get("status", ""))
            print("Merchant API error message:", error_data.get("message", ""))
        except ValueError:
            print("Merchant API returned a non-JSON error response")

    r.raise_for_status()
    return r.json() if r.content else {}


def merchant_items(limit=0):
 account=os.environ['GMC_ACCOUNT_ID'];params={'pageSize':min(1000,limit) if limit else 1000};scanned=0
 while True:
  payload=google_request('GET',f'products/v1/accounts/{account}/products',params=params)
  for item in payload.get('products',[]):
   yield item;scanned+=1
   if limit and scanned>=limit:return
  if not payload.get('nextPageToken'):break
  params['pageToken']=payload['nextPageToken']

def shopify_graphql(query,variables):
 domain=os.environ['SHOPIFY_SHOP_DOMAIN'];tok=os.environ['SHOPIFY_ADMIN_TOKEN']
 api_version=os.environ.get('SHOPIFY_API_VERSION','2026-10')
 r=requests.post(f'https://{domain}/admin/api/{api_version}/graphql.json',json={'query':query,'variables':variables},headers={'X-Shopify-Access-Token':tok},timeout=90)
 r.raise_for_status();data=r.json()
 if data.get('errors'):raise RuntimeError('Shopify GraphQL request error '+str(data['errors'])[:400])
 return data['data']

def shopify_descriptions(rows):
 # Detect the real product ID from processed GMC offerId, not from assumed template.
 ids=[];related={}
 for d in rows:
  m=re.fullmatch(r'shopify_[A-Za-z]{2}_([0-9]+)_([0-9]+)',d.get('offerId',''))
  if m:
   pid=m.group(1);ids.append(pid);related.setdefault(pid,[]).append(d)
 query='query($ids:[ID!]!){nodes(ids:$ids){... on Product { id legacyResourceId descriptionHtml title variants(first:100){nodes{legacyResourceId title selectedOptions{name value}}}}}}'
 found={}
 for start in range(0,len(set(ids)),40):
  batch=list(dict.fromkeys(ids))[start:start+40]
  data=shopify_graphql(query,{'ids':[f'gid://shopify/Product/{pid}' for pid in batch]})
  for node in data.get('nodes',[]):
   if node:found[str(node['legacyResourceId'])]=node
 for pid,associated in related.items():
  p=found.get(pid)
  if not p:continue
  variants={str(v['legacyResourceId']):v for v in p['variants']['nodes']}
  for d in associated:
   m=re.fullmatch(r'shopify_[A-Za-z]{2}_([0-9]+)_([0-9]+)',d.get('offerId',''))
   v=variants.get(m.group(2)) if m else None
   # Skip if variant can't be confirmed; don't attach another variant's properties.
   if not v:continue
   a=d.setdefault('productAttributes',{})
   a['description']=p['descriptionHtml']
   # Only append selected color option, not sizes or other unverified strings
   for opt in v.get('selectedOptions',[]):
    if opt['name'].lower() in ('color','colour'):d['variant option(name:value)']='Color: '+opt['value']
   d['shopify product id']=pid

def push_reviewed(filepath):
 """Push only explicitly approved rows. API source name must be supplemental, verified manually.
 Source CSV must include approved=yes and source=Shopify_verified; never push speculative audit CSV.
 """
 acc=os.environ['GMC_ACCOUNT_ID'];ds=os.environ['GMC_SUPPLEMENTAL_DATASOURCE']
 if not re.fullmatch(rf'accounts/{re.escape(acc)}/dataSources/\d+',ds):raise ValueError('Bad supplemental data source name')
 # Confirm source type via API, fail closed.
 meta=google_request('GET',f'datasources/v1/{ds}')
 if meta.get('input')!='API' or 'supplementalProductDataSource' not in meta:raise RuntimeError('Datasource is not verified supplemental API source')
 sent=0
 with open(filepath,encoding='utf-8-sig',newline='') as f:
  for row in csv.DictReader(f):
   if row.get('approved','').lower()!='yes' or row.get('source')!='Shopify_verified':continue
   if not row.get('id') or not row.get('language') or not row.get('feed_label'):continue
   attrs={k:row['proposed_'+k].strip() for k in ('color','pattern','material') if row.get('proposed_'+k,'').strip()}
   if not attrs:continue
   data={'offerId':row['id'],'contentLanguage':row['language'],'feedLabel':row['feed_label'],'productAttributes':attrs}
   google_request('POST',f'products/v1/accounts/{acc}/productInputs:insert',params={'dataSource':ds},json=data)
   sent+=1
 print(f'Submitted {sent} approved rows. Re-read processed products before claiming success.')
