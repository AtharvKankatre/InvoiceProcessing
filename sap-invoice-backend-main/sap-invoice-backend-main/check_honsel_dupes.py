import os, sys, django
from collections import defaultdict
from pprint import pprint

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sap_invoice.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from sales.services.transaction_merger import TransactionMerger
from sales.models import InvoiceEntryConsumption

# The exact part from the screenshot
part_number = "CFORDFG007T4EAA"

print(f"=== Debugging Duplicates in TransactionMerger for {part_number} ===")

merger = TransactionMerger()
inc = merger.get_incoming_transactions(part_number)
out = merger.get_outgoing_transactions(part_number)

print(f"1. Database Fetch:")
print(f"   Fetched {len(inc)} Incoming Records")
print(f"   Fetched {len(out)} Outgoing Records")

# Look specifically at the problem invoice "2242500426/A" in the raw fetch
problem_out = [txn for txn in out if txn.get('invoice_number') == '2242500426/A']
print(f"   -> How many times does '2242500426/A' appear in the raw fetch? {len(problem_out)}")

# Let's run the exact merge_and_sort logic step-by-step to see where it multiplies
incoming = sorted(inc, key=lambda x: (x['date'], x['created_at']))
outgoing = out

# Build Bill-to-Bill map (Layer 1)
incoming_by_invoice_num = {txn.get('invoice_number', ''): txn for txn in incoming if txn.get('invoice_number')}

bill_to_bill_map = defaultdict(list)
bill_to_bill_matched = set()

for txn in outgoing:
    out_inv_num = txn.get('invoice_number', '')
    if '/' in out_inv_num:
        base_num = out_inv_num.split('/')[0]
        if base_num in incoming_by_invoice_num:
            bill_to_bill_map[base_num].append(txn)
            if txn.get('invoice_entry_id'):
                bill_to_bill_matched.add(txn['invoice_entry_id'])

print(f"\n2. Layer 1 (Bill-to-Bill Matching):")
print(f"   Matched {len(bill_to_bill_matched)} outgoing entries via '/A' suffix.")

# Build Consumption map (Layer 2)
outgoing_by_entry_id = {txn.get('invoice_entry_id'): txn for txn in outgoing 
                        if txn.get('invoice_entry_id') and txn.get('invoice_entry_id') not in bill_to_bill_matched}

incoming_ids = [txn['invoice_id'] for txn in incoming if txn.get('invoice_id')]
outgoing_entry_ids = list(outgoing_by_entry_id.keys())

invoice_to_consumptions = defaultdict(list)
if incoming_ids and outgoing_entry_ids:
    consumptions = InvoiceEntryConsumption.objects.filter(
        invoice_id__in=incoming_ids,
        invoice_entry_id__in=outgoing_entry_ids,
    ).values('invoice_id', 'invoice_entry_id', 'consumed_qty', 'fc_value')

    print(f"\n3. Layer 2 (Consumption Matching):")
    print(f"   Found {len(consumptions)} consumption links for the remaining outgoing rows.")
    for c in consumptions:
        invoice_to_consumptions[c['invoice_id']].append(c)

# Build Final Array (This is where the duplication likely happens)
print("\n4. Building Final Array (Tracking 2242500426/A):")
final_count_426A = 0

for inc_txn in incoming:
    inv_num = inc_txn.get('invoice_number', '')
    inv_id = inc_txn.get('invoice_id')
    
    # Layer 1 additions
    if inv_num in bill_to_bill_map:
        for out_txn in bill_to_bill_map[inv_num]:
            if out_txn['invoice_number'] == '2242500426/A':
                print(f"   [+] Added via Layer 1 (Bill-to-Bill) under {inv_num}")
                final_count_426A += 1
                
    # Layer 2 additions
    if inv_id and inv_id in invoice_to_consumptions:
        for cons in invoice_to_consumptions[inv_id]:
            entry_id = cons['invoice_entry_id']
            if entry_id in outgoing_by_entry_id:
                out_txn = outgoing_by_entry_id[entry_id]
                if out_txn['invoice_number'] == '2242500426/A':
                    print(f"   [+] Added via Layer 2 (Consumption) under {inv_num}")
                    final_count_426A += 1

print(f"\nResult: '2242500426/A' was added to the final array {final_count_426A} times.")
if final_count_426A > 1:
    print("CONCLUSION: The merge_and_sort logic is duplicating the row. It likely matched on BOTH Layer 1 AND Layer 2, or the Consumption table has duplicate links.")
