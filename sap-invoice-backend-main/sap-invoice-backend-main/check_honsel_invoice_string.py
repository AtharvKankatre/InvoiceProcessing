import os, sys, django
from pprint import pprint

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sap_invoice.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from sales.models import Invoice

invoices = Invoice.objects.filter(invoice_number__icontains='2252600001')

print(f"Found {invoices.count()} invoices containing '2252600001'")

for inv in invoices:
    print(f"--- ID: {inv.id} ---")
    print(f"Raw Invoice Number: {repr(inv.invoice_number)}")
    print(f"Part Number: {repr(inv.part_number)}")
    print(f"Qty: {inv.qty}")

print("\nTrying exact match:")
exact = Invoice.objects.filter(invoice_number='2252600001')
print(f"Exact match count: {exact.count()}")
