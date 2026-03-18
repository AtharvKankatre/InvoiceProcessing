import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sap_invoice.settings')
django.setup()

from retail.models import InvoiceEntry
from sales.models import InvoiceRetailPartMap

def check_company_retail_entries(company_name_keyword):
    print(f"--- Checking Retail Entries for: '{company_name_keyword}' ---")
    
    # 1. Find all parts mapped to this company
    part_maps = InvoiceRetailPartMap.objects.filter(company_name__icontains=company_name_keyword)
    retail_part_numbers = list(part_maps.values_list('retail_part_number', flat=True))
    
    if not retail_part_numbers:
        print(f"  [INFO] No Part Maps found matching '{company_name_keyword}'.")
        print(f"  [STATUS] Deletion confirmed. No parts mapped for this company.")
        return
        
    print(f"  [INFO] Found {len(retail_part_numbers)} part numbers formally mapped to this company: {retail_part_numbers}")
    
    # 2. Check if any InvoiceEntry records still exist for these parts
    remaining_entries = InvoiceEntry.objects.filter(part_number__in=retail_part_numbers)
    entry_count = remaining_entries.count()
    
    if entry_count == 0:
        print(f"\n  ✅ [SUCCESS] DELETION CONFIRMED!")
        print(f"     There are 0 retail entries left for any parts related to '{company_name_keyword}'.")
    else:
        print(f"\n  ❌ [WARNING] DELETION INCOMPLETE!")
        print(f"     There are still {entry_count} retail entries remaining in the database for '{company_name_keyword}' parts.")

if __name__ == '__main__':
    # Target Mercury Marine Plant 10
    check_company_retail_entries('Mercury Marine Plant 10')
