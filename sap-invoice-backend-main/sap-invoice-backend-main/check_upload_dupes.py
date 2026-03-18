import os, sys, django
from pprint import pprint

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sap_invoice.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from retail.models import InvoiceEntry

entries = InvoiceEntry.objects.filter(retail_invoice_number='2242500426/A')
print(f"Found {entries.count()} entries for 2242500426/A")

for e in entries:
    print(f"--- ID: {e.id} ---")
    print(f"Date: {e.date}")
    print(f"Part Number: {e.part_number}")
    print(f"Created At: {e.created_at}")
    print(f"Retail Invoice Number: {e.retail_invoice_number}")
    print(f"USD Rate: {e.usd_rate}")
    print(f"INR Rate: {e.inr_rate}")
