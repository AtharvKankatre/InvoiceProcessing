from django.core.management.base import BaseCommand
from sales.services.stock_ledger import StockLedgerService
from datetime import date


class Command(BaseCommand):
    help = "Check Stock Ledger for Jul-Dec 2025 to verify Opening Stock logic"

    def handle(self, *args, **options):
        self.stdout.write("=== Test Case: Jul 1 2025 – Dec 31 2025 ===")
        self.stdout.write("Expected: Opening Stock = H1 (Jan-Jun) net, Shipment/Despatch = H2 data\n")

        data = StockLedgerService.get_ledger_data(
            from_date=date(2025, 7, 1),
            to_date=date(2025, 12, 31)
        )

        for row in data:
            self.stdout.write(
                f"Party: {row['Party Name']:<22} | Code: {row['Code No. Stock AC']:<5} | "
                f"Opening Qty: {row['Opening Stock Qty']:>8} | "
                f"Inc Qty: {row['Shipment to WH (Add) Qty']:>8} | "
                f"Out Qty: {row['Despatch (Less) Qty']:>8} | "
                f"Closing Qty: {row['Closing Stock Qty']:>8}"
            )
