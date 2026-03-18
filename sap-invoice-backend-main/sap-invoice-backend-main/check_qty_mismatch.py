"""
Detailed inventory check for the problematic invoices.
"""
import os, sys, django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sap_invoice.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from sales.models import Invoice, InvoiceEntryConsumption
from retail.models import InvoiceEntry

problem_invoices = ['2252600087', '2252600088', '2252600134', '2252600140']

print("--- DETAILED RECONCILIATION CHECK ---")

for base_num in problem_invoices:
    print(f"\n{'='*60}")
    print(f"ANALYZING INVOICE BASE: {base_num}")
    
    # 1. Look at the Incoming Invoice
    incoming = Invoice.objects.filter(invoice_number__iregex=fr"^{base_num}").first()
    if not incoming:
        print(f"  [ERROR] No incoming invoice found for {base_num}!")
        continue
        
    print(f"  INCOMING: {incoming.invoice_number}")
    print(f"    Original Qty Uploaded:  {incoming.original_qty if hasattr(incoming, 'original_qty') else '(check your DB/Excel)'}")
    print(f"    Current Remaining Qty:  {incoming.qty}")
    
    # Calculate how much was consumed from this incoming invoice
    consumptions_from_this = InvoiceEntryConsumption.objects.filter(invoice=incoming)
    total_consumed = sum(c.consumed_qty for c in consumptions_from_this)
    print(f"    Total Consumed By Others: {total_consumed}")
    
    for c in consumptions_from_this:
        print(f"      -> {c.consumed_qty} qty went to Outgoing '{c.invoice_entry.retail_invoice_number}'")
        
    # 2. Look at the Outgoing Invoices that TRIED to map to this
    outgoing = InvoiceEntry.objects.filter(retail_invoice_number__iregex=fr"^{base_num}")
    print(f"\n  OUTGOING ENTRIES trying to use {base_num}:")
    total_requested = sum(out.qty for out in outgoing)
    print(f"  Total Requested by these Outgoing rows: {total_requested}")
    for out in outgoing:
        print(f"    OUTGOING: {out.retail_invoice_number} | Requested Qty: {out.qty}")
        
        # Where did this outgoing *actually* get its stock from?
        its_consumptions = InvoiceEntryConsumption.objects.filter(invoice_entry=out)
        for c in its_consumptions:
            print(f"      <- Got {c.consumed_qty} qty from Incoming '{c.invoice.invoice_number}'")
            
    print(f"{'='*60}\n")
