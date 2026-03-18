"""
Run on the server:  python rename_innio.py

Renames customer/company name from 'INNIO' to 'INNIO Distributed Power Company'
in both Invoice and InvoiceRetailPartMap tables.
"""
import os, sys, django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sap_invoice.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from sales.models import Invoice, InvoiceRetailPartMap

OLD_NAME = 'INNIO'
NEW_NAME = 'INNIO Distributed Power Company'

inv_count = Invoice.objects.filter(customer_name=OLD_NAME).count()
map_count = InvoiceRetailPartMap.objects.filter(company_name=OLD_NAME).count()

print(f"Found {inv_count} Invoice rows and {map_count} RetailPartMap rows with name '{OLD_NAME}'")

if inv_count or map_count:
    Invoice.objects.filter(customer_name=OLD_NAME).update(customer_name=NEW_NAME)
    InvoiceRetailPartMap.objects.filter(company_name=OLD_NAME).update(company_name=NEW_NAME)
    print(f"✅ Renamed '{OLD_NAME}' → '{NEW_NAME}' in {inv_count + map_count} total rows.")
else:
    print("No rows found to update.")
