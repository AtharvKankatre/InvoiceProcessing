import os
import django
import sys
from datetime import datetime
from collections import defaultdict

# Setup Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sap_invoice.settings")
django.setup()

from sales.utils import TransactionMerger, BalanceCalculator

def force_print(msg):
    print(msg)
    sys.stdout.flush()

def test_view_logic():
    force_print(f"--- Simulating View Logic at {datetime.now()} ---")
    
    part_number = 'all' # Simulating the URL param
    
    # 1. Determine part_number to pass
    fetch_part = part_number if part_number != 'all' else None
    force_print(f"part_number='{part_number}' -> fetch_part={fetch_part}")

    merger = TransactionMerger()
    calculator = BalanceCalculator()
    
    # 2. Get transactions
    force_print("\nCalling get_incoming_transactions...")
    incoming_transactions = merger.get_incoming_transactions(
        fetch_part, None, None
    )
    force_print(f"  Result Count: {len(incoming_transactions)}")

    force_print("\nCalling get_outgoing_transactions...")
    outgoing_transactions = merger.get_outgoing_transactions(
        fetch_part, None, None
    )
    force_print(f"  Result Count: {len(outgoing_transactions)}")

    # 3. Merge
    merged_transactions = merger.merge_and_sort(
        incoming_transactions, outgoing_transactions
    )
    
    # 4. Group (Logic from view)
    if fetch_part:
        force_print("Running Single Part Logic")
    else:
        force_print("\nRunning 'All Parts' Grouping Logic")
        grouped_txns = defaultdict(list)
        for txn in merged_transactions:
             p_num = txn.get('part_number', 'UNKNOWN')
             grouped_txns[p_num].append(txn)
         
        transactions_with_balance = []
        for p_num, p_txns in grouped_txns.items():
             p_bals = calculator.calculate_running_balance(p_txns)
             transactions_with_balance.extend(p_bals)
        
        force_print(f"  Total items after grouping: {len(transactions_with_balance)}")

if __name__ == "__main__":
    test_view_logic()
