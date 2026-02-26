import os
import django
from datetime import datetime

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sap_invoice.settings")
django.setup()

from sales.utils import TransactionMerger

def test_merger():
    print(f"--- Merger Logic Verification at {datetime.now()} ---")
    merger = TransactionMerger()
    
    # Test 1: Incoming with None (Should be ALL)
    print("\nTest 1: get_incoming_transactions(part_number=None)")
    incoming = merger.get_incoming_transactions(part_number=None)
    print(f"  Count: {len(incoming)}")
    if len(incoming) > 0:
        print(f"  First item: {incoming[0]['part_number']}")
        
    # Test 2: Outgoing with None (Should be ALL)
    print("\nTest 2: get_outgoing_transactions(part_number=None)")
    outgoing = merger.get_outgoing_transactions(part_number=None)
    print(f"  Count: {len(outgoing)}")

    # Test 3: Filter check
    print("\nTest 3: get_incoming_transactions with dummy date")
    # Using a future date to ensure it returns 0
    inc_future = merger.get_incoming_transactions(from_date="2099-01-01")
    print(f"  Count (should be 0): {len(inc_future)}")

if __name__ == "__main__":
    test_merger()
