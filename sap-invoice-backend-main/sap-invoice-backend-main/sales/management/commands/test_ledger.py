from django.core.management.base import BaseCommand
from sales.models import Invoice, InvoiceRetailPartMap
from retail.models import InvoiceEntry
from django.contrib.auth import get_user_model
from sales.services.stock_ledger import StockLedgerService
from datetime import date
import pandas as pd

User = get_user_model()

class Command(BaseCommand):
    help = 'Test Stock Ledger Logic'

    def handle(self, *args, **options):
        self.stdout.write("Setting up test data...")
        user, _ = User.objects.get_or_create(username="testuser", defaults={"email": "test@example.com"})

        # Clean up
        Invoice.objects.all().delete()
        InvoiceRetailPartMap.objects.all().delete()
        InvoiceEntry.objects.all().delete()

        # 1. Incoming Invoice (Customer: Cooper, Code: 1000)
        inv1 = Invoice.objects.create(
            invoice_number="INV001",
            part_number="PART-A",
            date=date(2025, 1, 15),
            qty=100,
            dollar_rate=10.0,
            inr_rate=800.0,
            dollar_total=1000.0,
            inr_total=80000.0,
            customer_name="Cooper Corp",
            customer_code="1000",
            created_by=user
        )

        # 2. Outgoing Map (Customer: Honda, Code: 2000)
        map1 = InvoiceRetailPartMap.objects.create(
            sale_part_number="PART-A",
            retail_part_number="RETAIL-A",
            company_name="Honda",
            customer_code="2000",
            created_by=user
        )

        # 3. Outgoing Transaction (Despatch to Honda)
        entry1 = InvoiceEntry.objects.create(
            part_number="RETAIL-A",
            date=date(2025, 1, 20),
            qty=50,
            usd_rate=12.0,
            inr_rate=900.0,
            usd_total=600.0,
            inr_total=45000.0,
            conversion_rate=75.0,
            created_by=user
        )


        self.stdout.write("Test data created.")

        # 4. Run Service
        self.stdout.write("\nRunning StockLedgerService...")
        data = StockLedgerService.get_ledger_data(from_date=date(2025, 1, 1), to_date=date(2025, 1, 31))

        # 5. Verify Output
        df = pd.DataFrame(data)
        self.stdout.write("\nResult DataFrame:")
        self.stdout.write(df.to_string())

        # Check Cooper (Incoming)
        cooper_row = df[df["Party Name"] == "Cooper Corp"]
        if not cooper_row.empty:
            self.stdout.write("\n[PASS] Found Cooper Corp")
            qty = cooper_row.iloc[0]["Shipment to WH (Add) Qty"]
            if qty == 100:
                 self.stdout.write("[PASS] Cooper Incoming Qty is 100")
            else:
                 self.stdout.write(f"[FAIL] Cooper Incoming Qty is {qty}, expected 100")
        else:
            self.stdout.write("\n[FAIL] Cooper Corp not found in report")

        # Check Honda (Outgoing)
        honda_row = df[df["Party Name"] == "Honda"]
        if not honda_row.empty:
            self.stdout.write("\n[PASS] Found Honda")
            code = honda_row.iloc[0]["Code No. Stock AC"]
            if code == "2000":
                 self.stdout.write("[PASS] Honda Code is 2000")
            else:
                 self.stdout.write(f"[FAIL] Honda Code is {code}, expected 2000")
            
            qty = honda_row.iloc[0]["Despatch (Less) Qty"]
            if qty == 50:
                 self.stdout.write("[PASS] Honda Despatch Qty is 50")
            else:
                 self.stdout.write(f"[FAIL] Honda Despatch Qty is {qty}, expected 50")
        else:
            self.stdout.write("\n[FAIL] Honda not found in report")
