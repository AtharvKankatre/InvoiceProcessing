import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sap_invoice.settings')
django.setup()

from django.db import transaction
from retail.models import InvoiceEntry
from sales.models import InvoiceRetailPartMap, InvoiceEntryConsumption

def force_delete_mercury():
    print("--- 🚀 STARTING MERCURY MARINE FORCE DELETION ---")
    company_name_keyword = "Mercury Marine Plant 10"
    
    try:
        with transaction.atomic():
            part_maps = InvoiceRetailPartMap.objects.filter(company_name__icontains=company_name_keyword)
            retail_part_numbers = list(part_maps.values_list('retail_part_number', flat=True))
            
            if not retail_part_numbers:
                print("No parts mapped to Mercury Marine Plant 10.")
                return
                
            print(f"Targeting parts: {retail_part_numbers}")
            
            entries_to_delete = InvoiceEntry.objects.filter(part_number__in=retail_part_numbers)
            entry_count = entries_to_delete.count()
            
            if entry_count == 0:
                print("Already empty. Nothing to delete.")
                return
                
            print(f"Found {entry_count} retail entries to delete.")
            deleted_count = 0
            
            for entry in entries_to_delete:
                consumptions = InvoiceEntryConsumption.objects.filter(invoice_entry=entry)
                for consumption in consumptions:
                    source_invoice = consumption.invoice
                    consumed_qty = consumption.consumed_qty
                    
                    # Log the restoration
                    print(f"  -> Restoring {consumed_qty} stock to Cooper Invoice #{source_invoice.invoice_number}")
                    source_invoice.qty += int(consumed_qty)
                    source_invoice.save()
                    
                entry.delete()
                deleted_count += 1
                
            print(f"\n✅ SUCCESS: Safely deleted {deleted_count} InvoiceEntry records.")
            print("The consumed stock has been completely restored to the parent Cooper invoices.")
            
    except Exception as e:
        print(f"\n❌ [ERROR] An error occurred: {e}")

if __name__ == '__main__':
    force_delete_mercury()
