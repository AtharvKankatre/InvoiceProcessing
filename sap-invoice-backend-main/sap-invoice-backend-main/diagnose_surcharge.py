"""
Run on the server:  python diagnose_surcharge.py

Inspects consumption records for Honsel (Mexico + Spain) to find WHY
surcharge/exchange gain are non-zero when the displayed rates look the same.
Shows raw DB values at full precision.
"""
import os, sys, django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sap_invoice.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from decimal import Decimal
from django.db.models import Q
from sales.models import Invoice, InvoiceEntryConsumption, InvoiceRetailPartMap
from retail.models import InvoiceEntry

# Find all retail parts mapped to Honsel (Mexico + Spain)
honsel_filter = Q(company_name__icontains='Martinrea Honsel Maxico') | Q(company_name__icontains='MARTINREA HONSEL SPAIN')
honsel_maps = InvoiceRetailPartMap.objects.filter(honsel_filter)
retail_parts = list(honsel_maps.values_list('retail_part_number', flat=True))
sap_parts = list(honsel_maps.values_list('sale_part_number', flat=True))
all_parts = list(set(retail_parts + sap_parts))

problem_invoices = [
    '2252600082/A',
    '2252600087/A',
    '2252600088/A',
    '2252600113/A',
    '2252600118/A',
    '2252600134/A',
    '2252600140/A',
]

print(f"Checking specifically for: {problem_invoices}\n")

# Get these specific outgoing entries
entries = InvoiceEntry.objects.filter(retail_invoice_number__in=problem_invoices).order_by('date')

problem_count = 0

for entry in entries:
    consumptions = InvoiceEntryConsumption.objects.filter(invoice_entry=entry).select_related('invoice', 'invoice_entry')
    
    if not consumptions.exists():
        continue
    
    for c in consumptions:
        inv = c.invoice          # Incoming
        ent = c.invoice_entry    # Outgoing
        
        # Raw DB values at FULL precision
        inv_dollar_rate_raw = inv.dollar_rate or Decimal(0)
        entry_usd_rate_raw = ent.usd_rate or Decimal(0)
        plating_raw = ent.plating_charges or Decimal(0)
        inv_conv_raw = inv.conversion_rate or Decimal(0)
        entry_conv_raw = ent.conversion_rate or Decimal(0)
        
        # Rounded to 2dp (what our formula now uses)
        inv_dr_2 = round(inv_dollar_rate_raw, 2)
        entry_ur_2 = round(entry_usd_rate_raw, 2)
        plating_2 = round(plating_raw, 2)
        adjusted_2 = entry_ur_2 - plating_2
        inv_conv_2 = round(inv_conv_raw, 2)
        entry_conv_2 = round(entry_conv_raw, 2)
        
        consumed_qty = c.consumed_qty or 0
        
        # Calculate surcharge & exchange gain with 2dp values
        s_fc = (inv_dr_2 - adjusted_2) * consumed_qty
        surcharge_inr = round(s_fc * inv_conv_2, 2)
        exchange_gain = round((inv_conv_2 - entry_conv_2) * consumed_qty * adjusted_2, 2)
        
        # Only show problematic rows (where surcharge or exchange gain is non-zero)
        if surcharge_inr != 0 or exchange_gain != 0:
            problem_count += 1
            print(f"{'='*80}")
            print(f"OUTGOING: {ent.retail_invoice_number} | Part: {ent.part_number} | Qty: {consumed_qty}")
            print(f"  CONSUMED FROM INCOMING: {inv.invoice_number} (ID: {inv.id})")
            print(f"")
            print(f"  --- RAW DB VALUES (full precision) ---")
            print(f"  Incoming dollar_rate:    {inv_dollar_rate_raw}")
            print(f"  Outgoing usd_rate:       {entry_usd_rate_raw}")
            print(f"  Outgoing plating:        {plating_raw}")
            print(f"  Incoming conversion_rate:{inv_conv_raw}")
            print(f"  Outgoing conversion_rate:{entry_conv_raw}")
            print(f"")
            print(f"  --- ROUNDED TO 2 DECIMALS ---")
            print(f"  Incoming dollar_rate:    {inv_dr_2}")
            print(f"  Outgoing adjusted_rate:  {adjusted_2}")
            print(f"  Incoming conv_rate:      {inv_conv_2}")
            print(f"  Outgoing conv_rate:      {entry_conv_2}")
            print(f"")
            print(f"  --- CALCULATED VALUES ---")
            print(f"  Rate diff (inv - adj):   {inv_dr_2 - adjusted_2}")
            print(f"  Conv diff (inv - entry): {inv_conv_2 - entry_conv_2}")
            print(f"  Surcharge INR:           {surcharge_inr}")
            print(f"  Exchange Gain:           {exchange_gain}")
            print()

if problem_count == 0:
    print("✅ No problematic rows found! All surcharge/exchange gain values will be 0 when rates match.")
else:
    print(f"\n⚠️  Found {problem_count} consumption records with non-zero surcharge/exchange gain.")
    print("The raw DB values above show the actual rate differences causing this.")
