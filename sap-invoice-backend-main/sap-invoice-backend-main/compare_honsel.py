"""
Debug: Compare Sheet 1 vs Sheet 3 component values for Nemak Dillingen.
"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sap_invoice.settings')
django.setup()

from decimal import Decimal
from django.db.models import Sum, F, DecimalField, Value
from django.db.models.functions import Coalesce, NullIf
from sales.models import Invoice, InvoiceRetailPartMap, InvoiceEntryConsumption
from retail.models import InvoiceEntry
from sales.services.stock_ledger import StockLedgerService

CUSTOMER = 'Nemak Dillingen Casting GmbH & Co.'

print(f"=== DEBUG: {CUSTOMER} ===\n")

# --- Sheet 1 approach (by customer) ---
print("--- SHEET 1 (Stock Ledger) approach ---")
# Incoming (all time, no date filter)
incoming = Invoice.objects.filter(customer_name=CUSTOMER).aggregate(
    total_qty=Coalesce(Sum(Coalesce(NullIf(F('invoice_qty'), Value(0)), F('qty'))), 0),
    total_fc=Coalesce(Sum('dollar_total'), Decimal(0), output_field=DecimalField()),
    total_inr=Coalesce(Sum('inr_total'), Decimal(0), output_field=DecimalField())
)
print(f"Incoming: qty={incoming['total_qty']}, fc={incoming['total_fc']}, inr={incoming['total_inr']}")

retail_parts = list(InvoiceRetailPartMap.objects.filter(company_name=CUSTOMER).values_list('retail_part_number', flat=True))
print(f"Retail parts mapped: {retail_parts}")

out_entries = InvoiceEntry.objects.filter(
    part_number__in=retail_parts
).prefetch_related('consumptions', 'consumptions__invoice')
out_qty, out_fc, out_inr = StockLedgerService._get_hybrid_outgoing(out_entries)
print(f"Outgoing (hybrid): qty={out_qty}, fc={out_fc}, inr={out_inr}")

s_fc, s_inr, e_inr = StockLedgerService._get_cost_adjustments(out_entries)
print(f"Adjustments: surcharge_fc={s_fc}, surcharge_inr={s_inr}, exchange_inr={e_inr}")

closing_inr_s1 = (incoming['total_inr'] or Decimal(0)) - out_inr - s_inr - e_inr
print(f"Closing INR (Sheet 1): {round(float(closing_inr_s1), 2)}")

# --- Sheet 3 approach (by part -> customer) ---
print("\n--- SHEET 3 (Part-Wise Tracking) approach ---")

# Get part mappings
retail_to_sale = {}
retail_to_company = {}
for pm in InvoiceRetailPartMap.objects.all():
    retail_to_company[pm.retail_part_number] = pm.company_name
    if pm.sale_part_number:
        retail_to_sale[pm.retail_part_number] = pm.sale_part_number
        if pm.sale_part_number not in retail_to_company:
            retail_to_company[pm.sale_part_number] = pm.company_name
        if pm.sale_part_number not in retail_to_sale:
            retail_to_sale[pm.sale_part_number] = pm.sale_part_number

# Find parts for this customer
nemak_parts_retail = set()
nemak_parts_sale = set()
for pm in InvoiceRetailPartMap.objects.filter(company_name=CUSTOMER):
    nemak_parts_retail.add(pm.retail_part_number)
    if pm.sale_part_number:
        nemak_parts_sale.add(pm.sale_part_number)

print(f"Retail part numbers: {nemak_parts_retail}")
print(f"Sale part numbers: {nemak_parts_sale}")

# Check incoming invoices - what part numbers are they under?
incoming_parts = Invoice.objects.filter(customer_name=CUSTOMER).values_list('part_number', flat=True).distinct()
print(f"Incoming invoice part numbers: {list(incoming_parts)}")

# Check if incoming part numbers match the sale part numbers
incoming_set = set(incoming_parts)
print(f"\nIncoming parts in sale_parts: {incoming_set & nemak_parts_sale}")
print(f"Incoming parts NOT in sale_parts: {incoming_set - nemak_parts_sale}")

# Now trace Sheet 3's grouped entries
all_entries = InvoiceEntry.objects.all().prefetch_related('consumptions', 'consumptions__invoice')
grouped = {}
for entry in all_entries:
    rp = entry.part_number
    canonical = retail_to_sale.get(rp, rp)
    cust = retail_to_company.get(rp, "Unknown")
    if cust == CUSTOMER:
        if canonical not in grouped:
            grouped[canonical] = []
        grouped[canonical].append(entry)

print(f"\nSheet 3 grouped outgoing parts for {CUSTOMER}:")
total_s3_out_inr = Decimal(0)
total_s3_adj_s_inr = Decimal(0)
total_s3_adj_e_inr = Decimal(0)
for part, entries_list in sorted(grouped.items()):
    oq, ofc, oinr = StockLedgerService._get_hybrid_outgoing(entries_list)
    sf, si, ei = StockLedgerService._get_cost_adjustments(entries_list)
    total_s3_out_inr += oinr
    total_s3_adj_s_inr += si
    total_s3_adj_e_inr += ei
    print(f"  Part {part}: {len(entries_list)} entries, out_inr={oinr}, s_inr={si}, e_inr={ei}")

print(f"\nTotal Sheet 3 outgoing INR: {total_s3_out_inr}")
print(f"Total Sheet 3 surcharge INR: {total_s3_adj_s_inr}")
print(f"Total Sheet 3 exchange INR: {total_s3_adj_e_inr}")

# Check if incoming is the same
inc_s3 = Decimal(0)
inc_parts_s3 = set()
for part in set(list(grouped.keys()) + list(incoming_set)):
    inc = Invoice.objects.filter(customer_name=CUSTOMER, part_number=part).aggregate(
        inr=Coalesce(Sum('inr_total'), Decimal(0), output_field=DecimalField())
    )
    if inc['inr']:
        inc_s3 += inc['inr']
        inc_parts_s3.add(part)

print(f"\nSheet 3 incoming INR (summed by part): {inc_s3}")
print(f"Sheet 1 incoming INR: {incoming['total_inr']}")
print(f"Incoming difference: {float(inc_s3) - float(incoming['total_inr'] or 0)}")

closing_inr_s3 = inc_s3 - total_s3_out_inr - total_s3_adj_s_inr - total_s3_adj_e_inr
print(f"\nReconstructed Sheet 3 Closing INR: {round(float(closing_inr_s3), 2)}")
print(f"Sheet 1 Closing INR:               {round(float(closing_inr_s1), 2)}")
print(f"Difference:                         {round(float(closing_inr_s3 - closing_inr_s1), 2)}")
