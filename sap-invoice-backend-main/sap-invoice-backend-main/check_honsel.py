import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'InvoiceProcessing.settings')
django.setup()

from sales.models import InvoiceRetailPartMap
from retail.models import InvoiceEntry

honsel = 'Martinrea Honsel Maxico S.A. de C.V'
maps = InvoiceRetailPartMap.objects.filter(company_name=honsel)

print('--- HONSEL MEXICO MAPPINGS ---')
mapped_parts = []
sale_parts = []
for m in maps:
    mapped_parts.append(m.retail_part_number)
    sale_parts.append(m.sale_part_number)
    print(f'  Retail: "{m.retail_part_number}" -> Sale: "{m.sale_part_number}"')

retail_count = InvoiceEntry.objects.filter(part_number__in=mapped_parts).count()
sale_count = InvoiceEntry.objects.filter(part_number__in=sale_parts).count()
print(f'\nDispatch entries with RETAIL parts: {retail_count}')
print(f'Dispatch entries with SALE parts: {sale_count}')

print('\nBreakdown by retail part:')
for p in mapped_parts:
    entries = InvoiceEntry.objects.filter(part_number=p)
    print(f'  "{p}": {entries.count()} entries, qty={sum(e.qty for e in entries)}')

print('\nBreakdown by sale part:')
for s in sale_parts:
    entries = InvoiceEntry.objects.filter(part_number=s)
    print(f'  "{s}": {entries.count()} entries, qty={sum(e.qty for e in entries)}')

# Check for duplicates
print('\nChecking for duplicate invoice numbers...')
from django.db.models import Count
all_parts = mapped_parts + sale_parts
dupes = InvoiceEntry.objects.filter(part_number__in=all_parts).values('retail_invoice_number', 'part_number').annotate(cnt=Count('id')).filter(cnt__gt=1)
for d in dupes:
    print(f'  DUPLICATE: invoice="{d["retail_invoice_number"]}" part="{d["part_number"]}" count={d["cnt"]}')
if not dupes:
    print('  No duplicates found.')
