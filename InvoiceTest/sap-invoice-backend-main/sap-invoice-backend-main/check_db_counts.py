import os
import django
from datetime import datetime

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sap_invoice.settings")
django.setup()

from sales.models import Invoice
from retail.models import InvoiceEntry

def check_counts():
    print(f"--- Database Verification at {datetime.now()} ---")
    
    # 1. Check Invoice (Incoming)
    inv_count = Invoice.objects.count()
    print(f"Invoice (Incoming) Count: {inv_count}")
    
    if inv_count > 0:
        first = Invoice.objects.first()
        print(f"  First Invoice: Date={first.date}, Part={first.part_number}")
    else:
        print("  Table appears empty.")

    # 2. Check InvoiceEntry (Outgoing)
    entry_count = InvoiceEntry.objects.count()
    print(f"InvoiceEntry (Outgoing) Count: {entry_count}")
    
    if entry_count > 0:
        first = InvoiceEntry.objects.first()
        print(f"  First Entry: Date={first.date}, Part={first.part_number}")
    else:
        print("  Table appears empty.")

if __name__ == "__main__":
    check_counts()
