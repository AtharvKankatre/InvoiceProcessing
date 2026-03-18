import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sap_invoice.settings')
django.setup()

from decimal import Decimal
from sales.models import Invoice, InvoiceRetailPartMap, InvoiceEntryConsumption
from retail.models import InvoiceEntry

PART = 'CFORDFG009E5EAA'
COMPANY = 'NEMAK MEXICO SA'

def debug_part():
    print(f"\n{'='*80}")
    print(f"  DEBUG: Part {PART} — {COMPANY}")
    print(f"{'='*80}")
    
    # 1. Check Part Mapping
    print(f"\n--- 1. Part Mapping ---")
    mappings = InvoiceRetailPartMap.objects.filter(sale_part_number=PART)
    if mappings.exists():
        for m in mappings:
            print(f"  sale_part: {m.sale_part_number} → retail_part: {m.retail_part_number} | company: {m.company_name}")
    else:
        print(f"  No mappings found for sale_part_number={PART}")
    
    mappings2 = InvoiceRetailPartMap.objects.filter(retail_part_number=PART)
    if mappings2.exists():
        for m in mappings2:
            print(f"  retail_part: {m.retail_part_number} → sale_part: {m.sale_part_number} | company: {m.company_name}")
    
    # Collect all relevant part numbers
    all_retail_parts = set()
    all_retail_parts.add(PART)
    for m in mappings:
        all_retail_parts.add(m.retail_part_number)
    for m in mappings2:
        all_retail_parts.add(m.sale_part_number)
    print(f"  All related parts: {all_retail_parts}")
    
    # 2. Incoming Cooper Invoices
    print(f"\n--- 2. Incoming Cooper Invoices (part_number={PART}) ---")
    incoming = Invoice.objects.filter(part_number=PART).order_by('date')
    total_inc_qty = 0
    total_inc_fc = Decimal(0)
    total_inc_inr = Decimal(0)
    
    for inv in incoming:
        inv_qty = inv.invoice_qty if inv.invoice_qty is not None else (inv.qty or 0)
        total_inc_qty += inv_qty
        total_inc_fc += inv.dollar_total or Decimal(0)
        total_inc_inr += inv.inr_total or Decimal(0)
        print(f"  [{inv.date}] #{inv.invoice_number} | qty={inv_qty} | dollar_rate={inv.dollar_rate} | conv_rate={inv.conversion_rate} | FC={inv.dollar_total} | INR={inv.inr_total}")
    
    print(f"  TOTAL INCOMING: qty={total_inc_qty}, FC={total_inc_fc}, INR={total_inc_inr}")
    
    # 3. Outgoing Retail Entries
    print(f"\n--- 3. Outgoing Retail Entries ---")
    entries = InvoiceEntry.objects.filter(part_number__in=all_retail_parts).order_by('date')
    total_out_qty = 0
    total_out_fc = Decimal(0)
    total_out_inr = Decimal(0)
    
    entry_ids = []
    for entry in entries:
        entry_ids.append(entry.id)
        plating = entry.plating_charges or Decimal(0)
        entry_conv = entry.conversion_rate or Decimal(0)
        qty = entry.qty or 0
        total_out_qty += qty
        
        # Check consumption
        cons = InvoiceEntryConsumption.objects.filter(invoice_entry=entry)
        if cons.exists():
            cons_qty = sum(c.consumed_qty or 0 for c in cons)
            cons_fc = sum(c.fc_value or Decimal(0) for c in cons)
            fc_val = cons_fc
            inr_val = entry.inr_total or Decimal(0)
        else:
            fc_val = entry.usd_total or Decimal(0)
            inr_val = entry.inr_total or Decimal(0)
        
        # Adjust for plating
        if plating:
            fc_val -= plating * qty
            inr_val -= plating * entry_conv * qty
        
        total_out_fc += fc_val
        total_out_inr += inr_val
        
        print(f"  [{entry.date}] #{entry.retail_invoice_number} | part={entry.part_number} | qty={qty} | usd_rate={entry.usd_rate} | conv_rate={entry.conversion_rate} | plating={plating} | FC={fc_val} | INR={inr_val}")
    
    print(f"  TOTAL OUTGOING: qty={total_out_qty}, FC={total_out_fc}, INR={total_out_inr}")
    
    # 4. Consumption Records (Surcharge & Exchange Gain)
    print(f"\n--- 4. Consumption Records & Surcharge Calculation ---")
    consumptions = InvoiceEntryConsumption.objects.filter(
        invoice_entry_id__in=entry_ids
    ).select_related('invoice', 'invoice_entry').order_by('invoice_entry__date')
    
    total_surcharge_fc = Decimal(0)
    total_surcharge_inr = Decimal(0)
    total_exchange_gain = Decimal(0)
    
    for c in consumptions:
        inv = c.invoice
        entry = c.invoice_entry
        consumed_qty = c.consumed_qty or 0
        
        inv_dollar_rate = inv.dollar_rate or Decimal(0)
        entry_usd_rate = entry.usd_rate or Decimal(0)
        plating = entry.plating_charges or Decimal(0)
        adjusted_rate = entry_usd_rate - plating
        inv_er = inv.conversion_rate or Decimal(0)
        entry_er = entry.conversion_rate or Decimal(0)
        
        s_fc = (inv_dollar_rate - adjusted_rate) * consumed_qty
        s_inr = s_fc * inv_er
        ex_gain = (inv_er - entry_er) * consumed_qty * adjusted_rate
        
        total_surcharge_fc += s_fc
        total_surcharge_inr += s_inr
        total_exchange_gain += ex_gain
        
        print(f"  Consumption: entry #{entry.retail_invoice_number} ← invoice #{inv.invoice_number}")
        print(f"    consumed_qty={consumed_qty}")
        print(f"    inv_dollar_rate={inv_dollar_rate}, entry_usd_rate={entry_usd_rate}, plating={plating}, adjusted_rate={adjusted_rate}")
        print(f"    inv_conv_rate={inv_er}, entry_conv_rate={entry_er}")
        print(f"    surcharge_fc={round(s_fc, 4)}, surcharge_inr={round(s_inr, 2)}")
        print(f"    exchange_gain_inr={round(ex_gain, 2)}")
        print()
    
    print(f"  TOTAL SURCHARGE FC:  {round(total_surcharge_fc, 2)}")
    print(f"  TOTAL SURCHARGE INR: {round(total_surcharge_inr, 2)}")
    print(f"  TOTAL EXCHANGE GAIN: {round(total_exchange_gain, 2)}")
    
    # 5. Summary
    print(f"\n--- 5. SUMMARY ---")
    print(f"  Incoming Qty:  {total_inc_qty}")
    print(f"  Outgoing Qty:  {total_out_qty}")
    print(f"  Balance Qty:   {total_inc_qty - total_out_qty}")
    print(f"")
    print(f"  Incoming FC:   {total_inc_fc}")
    print(f"  Outgoing FC:   {total_out_fc}")
    print(f"  Surcharge FC:  {round(total_surcharge_fc, 2)}")
    closing_fc = total_inc_fc - total_out_fc - total_surcharge_fc
    print(f"  Closing FC:    {round(closing_fc, 2)}")
    print(f"")
    print(f"  Incoming INR:  {total_inc_inr}")
    print(f"  Outgoing INR:  {total_out_inr}")
    print(f"  Surcharge INR: {round(total_surcharge_inr, 2)}")
    print(f"  Exchange Gain: {round(total_exchange_gain, 2)}")
    closing_inr = total_inc_inr - total_out_inr - total_surcharge_inr - total_exchange_gain
    print(f"  Closing INR:   {round(closing_inr, 2)}")
    print(f"\n{'='*80}\n")

if __name__ == '__main__':
    debug_part()
