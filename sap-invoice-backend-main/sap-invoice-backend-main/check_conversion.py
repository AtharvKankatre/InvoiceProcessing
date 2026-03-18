import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'InvoiceProcessing.settings')
django.setup()

from sales.services.transaction_merger import TransactionMerger
from sales.views import PartHistoryViewSet

merger = TransactionMerger()
outgoing = merger.get_outgoing_transactions(None, '2025-04-01', '2026-03-31')

if outgoing:
    txn = outgoing[0] # Just grab the first outgoing
    print("Found an Outgoing Txn:")
    print(f"  Invoice: {txn['invoice_number']}")
    print(f"  Customer: {txn['name']}")
    print(f"  Qty: {txn['qty']}")
    print(f"  FC Value: {txn['fc_value']}")
    print(f"  Rate FC: {txn['rate_fc']}")
    print(f"  INR Value: {txn['inr_value']}")
    print(f"  Exchange Rate (Retail): {txn['exchange_rate']}")
    
    # Let's manually run the surcharge block to see what it does
    from sales.models import InvoiceEntryConsumption
    
    cons_qs = InvoiceEntryConsumption.objects.filter(invoice_entry_id=txn['invoice_entry_id']).select_related('invoice', 'invoice_entry')
    for c in cons_qs:
        inv = c.invoice
        entry = c.invoice_entry
        print("\n  Related Incoming (Cooper) Invoice:")
        print(f"    Inv Qty: {inv.qty}, Dollar Rate: {inv.dollar_rate}, Conv Rate: {inv.conversion_rate}")
        print("  This Retail Entry:")
        print(f"    Consumed Qty: {c.consumed_qty}, USD Rate: {entry.usd_rate}, Conv Rate: {entry.conversion_rate}")
        
        inv_dollar_rate = inv.dollar_rate or 0
        entry_usd_rate = entry.usd_rate or 0
        s_fc = (inv_dollar_rate - entry_usd_rate) * c.consumed_qty
        
        surcharge_with_inv_er = s_fc * (inv.conversion_rate or 0)
        surcharge_with_entry_er = s_fc * (entry.conversion_rate or 0)
        
        print("\n  Surcharge Calculation:")
        print(f"    Current formula (using Cooper ER): {surcharge_with_inv_er}")
        print(f"    If using Retail ER: {surcharge_with_entry_er}")

