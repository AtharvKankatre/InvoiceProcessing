import os
import django
import sys
from decimal import Decimal
from django.db.models import Q, Sum, F, Value, DecimalField
from django.db.models.functions import Coalesce, NullIf

# Setup Django environment
sys.path.append(r"d:\Inpinite\InvoiceTest\sap-invoice-backend-main\sap-invoice-backend-main")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sap_invoice.settings")
django.setup()

from sales.models import Invoice, InvoiceRetailPartMap, InvoiceEntryConsumption
from retail.models import InvoiceEntry
from sales.services.stock_ledger import StockLedgerService
from datetime import datetime

customer_code = "10365"

# 1. Identify all Name/Code variations for Honsel
print("--- Deep Name Search for Honsel/Mexico ---")

# Search for ANY name containing "Honsel" or "Mexico" or "Maxico"
distinct_in = list(Invoice.objects.filter(Q(customer_name__icontains="Honsel") | Q(customer_name__icontains="Mex")).values('customer_name', 'customer_code').distinct())
print(f"Names/Codes in Invoice table: {distinct_in}")

distinct_map = list(InvoiceRetailPartMap.objects.filter(Q(company_name__icontains="Honsel") | Q(company_name__icontains="Mex")).values('company_name', 'customer_code').distinct())
print(f"Names/Codes in Retail Mapping table: {distinct_map}")

all_names = set([v['customer_name'] for v in distinct_in if v['customer_name']])
all_names.update([v['company_name'] for v in distinct_map if v['company_name']])

# 2. Check Stock Ledger rows for ALL these names
print("\n--- Stock Ledger Rows for these names (as of 31-03-2024) ---")
to_date = datetime.strptime("2024-03-31", "%Y-%m-%d").date()
stock_ledger = StockLedgerService()
ledger_data = stock_ledger.get_ledger_data(to_date=to_date)

for row in ledger_data:
    if row['Party Name'] in all_names or row.get('Code No. Stock AC') == customer_code:
        print(f"Row: {row['Party Name']} | Code: {row.get('Code No. Stock AC')} | Opening: {row['Opening Stock Qty']} | Incoming: {row['Shipment to WH (Add) Qty']} | Outgoing: {row['Despatch (Less) Qty']} | Closing: {row['Closing Stock Qty']}")

print(f"\n--- Checking for ALL 'Future Consumptions' (OUT occurring chronological mismatch) ---")
# Use a wider range or NO date filter on OUT to see what's happening
mismatches = InvoiceEntryConsumption.objects.filter(
    invoice__date__gt=F('invoice_entry__date'),
    invoice__customer_name__in=all_names
).select_related('invoice', 'invoice_entry').order_by('invoice_entry__date')

total_mismatch = 0
if mismatches.exists():
    print(f"Found {mismatches.count()} mismatched consumption records:")
    for m in mismatches:
        print(f"  {m.invoice_entry.retail_invoice_number} ({m.invoice_entry.date}) consumes {m.invoice.invoice_number} ({m.invoice.date}) | Qty: {m.consumed_qty}")
        total_mismatch += m.consumed_qty
    print(f"Total Mismatched Qty (Total Future Consumption): {total_mismatch}")
else:
    print("No mismatched consumptions found.")

# 4. Raw Aggregated Totals
print("\n--- Raw Aggregated Totals (All Time) ---")
all_in = Invoice.objects.filter(customer_name__in=all_names).aggregate(
    total=Coalesce(Sum(Coalesce(NullIf(F('invoice_qty'), Value(0)), F('qty'))), 0)
)['total']

retail_parts = InvoiceRetailPartMap.objects.filter(company_name__in=all_names).values_list('retail_part_number', flat=True)
all_out = InvoiceEntry.objects.filter(part_number__in=retail_parts).aggregate(total=Coalesce(Sum('qty'), 0))['total']

print(f"Total Incoming: {all_in}")
print(f"Total Outgoing: {all_out}")
print(f"Total Balance:  {all_in - all_out}")
