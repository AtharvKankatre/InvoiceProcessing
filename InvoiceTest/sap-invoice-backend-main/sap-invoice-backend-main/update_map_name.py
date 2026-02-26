import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sap_invoice.settings')
django.setup()

from sales.models import InvoiceRetailPartMap

def update_map():
    # Update "Inpinite Test" -> "Global Electronics" (using same name as before for consistency)
    count = InvoiceRetailPartMap.objects.filter(company_name="Inpinite Test").update(company_name="Global Electronics")
    print(f"Updated {count} Retail Part Maps from 'Inpinite Test' to 'Global Electronics'")

if __name__ == "__main__":
    update_map()
