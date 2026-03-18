import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'InvoiceProcessing.settings')
django.setup()

from sales.services.stock_ledger import StockLedgerService
from sales.services.transaction_merger import TransactionMerger

print("=== Kawasaki Debug ===")
party = "Kawasaki"

print("\n--- 1. Stock Ledger Details ---")
ledger_data = StockLedgerService.get_ledger_data('01-04-2025', '11-03-2026')
for row in ledger_data:
    if "Kawasaki" in row.get("Party Name", ""):
        print(f"Opening: {row.get('Opening Stock Qty')}, Shipment: {row.get('Shipment Qty')}, Dispatch: {row.get('Despatch Qty', 0)}, Closing: {row.get('Closing Stock Qty', 0)}")

print("\n--- 2. Part History (API) Details ---")
merger = TransactionMerger()
incoming = merger.get_incoming_transactions(None, '2025-04-01', '2026-03-11')
outgoing = merger.get_outgoing_transactions(None, '2025-04-01', '2026-03-11')

k_in = 0
k_out = 0
print("Incoming txns for Kawasaki:")
for t in incoming:
    if "Kawasaki" in t.get('name', ''):
        print(f"  {t['date']} - {t['invoice_number']} - QTY: {t['qty']}")
        k_in += t['qty']

print("Outgoing txns for Kawasaki:")
for t in outgoing:
    if "Kawasaki" in t.get('name', ''):
        print(f"  {t['date']} - {t['invoice_number']} - QTY: {t['qty']}")
        k_out += t['qty']

print(f"\nAPI Totals -> Incoming: {k_in}, Outgoing: {k_out}, Closing: {k_in - k_out}")

