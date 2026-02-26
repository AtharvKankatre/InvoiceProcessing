import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sap_invoice.settings')
django.setup()

from sales.models import Invoice, InvoiceRetailPartMap

def search_inpinite():
    print("--- Searching Invoices ---")
    inv_matches = Invoice.objects.filter(customer_name__icontains="Inpinite")
    print(f"Found {inv_matches.count()} Invoices with 'Inpinite' in name.")
    for inv in inv_matches:
        print(f"ID: {inv.id}, Name: '{inv.customer_name}'")

    print("\n--- Searching Retail Part Maps ---")
    map_matches = InvoiceRetailPartMap.objects.filter(company_name__icontains="Inpinite")
    print(f"Found {map_matches.count()} Maps with 'Inpinite' in company_name.")
    for m in map_matches:
        print(f"ID: {m.id}, Company: '{m.company_name}'")

if __name__ == "__main__":
    search_inpinite()
