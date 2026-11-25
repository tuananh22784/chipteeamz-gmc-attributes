"""Read-only Merchant + Shopify connectors. No GMC write code in V1.1."""
import os
import re
import time
import requests

OFFER_ID = re.compile(r'^shopify_[A-Za-z]{2}_([0-9]+)_([0-9]+)$')

def token():
    import google.auth
    from google.auth.transport.requests import Request
    credentials, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/content'])
    credentials.refresh(Request())
    return credentials.token

def google_request(method, path, **kwargs):
    if not path.startswith('https://'):
        path = 'https://merchantapi.googleapis.com/' + path.lstrip('/')
    for attempt in range(5):
        response = requests.request(method, path,
                                    headers={'Authorization': 'Bearer ' + token()},
                                    timeout=90, **kwargs)
        if response.status_code in (429, 500, 502, 503, 504) and attempt < 4:
            time.sleep(2 ** attempt)
            continue
        if not response.ok:
            try:
                error = response.json().get('error', {})
                print('Merchant API HTTP status:', response.status_code)
                print('Merchant API error status:', error.get('status', ''))
                print('Merchant API error message:', str(error.get('message', ''))[:700])
            except ValueError:
                print('Merchant API HTTP status:', response.status_code)
        response.raise_for_status()
        return response.json() if response.content else {}

def merchant_items(limit=0):
    account = os.environ['GMC_ACCOUNT_ID'].strip()
    params = {'pageSize': min(1000, limit) if limit else 1000}
    scanned = 0
    while True:
        payload = google_request('GET', f'products/v1/accounts/{account}/products', params=params)
        for item in payload.get('products', []):
            yield item
            scanned += 1
            if limit and scanned >= limit:
                return
        if not payload.get('nextPageToken'):
            return
        params['pageToken'] = payload['nextPageToken']

def shopify_graphql(query, variables):
    domain = os.environ['SHOPIFY_SHOP_DOMAIN'].strip()
    version = os.environ.get('SHOPIFY_API_VERSION', '2026-10')
    response = requests.post(
        f'https://{domain}/admin/api/{version}/graphql.json',
        json={'query': query, 'variables': variables},
        headers={'X-Shopify-Access-Token': os.environ['SHOPIFY_ADMIN_TOKEN']},
        timeout=90,
    )
    response.raise_for_status()
    result = response.json()
    if result.get('errors'):
        raise RuntimeError('Shopify GraphQL errors: ' + str(result['errors'])[:500])
    return result['data']

def shopify_descriptions(rows):
    """Set verified only if BOTH Shopify product AND requested variant are confirmed.

    Shopify API errors stop the audit rather than pretending the returned GMC description
    came from Shopify. Unsupported IDs receive explicit status.
    """
    index = {}
    for item in rows:
        item['_shopify_status'] = 'UNMATCHED_OFFER_ID'
        offer_id = item.get('offerId', '')
        match = OFFER_ID.fullmatch(offer_id)
        if match:
            pid, vid = match.groups()
            item['_shopify_product_id'] = pid
            item['_shopify_variant_id'] = vid
            item['_shopify_status'] = 'SHOPIFY_NOT_FOUND'
            index.setdefault(pid, []).append(item)
    if not index:
        return
    # Request first 100 variant nodes. If a desired variant isn't present,
    # mark VARIANT_NOT_FOUND_OR_UNPAGINATED; NEVER substitute another variant.
    query = '''query($ids: [ID!]!) {
        nodes(ids: $ids) {
          ... on Product {
            legacyResourceId
            descriptionHtml
            variants(first: 100) {
              nodes { legacyResourceId selectedOptions { name value } }
              pageInfo { hasNextPage }
            }
          }
        }
    }'''
    products = {}
    ids = list(index)
    for start in range(0, len(ids), 8):
        batch = ids[start:start + 8]
        result = shopify_graphql(query, {'ids': ['gid://shopify/Product/' + pid for pid in batch]})
        for product in result.get('nodes', []):
            if product and product.get('legacyResourceId'):
                products[str(product['legacyResourceId'])] = product
    for pid, associated in index.items():
        product = products.get(pid)
        if not product:
            continue
        variants = {str(v.get('legacyResourceId')): v for v in product.get('variants', {}).get('nodes', [])}
        more_pages = product.get('variants', {}).get('pageInfo', {}).get('hasNextPage', False)
        for item in associated:
            vid = item['_shopify_variant_id']
            variant = variants.get(vid)
            if not variant:
                item['_shopify_status'] = 'VARIANT_NOT_FOUND_OR_UNPAGINATED' if more_pages else 'VARIANT_NOT_FOUND'
                continue
            item['_shopify_status'] = 'SHOPIFY_VERIFIED'
            item.setdefault('productAttributes', {})['description'] = product.get('descriptionHtml') or ''
            opts = [str(o.get('value', '')).strip() for o in variant.get('selectedOptions', [])
                    if str(o.get('name', '')).lower() in ('color', 'colour')]
            if len(opts) == 1:
                item['_selected_color'] = opts[0]
