"""
Find date ranges and part details for customers with missing wholesale invoices.
"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sap_invoice.settings')
django.setup()

from sales.models import InvoiceRetailPartMap
from retail.models import InvoiceEntry
from django.db.models import Min, Max, Sum

orphan_companies = [
    'Kawasaki  Motors Manufacturing',
    'Wabtec Transportation Systems,LLC',
    'Jaguar Land Rover Limited',
]

for company in orphan_companies:
    print(f"\n{'='*60}")
    print(f"Company: {company}")
    print(f"{'='*60}")
    
    # Get retail parts for this company
    maps = InvoiceRetailPartMap.objects.filter(company_name=company)
    retail_parts = [m.retail_part_number for m in maps]
    sale_parts = [m.sale_part_number for m in maps if m.sale_part_number]
    
    print(f"\nPart mappings:")
    for m in maps:
        print(f"  Retail: {m.retail_part_number}  ->  Sale/Wholesale: {m.sale_part_number}")
    
    # Find dispatch entries for these retail parts
    dispatches = InvoiceEntry.objects.filter(part_number__in=retail_parts)
    
    if dispatches.exists():
        stats = dispatches.aggregate(
            earliest=Min('date'),
            latest=Max('date'),
            total_qty=Sum('qty'),
            count=Sum('qty')  # just to count
        )
        print(f"\nDispatch records found: {dispatches.count()}")
        print(f"Date range: {stats['earliest']} to {stats['latest']}")
        print(f"Total qty dispatched: {stats['total_qty']}")
        
        print(f"\nDispatch details:")
        for d in dispatches.order_by('date'):
            print(f"  Date: {d.date}, Part: {d.part_number}, Qty: {d.qty}")
    else:
        print(f"\nNo dispatch records found for these parts")
