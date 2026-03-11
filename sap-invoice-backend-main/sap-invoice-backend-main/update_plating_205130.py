"""
Script to backfill plating_charges and plating_conversion_rate for part 205130R and 205130S.
Run on server: python manage.py shell -c "exec(open('update_plating_205130.py').read())"
"""
from retail.models import InvoiceEntry
from decimal import Decimal

# Data from client's Excel (screenshot)
# Format: (retail_invoice_number, plating_charges, plating_conversion_rate)
PLATING_DATA = {
    '5891': ('66.8600', '87.30'),
    '5901': ('66.8600', '87.30'),
    '5902': ('66.8600', '87.30'),
    '5907': ('66.8600', '87.30'),
    '5908': ('66.8600', '87.30'),
    '5909': ('66.8600', '87.30'),
    '5915': ('66.8600', '87.30'),
    '5924': ('66.8600', '87.30'),
    '5929': ('66.8600', '86.40'),
    '5932': ('66.8600', '86.40'),
    '5936': ('66.8600', '86.40'),
    '5938': ('66.8600', '86.40'),
    '5947': ('66.8600', '86.75'),
    '5949': ('66.8600', '86.75'),
    '5954': ('66.8600', '86.40'),
    '5955': ('66.8600', '86.40'),
    '5961': ('66.8600', '86.40'),
    '5963': ('66.8600', '86.20'),
    '5970': ('66.8600', '86.80'),
    '5977': ('66.8600', '86.80'),
    '5991': ('66.8600', '86.40'),
    '5992': ('66.8600', '86.40'),
    '5998': ('66.8600', '88.60'),
    '6001': ('66.8600', '87.90'),
    '6007': ('66.8600', '89.00'),
    '6008': ('66.8600', '88.60'),
    '6010': ('66.8600', '89.00'),
    '6017': ('66.8600', '89.00'),
    '6019': ('66.8600', '89.00'),
}

PARTS = ['205130R', '205130S']

updated = 0
not_found = 0

for inv_num, (plating, plating_conv) in PLATING_DATA.items():
    entries = InvoiceEntry.objects.filter(
        retail_invoice_number=inv_num,
        part_number__in=PARTS
    )
    if entries.exists():
        count = entries.update(
            plating_charges=Decimal(plating),
            plating_conversion_rate=Decimal(plating_conv)
        )
        updated += count
        print(f"  ✓ Invoice {inv_num}: Updated {count} entry(ies)")
    else:
        not_found += 1
        print(f"  ✗ Invoice {inv_num}: NOT FOUND")

print(f"\n=== SUMMARY ===")
print(f"  Updated: {updated} entries")
print(f"  Not found: {not_found} invoices")
print(f"\nNext: Re-export Stock Ledger from frontend to see the impact!")
