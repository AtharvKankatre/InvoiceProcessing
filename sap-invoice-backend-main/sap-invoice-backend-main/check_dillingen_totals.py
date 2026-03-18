import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sap_invoice.settings')
django.setup()

from sales.models import Invoice

print("=== CHECKING INCOMPLETE DATE INVOICES ===")

target_invoices = ['2242500508', '2242500527', '2252600663', '2252600664', '2252600715', '2252600348']

invoices = Invoice.objects.filter(invoice_number__in=target_invoices)

for inv in invoices:
    print(f"[{inv.date}] Invoice {inv.invoice_number} | Part: {inv.part_number} | Qty: {inv.qty} | Invoice Qty: {inv.invoice_qty} | Customer: {inv.customer_name}")

print("\n=== TOTALS FOR NEMAK DILLINGEN WITHIN DATE RANGE ===")
from django.db.models import Sum, F, Value
from django.db.models.functions import Coalesce, NullIf
from datetime import date

# simulate the query exactly like stock ledger does
qs = Invoice.objects.filter(
    customer_name__icontains="Nemak Dillingen",
    date__gte=date(2024, 12, 6),
    date__lte=date(2025, 3, 15)
).aggregate(
    total_qty=Coalesce(Sum(Coalesce(NullIf(F('invoice_qty'), Value(0)), F('qty'))), 0)
)
print(f"Total Qty exactly as Stock Ledger calculates: {qs['total_qty']}")
