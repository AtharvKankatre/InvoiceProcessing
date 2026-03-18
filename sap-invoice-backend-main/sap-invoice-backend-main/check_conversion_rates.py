"""
Diagnostic script to check if Cooper and Retail conversion rates differ.
Run on the server: python manage.py shell < check_conversion_rates.py
"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'InvoiceProcessing.settings')
django.setup()

from sales.models import InvoiceEntryConsumption

print("=" * 80)
print("CONVERSION RATE COMPARISON: Cooper (Incoming) vs Retail (Outgoing)")
print("=" * 80)

qs = InvoiceEntryConsumption.objects.select_related('invoice', 'invoice_entry').all()

same_count = 0
diff_count = 0
diff_examples = []

for c in qs:
    inv = c.invoice
    entry = c.invoice_entry
    inv_er = float(inv.conversion_rate or 0)
    entry_er = float(entry.conversion_rate or 0)
    
    if inv_er == entry_er:
        same_count += 1
    else:
        diff_count += 1
        if len(diff_examples) < 10:  # Show first 10 examples
            diff_examples.append({
                'cooper_invoice': inv.invoice_number,
                'cooper_er': inv_er,
                'retail_invoice': entry.retail_invoice_number,
                'retail_er': entry_er,
                'part': entry.part_number,
                'consumed_qty': c.consumed_qty,
            })

print(f"\nTotal consumption records: {same_count + diff_count}")
print(f"  Same conversion rate:      {same_count}")
print(f"  Different conversion rate:  {diff_count}")

if diff_examples:
    print(f"\nFirst {len(diff_examples)} examples of DIFFERENT rates:")
    for ex in diff_examples:
        print(f"  Cooper Invoice: {ex['cooper_invoice']} (ER={ex['cooper_er']})")
        print(f"  Retail Invoice: {ex['retail_invoice']} (ER={ex['retail_er']})")
        print(f"  Part: {ex['part']}, Consumed Qty: {ex['consumed_qty']}")
        print(f"  ---")
else:
    print("\nNO differences found — all Cooper and Retail conversion rates are identical.")
    print("This means the formula change (inv_er -> entry_er) won't produce visible differences here.")
    print("The client's production database likely HAS different rates.")
