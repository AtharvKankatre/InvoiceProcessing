import os
import django
from datetime import date

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sap_invoice.settings')
django.setup()

from sales.utils import TransactionMerger, BalanceCalculator
from sales.models import Invoice
from retail.models import InvoiceEntry

def debug_export():
    print("--- DEBUGGING EXPORT LOGIC ---")
    
    # Check raw counts
    print(f"Total Invoices: {Invoice.objects.count()}")
    print(f"Total InvoiceEntries: {InvoiceEntry.objects.count()}")
    
    merger = TransactionMerger()
    calculator = BalanceCalculator()
    
    part_number = 'all'
    fetch_part = None # Logic from view
    
    print(f"\nFetching transactions with part_number={fetch_part}...")
    
    incoming = merger.get_incoming_transactions(fetch_part)
    print(f"Incoming count: {len(incoming)}")
    if incoming:
        print(f"Sample incoming: {incoming[0]}")
        
    outgoing = merger.get_outgoing_transactions(fetch_part)
    print(f"Outgoing count: {len(outgoing)}")
    if outgoing:
        print(f"Sample outgoing: {outgoing[0]}")
        
    merged = merger.merge_and_sort(incoming, outgoing)
    print(f"Merged count: {len(merged)}")
    
    # Grouping logic
    from collections import defaultdict
    grouped_txns = defaultdict(list)
    for txn in merged:
        p_num = txn.get('part_number', 'UNKNOWN')
        grouped_txns[p_num].append(txn)
        
    print(f"Grouped into {len(grouped_txns)} parts.")
    
    transactions_with_balance = []
    for p_num, p_txns in grouped_txns.items():
        p_bals = calculator.calculate_running_balance(p_txns)
        transactions_with_balance.extend(p_bals)
        
    print(f"Final transactions with balance: {len(transactions_with_balance)}")
    
    # Filtering logic check
    data = []
    skipped = 0
    for txn in transactions_with_balance:
        if part_number and part_number != 'all' and txn.get('part_number') != part_number:
                skipped += 1
                continue
        data.append(txn)
        
    print(f"Final data rows: {len(data)} (Skipped: {skipped})")
    
    if not data and (len(incoming) > 0 or len(outgoing) > 0):
        print("!!! DATA LOST DURING PROCESSING !!!")
    elif data:
        print("Logic seems correct. Data is present.")

if __name__ == "__main__":
    debug_export()
