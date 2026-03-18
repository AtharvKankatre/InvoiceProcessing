import os, sys, django
from pprint import pprint

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sap_invoice.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from sales.services.transaction_merger import TransactionMerger

merger = TransactionMerger()
part_number = "CFORDFG007T4EAA"

inc = merger.get_incoming_transactions(part_number)
out = merger.get_outgoing_transactions(part_number)

print(f"--- Fetched {len(inc)} Incoming and {len(out)} Outgoing for {part_number} ---")

# Let's exactly run merge_and_sort logic here with debug prints
incoming = inc
outgoing = out

incoming.sort(key=lambda x: (x['date'], x['created_at']))

incoming_by_invoice_num = {}
for txn in incoming:
    inv_num = txn.get('invoice_number', '')
    if inv_num:
        incoming_by_invoice_num[inv_num] = txn

from collections import defaultdict
bill_to_bill_map = defaultdict(list)
bill_to_bill_matched = set()

for txn in outgoing:
    out_inv_num = txn.get('invoice_number', '')
    if '/' in out_inv_num:
        base_num = out_inv_num.split('/')[0]
        if base_num in incoming_by_invoice_num:
            bill_to_bill_map[base_num].append(txn)
            entry_id = txn.get('invoice_entry_id')
            if entry_id:
                bill_to_bill_matched.add(entry_id)

print(f"Layer 1 Matches: {len(bill_to_bill_matched)} outgoing entries matched bill-to-bill")

outgoing_by_entry_id = {}
for txn in outgoing:
    entry_id = txn.get('invoice_entry_id')
    if entry_id and entry_id not in bill_to_bill_matched:
        outgoing_by_entry_id[entry_id] = txn

print(f"Layer 2 Candidates: {len(outgoing_by_entry_id)} outgoing entries left for consumption matching")

from sales.models import InvoiceEntryConsumption
incoming_ids = [txn['invoice_id'] for txn in incoming if txn.get('invoice_id')]
outgoing_entry_ids = list(outgoing_by_entry_id.keys())

invoice_to_consumptions = defaultdict(list)
if incoming_ids and outgoing_entry_ids:
    consumptions = InvoiceEntryConsumption.objects.filter(
        invoice_id__in=incoming_ids,
        invoice_entry_id__in=outgoing_entry_ids,
    ).values(
        'invoice_id', 'invoice_entry_id', 'consumed_qty', 'fc_value'
    ).order_by('invoice_entry__date', 'invoice_entry_id')

    print(f"Found {len(consumptions)} consumption records linking these un-matched outgoing rows.")
    for c in consumptions:
        invoice_to_consumptions[c['invoice_id']].append({
            'entry_id': c['invoice_entry_id'],
            'consumed_qty': c['consumed_qty'] or 0,
            'fc_value': float(c['fc_value'] or 0),
        })

result = []
placed_entry_ids = set(bill_to_bill_matched)

for inc_txn in incoming:
    result.append(inc_txn)
    inv_num = inc_txn.get('invoice_number', '')
    inv_id = inc_txn.get('invoice_id')

    if inv_num in bill_to_bill_map:
        for out_txn in bill_to_bill_map[inv_num]:
            print(f" [L1] Appending {out_txn['invoice_number']} under {inv_num}")
            result.append(out_txn)

    if inv_id and inv_id in invoice_to_consumptions:
        for cons in invoice_to_consumptions[inv_id]:
            entry_id = cons['entry_id']
            if entry_id not in outgoing_by_entry_id:
                # Wait, could this happen? Only if it was in Layer 1, but we excluded those from outgoing_entry_ids!
                print(f" [!] entry_id {entry_id} in consumptions but not in outgoing_by_entry_id! Was it matched in L1? {entry_id in bill_to_bill_matched}")
                continue
            
            print(f" [L2] Appending split for {outgoing_by_entry_id[entry_id]['invoice_number']} under {inv_num}")

print("\nDONE. If it appears duplicated in the Excel, it either printed twice above, or it's duplicated in views.py later.")
