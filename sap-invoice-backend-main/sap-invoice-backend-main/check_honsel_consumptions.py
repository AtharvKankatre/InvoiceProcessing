import os, sys, django
from pprint import pprint

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sap_invoice.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from retail.models import InvoiceEntry
from sales.models import InvoiceEntryConsumption

honsel_entries = InvoiceEntry.objects.filter(retail_invoice_number__in=[
    '2252600001/A',
    '2252600002/A',
])

for entry in honsel_entries:
    print(f"\nOUTGOING: {entry.retail_invoice_number} | QTY: {entry.qty} | RATE USD: {entry.usd_rate} | RATE INR: {entry.inr_rate}")
    
    consumptions = InvoiceEntryConsumption.objects.filter(invoice_entry=entry)
    for c in consumptions:
        print(f"  -> CONSUMED: {c.consumed_qty} from INCOMING: {c.invoice.invoice_number}")
        print(f"     INCOMING RATES -> USD: {c.invoice.dollar_rate} | INR: {c.invoice.inr_rate} | Conv: {c.invoice.conversion_rate}")
