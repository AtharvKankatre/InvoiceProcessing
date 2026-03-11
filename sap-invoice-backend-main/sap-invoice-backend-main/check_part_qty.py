"""
Django shell script to investigate WH to Customer Qty for part CKJMCFG0070030A.
Run with: python manage.py shell -c "exec(open('check_part_qty.py').read())"
"""
from sales.models import InvoiceRetailPartMap, InvoiceEntryConsumption
from retail.models import InvoiceEntry
from decimal import Decimal

TARGET_PART = 'CKJMCFG0070030A'

# 1. Find all retail part numbers mapped to this sale part
maps = InvoiceRetailPartMap.objects.filter(sale_part_number=TARGET_PART)
print(f"\n=== Retail Part Mappings for {TARGET_PART} ===")
retail_parts = []
for m in maps:
    print(f"  Retail: {m.retail_part_number} | Company: {m.company_name}")
    retail_parts.append(m.retail_part_number)

# 2. Get all InvoiceEntry records with these retail parts
entries = InvoiceEntry.objects.filter(part_number__in=retail_parts).prefetch_related('consumptions')

print(f"\n=== Total InvoiceEntry records found: {entries.count()} ===")

# 3. Calculate totals both ways
raw_qty_total = 0       # Sum of entry.qty  (what client might be using)
hybrid_qty_total = 0    # What our system calculates (consumption-based)

entries_with_consumption = 0
entries_without_consumption = 0

for entry in entries:
    raw_qty = entry.qty or 0
    raw_qty_total += raw_qty
    
    cons = entry.consumptions.all()
    if cons.exists():
        entries_with_consumption += 1
        for c in cons:
            hybrid_qty_total += c.consumed_qty or 0
    else:
        entries_without_consumption += 1
        hybrid_qty_total += raw_qty

print(f"\n=== QUANTITY COMPARISON ===")
print(f"  Raw entry.qty total:              {raw_qty_total}")
print(f"  Hybrid qty (consumption-based):   {hybrid_qty_total}")
print(f"  Difference:                       {raw_qty_total - hybrid_qty_total}")
print(f"\n  Entries WITH consumption records: {entries_with_consumption}")
print(f"  Entries WITHOUT consumption:      {entries_without_consumption}")

# 4. Detailed breakdown
print(f"\n=== DETAILED ENTRY BREAKDOWN ===")
for entry in entries.order_by('date'):
    cons = entry.consumptions.all()
    cons_qty = sum(c.consumed_qty or 0 for c in cons) if cons.exists() else None
    print(f"  Date: {entry.date} | Part: {entry.part_number} | entry.qty: {entry.qty} | consumed_qty: {cons_qty} | id: {entry.id}")

# 5. Check direct entries
direct_entries = InvoiceEntry.objects.filter(part_number=TARGET_PART)
print(f"\n=== Direct InvoiceEntry with part_number={TARGET_PART}: {direct_entries.count()} ===")
for e in direct_entries:
    print(f"  Date: {e.date} | qty: {e.qty}")
