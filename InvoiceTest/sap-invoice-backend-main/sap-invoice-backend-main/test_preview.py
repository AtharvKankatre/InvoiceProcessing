import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sap_invoice.settings')
django.setup()

from rest_framework_simplejwt.tokens import RefreshToken
from user.models import User
from django.test import Client

c = Client()
user = User.objects.first()
token = str(RefreshToken.for_user(user).access_token)

with open('../../test_staging_scenarios.xlsx', 'rb') as fp:
    response = c.post('/api/retail/bulk-preview/', {'file': fp}, HTTP_AUTHORIZATION=f'Bearer {token}')

print('Status:', response.status_code)
if response.status_code == 200:
    data = response.json()
    print("KEYS:", data['part_inventory'].keys())
    for part, info in data['part_inventory'].items():
        print(f"Part: {part}, Avail Qty: {info['available_qty']}, Num Invoices: {len(info['invoices'])}")
else:
    print("Content:", response.content.decode())
