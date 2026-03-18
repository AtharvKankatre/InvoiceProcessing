import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sap_invoice.settings')
django.setup()

from retail.models import InvoiceEntry
from sales.models import InvoiceRetailPartMap, Invoice

def find_nemak_names():
    print("\n--- Searching for 'Nemak' in the database ---")
    
    # 1. Check Part Maps
    maps = InvoiceRetailPartMap.objects.filter(company_name__icontains='nemak').values_list('company_name', flat=True).distinct()
    print(f"\n1. Names in InvoiceRetailPartMap:")
    for m in maps:
        print(f"   - '{m}'")
    if not maps:
        print("   (No results found)")

    # 2. Check Cooper Invoices
    invoices = Invoice.objects.filter(customer_name__icontains='nemak').values_list('customer_name', flat=True).distinct()
    print(f"\n2. Names in Invoice (Cooper Invoices):")
    for i in invoices:
        print(f"   - '{i}'")
    if not invoices:
        print("   (No results found)")
        
    # 3. Check Retail Entries (ASN)
    entries = InvoiceEntry.objects.filter(customer_name__icontains='nemak').values_list('customer_name', flat=True).distinct()
    print(f"\n3. Names in InvoiceEntry (Retail/ASN Invoices):")
    for e in entries:
        print(f"   - '{e}'")
    if not entries:
        print("   (No results found)")

if __name__ == '__main__':
    find_nemak_names()
