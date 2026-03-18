import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sap_invoice.settings')
django.setup()

from sales.models import InvoiceRetailPartMap

print("=== MAPPINGS FOR NEMAK DILLINGEN ===")
mappings = InvoiceRetailPartMap.objects.filter(company_name__icontains="Nemak Dillingen")
for m in mappings:
    print(f"ID={m.id} | SalePart={m.sale_part_number} | RetailPart={m.retail_part_number} | Company={m.company_name}")
    
print("\n=== MAPPINGS WHERE RETAIL PART INCLUDES NEMAK OR SIMILAR ===")
# Just in case the sale part is the one that says Nemak
mappings_sale = InvoiceRetailPartMap.objects.filter(sale_part_number__icontains="Nemak")
for m in mappings_sale:
    print(f"ID={m.id} | SalePart={m.sale_part_number} | RetailPart={m.retail_part_number} | Company={m.company_name}")
