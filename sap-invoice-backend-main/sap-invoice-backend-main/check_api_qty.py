import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'InvoiceProcessing.settings')
django.setup()

from sales.services.stock_ledger import StockLedgerService
from sales.services.transaction_merger import TransactionMerger
from sales.services.balance_calculator import BalanceCalculator

def compare_api_vs_ledger():
    print("Generating Stock Ledger (Sheet 1)...")
    ledger_data = StockLedgerService.get_ledger_data('01-04-2025', '11-03-2026')
    
    s1_totals = {}
    for row in ledger_data:
        party = row.get("Party Name", "Unknown")
        s1_totals[party] = {
            'qty': int(row.get("Closing Stock Qty", 0) or 0),
            'fc': round(float(row.get("Closing Stock FC Value", 0) or 0), 2)
        }

    print("Generating Part History (Frontend API equivalent)...")
    # This is exactly what sales/views.py PartHistoryViewSet does for 'All'
    merger = TransactionMerger()
    calculator = BalanceCalculator()
    
    incoming = merger.get_incoming_transactions(None, '2025-04-01', '2026-03-11')
    outgoing = merger.get_outgoing_transactions(None, '2025-04-01', '2026-03-11')
    merged = merger.merge_and_sort(incoming, outgoing)
    
    # The API groups by part number, calculates balance, then returns
    from collections import defaultdict
    grouped_txns = defaultdict(list)
    for txn in merged:
        p_num = txn.get('part_number', 'UNKNOWN')
        grouped_txns[p_num].append(txn)
        
    transactions_with_balance = []
    for p_num, p_txns in grouped_txns.items():
        p_bals = calculator.calculate_running_balance(p_txns)
        transactions_with_balance.extend(p_bals)

    # Now aggregate the API results by customer name to compare with Stock Ledger
    api_totals = {}
    for txn in transactions_with_balance:
        # Stock ledger groups by 'name' which is the customer name
        party = txn.get('name', 'Unknown')
        if party not in api_totals:
            api_totals[party] = {'qty': 0, 'fc': 0.0}
            
        qty_change = txn.get('qty', 0)
        # Incoming is positive, outgoing is negative in the API
        if txn.get('type') == 'OUTGOING':
            qty_change = -qty_change
            
        api_totals[party]['qty'] += int(qty_change)
        
        # We'll just compare QTY first since that's the main complaint
        
    print("\n=== COMPARING SH1 (Stock Ledger) vs API (Part History) ===")
    all_parties = set(list(s1_totals.keys()) + list(api_totals.keys()))
    
    mismatch_found = False
    for p in sorted(all_parties):
        if not p.strip() or 'Unknown' in p:
            continue
            
        s1 = s1_totals.get(p, {'qty': 0})
        api = api_totals.get(p, {'qty': 0})
        
        if s1['qty'] != api['qty']:
            print(f"MISMATCH FOR: {p}")
            print(f"  SH1 (Stock Ledger): QTY = {s1['qty']}")
            print(f"  API (Part History): QTY = {api['qty']}")
            mismatch_found = True
            
    if not mismatch_found:
        print("PERFECT MATCH FOR ALL CUSTOMERS!")

compare_api_vs_ledger()
