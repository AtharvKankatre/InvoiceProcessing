import sys
import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'InvoiceProcessing.settings')
django.setup()

from retail.models import InvoiceEntry
from sales.models import Invoice, InvoiceRetailPartMap

def delete_company_data():
    target_company = "Nemak Dillingen Casting GmbH & Co."
    print(f"================================================================================")
    print(f"  DELETING DATA FOR: {target_company}")
    print(f"================================================================================")
    
    # 1. Find all parts mapped to this company
    mapped_parts = InvoiceRetailPartMap.objects.filter(company_name__icontains="Nemak Dillingen").values_list('retail_part_number', flat=True)
    sales_parts = InvoiceRetailPartMap.objects.filter(company_name__icontains="Nemak Dillingen").values_list('sale_part_number', flat=True)
    
    parts_to_delete_retail = list(mapped_parts)
    parts_to_delete_sales = list(sales_parts)
    
    print(f"Found {len(parts_to_delete_retail)} retail parts and {len(parts_to_delete_sales)} sales parts mapped to this company.")
    
    # 2. Delete Outgoing (InvoiceEntry)
    if parts_to_delete_retail:
        outgoing = InvoiceEntry.objects.filter(part_number__in=parts_to_delete_retail)
        outgoing_count = outgoing.count()
        outgoing.delete()
        print(f"✅ Deleted {outgoing_count} Outgoing (Retail) Invoice Entries.")
    else:
        print("✅ No Outgoing entries found to delete.")
        
    # 3. Delete Incoming (Invoice)
    # Incoming invoices can be found either by customer_name directly OR by the sales part numbers
    incoming = Invoice.objects.filter(customer_name__icontains="Nemak Dillingen")
    if not incoming.exists() and parts_to_delete_sales:
        incoming = Invoice.objects.filter(part_number__in=parts_to_delete_sales)
        
    incoming_count = incoming.count()
    if incoming_count > 0:
        incoming.delete()
        print(f"✅ Deleted {incoming_count} Incoming (Warehouse) Invoices.")
    else:
        print("✅ No Incoming invoices found to delete.")
        
    print(f"================================================================================")
    print(f"  DELETION COMPLETE")
    print(f"================================================================================")

if __name__ == "__main__":
    delete_company_data()
