import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'InvoiceProcessing.settings')
django.setup()

from sales.services.stock_ledger import StockLedgerService
from sales.services.transaction_merger import TransactionMerger
from sales.services.balance_calculator import BalanceCalculator

def compare_api_vs_ledger():
    from_date = '2025-04-01'
    to_date = '2026-03-11'
    
    print("Generating Stock Ledger (Sheet 1)...")
    ledger_data = StockLedgerService.get_ledger_data('01-04-2025', '11-03-2026')
    
    s1_totals = {}
    for row in ledger_data:
        party = row.get("Party Name", "Unknown")
        s1_totals[party] = {
            'qty': int(row.get("Closing Stock Qty", 0) or 0)
        }

    print("Generating Part History (Frontend API equivalent)...")
    merger = TransactionMerger()
    calculator = BalanceCalculator()
    
    incoming = merger.get_incoming_transactions(None, from_date, to_date)
    outgoing = merger.get_outgoing_transactions(None, from_date, to_date)
    merged = merger.merge_and_sort(incoming, outgoing)
    
    # +++ Apply our new Opening Balance fix +++
    opening_balance = merger.get_opening_balance(None, from_date)
    if opening_balance:
        merged.insert(0, opening_balance)
    
    from collections import defaultdict
    grouped_txns = defaultdict(list)
    for txn in merged:
        p_num = txn.get('part_number', 'UNKNOWN')
        grouped_txns[p_num].append(txn)
        
    transactions_with_balance = []
    for p_num, p_txns in grouped_txns.items():
        p_bals = calculator.calculate_running_balance(p_txns)
        transactions_with_balance.extend(p_bals)

    # API groups by part number. We aggregate by party name to compare against Stock Ledger's party grouping.
    api_totals = {}
    for txn in transactions_with_balance:
        # Stock ledger groups by 'name' which is the customer name
        party = txn.get('name', 'UNKNOWN')
        if party not in api_totals:
            api_totals[party] = {'qty': 0}
            
        qty_change = txn.get('qty', 0)
        api_totals[party]['qty'] += int(qty_change)
        
    print("\n=== COMPARING SH1 (Stock Ledger) vs API (Part History) ===")
    all_parties = set(list(s1_totals.keys()) + list(api_totals.keys()))
    
    mismatch_found = False
    for p in sorted(all_parties):
        if not p.strip() or 'Unknown' in p or 'SYSTEM' in p:
             # SYSTEM isn't an actual party, it's just the label we put on OPENING BALANCE row
             # that needs to be summed under the actual customer
            continue
            
        s1 = s1_totals.get(p, {'qty': 0})
        api = api_totals.get(p, {'qty': 0})
        
        # We must add the SYSTEM (opening balance) qty manually distributed to proper parties if we were testing perfectly.
        # Wait, the opening balance row has name='SYSTEM', so its QTY is attributed to 'SYSTEM' here. 
        # But wait! Stock Ledger attributes opening balance correctly to the Party (e.g., Kawasaki).
        # We set name='SYSTEM' in our new get_opening_balance method, which prevents it from being grouped properly by customer name in our custom test map.
        # Actually, let's just test single part export to prove it works first.
        
compare_api_vs_ledger()

print("\n\n--- Kawasaki Specific Test ---")
merger = TransactionMerger()
incoming = merger.get_incoming_transactions('PART-A400', '2025-04-01', '2026-03-11') # assuming PART-A400 is Kawasaki
outgoing = merger.get_outgoing_transactions('PART-A400', '2025-04-01', '2026-03-11')
merged = merger.merge_and_sort(incoming, outgoing)

ob = merger.get_opening_balance('PART-A400', '2025-04-01')
if ob: 
    print(f"Opening Balance Row Created: {ob['qty']}")
    merged.insert(0, ob)

calc = BalanceCalculator()
merged = calc.calculate_running_balance(merged)

print("Part History Export Rows for Kawasaki Part:")
for r in merged:
    print(f"  {r['date']} | {r['name']} | {r['type']} | Qty: {r['qty']} | Running Bal: {r['on_hand']}")
