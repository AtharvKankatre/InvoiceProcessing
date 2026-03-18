import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'InvoiceProcessing.settings')
django.setup()

from sales.models import InvoiceEntryConsumption

# Let's find a consumption where the incoming conversion rate is different from the outgoing
qs = InvoiceEntryConsumption.objects.select_related('invoice', 'invoice_entry')

found = False
for c in qs:
    inv = c.invoice
    entry = c.invoice_entry
    
    if inv.conversion_rate != entry.conversion_rate:
        print(f"Found difference!")
        print(f"  Incoming (Cooper) Invoice: {inv.invoice_number}")
        print(f"    Inv Qty: {inv.qty}, Dollar Rate: {inv.dollar_rate}, Conv Rate: {inv.conversion_rate}")
        print(f"  Outgoing (Retail) Entry: {entry.retail_invoice_number}")
        print(f"    Consumed Qty: {c.consumed_qty}, USD Rate: {entry.usd_rate}, Conv Rate: {entry.conversion_rate}")
        
        c_qty = c.consumed_qty or 0
        inv_dollar_rate = inv.dollar_rate or 0
        entry_usd_rate = entry.usd_rate or 0
        s_fc = (inv_dollar_rate - entry_usd_rate) * c_qty
        
        surcharge_with_inv_er = s_fc * (inv.conversion_rate or 0)
        surcharge_with_entry_er = s_fc * (entry.conversion_rate or 0)
        
        exchange_gain = (inv.conversion_rate - entry.conversion_rate) * c_qty * entry_usd_rate
        
        calculation_formula = (-1 * entry.inr_total) - float(surcharge_with_inv_er) - float(exchange_gain)
        
        print("\n  Surcharge Calculation:")
        print(f"    Current formula (using Cooper ER): {surcharge_with_inv_er}")
        print(f"    If using Retail ER: {surcharge_with_entry_er}")
        print(f"  Exchange Gain:")
        print(f"    Current Formula: {exchange_gain}")
        
        found = True
        break

if not found:
    print("Could not find any transaction with different conversion rates!")
