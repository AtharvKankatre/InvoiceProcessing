import os, sys, django
from decimal import Decimal

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'InvoiceProcessing.settings')
django.setup()

from retail.models import InvoiceEntry
from sales.models import InvoiceRetailPartMap, InvoiceEntryConsumption

def fix_wabtec_data():
    # 1. Get all Wabtec parts
    wabtec_parts = list(InvoiceRetailPartMap.objects.filter(company_name__icontains='Wabtec').values_list('retail_part_number', flat=True))
    
    if not wabtec_parts:
        print("No Wabtec parts found!")
        return

    # 2. Get all InvoiceEntry records for these parts
    entries = InvoiceEntry.objects.filter(part_number__in=wabtec_parts)
    count = entries.count()
    print(f"Found {count} Wabtec InvoiceEntry records to update.")
    
    # 3. Target Retail Conversion Rate
    # The client screenshot showed they expect 84.90 for retail conversion rate for Wabtec
    target_er = Decimal('84.90')
    
    updated_count = 0
    
    for entry in entries:
        old_er = entry.conversion_rate
        old_usd_total = entry.usd_total
        old_inr_total = entry.inr_total
        old_inr_rate = entry.inr_rate
        
        # Calculate new values based on the new conversion rate
        new_inr_rate = entry.usd_rate * target_er
        new_inr_total = new_inr_rate * abs(entry.qty) # qty can be negative for returns

        # Update the entry
        entry.conversion_rate = target_er
        # If inr_rate and inr_total were calculated using the old ER, update them too.
        # It's safer to update them to prevent inconsistencies in the database.
        entry.inr_rate = new_inr_rate
        entry.inr_total = new_inr_total
        
        entry.save()
        updated_count += 1
        
        if updated_count <= 5:
            print(f"Updated {entry.retail_invoice_number}: ER {old_er} -> {target_er}")

    print(f"\nSuccessfully updated {updated_count} record(s).")

if __name__ == '__main__':
    fix_wabtec_data()
