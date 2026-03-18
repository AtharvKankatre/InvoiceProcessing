import sys
import os
import django
from datetime import datetime
from decimal import Decimal

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sap_invoice.settings')
django.setup()

from sales.models import Invoice, InvoiceRetailPartMap
from retail.models import InvoiceEntry
from sales.services.transaction_merger import TransactionMerger

def debug_honsel_mexico_opening():
    target_company = "Martinrea Honsel Mexico S.A. de C.V"
    search_term = "MEXICO"
    
    print(f"================================================================================")
    print(f"  DEBUGGING OPENING BALANCE FOR {target_company}")
    print(f"================================================================================")
    
    # 1. We assume the part in question is the one we saw: 'CFORDFG009E5EAA'
    # But let's check all parts for this company
    incoming_parts = set(Invoice.objects.filter(customer_name__icontains=search_term).values_list('part_number', flat=True))
    
    if not incoming_parts:
        print("No incoming invoices found for Honsel Mexico.")
        return
        
    merger = TransactionMerger()
    
    for part in incoming_parts:
        print(f"\nAnalyzing Part: {part}")
        
        # Get all incoming for this part and customer
        incoming_qs = Invoice.objects.filter(
            customer_name__icontains=search_term,
            part_number=part
        ).order_by('date')
        
        # Determine the earliest date in this set
        first_invoice = incoming_qs.first()
        if not first_invoice:
            continue
            
        start_date = first_invoice.date
        
        # Let's say we want the opening balance AS OF start_date (which will just be what happened PREVIOUS to start_date, or what if start_date is later?)
        # Let's check opening balance exactly as the application does.
        # Normally, the application expects an explicitly provided `start_date` and `end_date`. Let's assume start_date is the earliest date we have.
        print(f"  -> Earliest incoming invoice date: {start_date}")
        
        # Calculate it from the ground up for this specific customer
        # 1. incoming qty before start_date
        incoming_before = Invoice.objects.filter(
            customer_name__icontains=search_term,
            part_number=part,
            date__lt=start_date
        )
        total_in_before = sum((inv.invoice_qty if inv.invoice_qty is not None else (inv.qty or 0)) for inv in incoming_before)
        
        # 2. outgoing qty before start_date
        mapped_retail_parts = InvoiceRetailPartMap.objects.filter(
            company_name__icontains=search_term,
            sale_part_number=part
        ).values_list('retail_part_number', flat=True)
        
        outgoing_before = InvoiceEntry.objects.filter(
            part_number__in=mapped_retail_parts,
            date__lt=start_date
        )
        total_out_before = sum((entry.qty or 0) for entry in outgoing_before)
        
        opening_balance = total_in_before - total_out_before
        
        print(f"  -> Explicit calculation before {start_date}:")
        print(f"       Total Incoming (Before): {total_in_before}")
        print(f"       Total Outgoing (Before): {total_out_before}")
        print(f"       Calculated Opening Bal : {opening_balance}")
        
        # Now let's just trace ALL incoming vs outgoing up to TODAY, chronologically
        total_in = 0
        total_out = 0
        incoming_all = list(incoming_qs)
        outgoing_all = list(InvoiceEntry.objects.filter(part_number__in=mapped_retail_parts).order_by('date'))
        
        print(f"\n  -> Full Chronological Event Trace for {part}:")
        all_events = []
        for inv in incoming_all:
            q = inv.invoice_qty if inv.invoice_qty is not None else (inv.qty or 0)
            all_events.append({'date': inv.date, 'type': 'IN', 'qty': q, 'id': inv.invoice_number})
        for out in outgoing_all:
            all_events.append({'date': out.date, 'type': 'OUT', 'qty': out.qty, 'id': out.retail_invoice_number})
            
        all_events.sort(key=lambda x: x['date'])
        
        running = 0
        for ev in all_events:
            sgn = 1 if ev['type'] == 'IN' else -1
            running += (ev['qty'] * sgn)
            print(f"     {ev['date'].strftime('%Y-%m-%d')} | {ev['type']:<3} | QTY: {(ev['qty'] * sgn):<10} | RUNNING: {running:<10} | REF: {ev['id']}")
            

if __name__ == "__main__":
    debug_honsel_mexico_opening()
