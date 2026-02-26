# coding: utf-8
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sap_invoice.settings')
django.setup()

from sales.models import Invoice, InvoiceRetailPartMap
from retail.models import InvoiceEntry
from django.db.models import Sum

print("=== Retail Part Mappings ===")
for p in InvoiceRetailPartMap.objects.all()[:10]:
    print(f"  {p.retail_part_number} -> {p.sale_part_number}")

print("\n=== Stock by retail part ===")
for p in InvoiceRetailPartMap.objects.all()[:10]:
    inv_qs = Invoice.objects.filter(part_number=p.sale_part_number, qty__gt=0)
    total = inv_qs.aggregate(s=Sum('qty'))['s'] or 0
    cnt = inv_qs.count()
    print(f"  {p.retail_part_number} ({p.sale_part_number}): {total} qty across {cnt} invoices")

print("\n=== Sample existing retail invoice numbers ===")
for e in InvoiceEntry.objects.all()[:5]:
    print(f"  {e.retail_invoice_number} ({e.part_number})")
