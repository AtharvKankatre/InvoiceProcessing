"""
Run on the server:  python check_honsel_dates.py

Finds all "future consumption" cases for Martinrea Honsel Mexico
where the outgoing (retail) date is BEFORE the incoming (warehouse) date.
"""
import os, sys, django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sap_invoice.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from sales.models import Invoice, InvoiceEntryConsumption

# Find Honsel Mexico invoices
from django.db.models import Q
honsel = Invoice.objects.filter(Q(customer_name__icontains='honsel') & Q(customer_name__icontains='m'))
print(f"=== Martinrea Honsel Mexico Invoices ===")
print(f"Total incoming invoices: {honsel.count()}\n")

# Get all consumption records linked to these invoices
consumptions = InvoiceEntryConsumption.objects.filter(
    invoice__in=honsel
).select_related('invoice', 'invoice_entry')

future_total = 0
future_count = 0

print("=== Future Consumptions (OUT date < IN date) ===\n")
print(f"{'OUT Invoice':<25} {'OUT Date':<15} {'IN Invoice':<25} {'IN Date':<15} {'Qty':>8}")
print("-" * 95)

for c in consumptions:
    in_date = c.invoice.date
    out_date = c.invoice_entry.date
    if out_date < in_date:
        future_count += 1
        future_total += (c.consumed_qty or 0)
        print(f"{c.invoice_entry.retail_invoice_number or 'N/A':<25} "
              f"{str(out_date):<15} "
              f"{c.invoice.invoice_number:<25} "
              f"{str(in_date):<15} "
              f"{c.consumed_qty:>8}")

print("-" * 95)
print(f"\nTotal future consumptions: {future_count} records")
print(f"Total units affected: {future_total}")
print(f"\nThese OUT transactions are dated BEFORE their IN stock arrived,")
print(f"causing a {future_total} unit hole in the opening balance.")
