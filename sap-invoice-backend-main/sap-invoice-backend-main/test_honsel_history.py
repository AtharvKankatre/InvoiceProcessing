import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sap_invoice.settings")
django.setup()

from sales.views import PartHistoryViewSet
from rest_framework.test import APIRequestFactory

factory = APIRequestFactory()
view = PartHistoryViewSet.as_view({'get': 'list'})

request = factory.get('/api/part-history/?company=Martinrea%20Honsel%20Mexico%20S.A.%20de%20C.V&part_number=CFORDFG009E5EAA&from_date=2024-09-01&to_date=2025-03-01')
response = view(request)

if hasattr(response, 'data'):
    data = response.data
    results = data.get('results', data) if isinstance(data, dict) else data
    print(f"Total rows: {len(results)}")
    
    for i, r in enumerate(results):
        print(f"--- ROW {i} ---")
        print(f"Date: {r.get('date')} | Type: {r.get('type')}")
        print(f"Qty: {r.get('qty')} | FC Value: {r.get('fc_value')}")
        print(f"Surcharge: {r.get('surcharge')} | Exchange Gain: {r.get('exchange_gain')}")
        print(f"Running Bal Qty: {r.get('running_balance_qty')} | Running Bal Value: {r.get('running_balance_value')}")
else:
    print(response.status_code, response.content)
