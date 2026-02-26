"""
Seed 1 year of dummy Stock Ledger data (Jan 2025 - Dec 2025).

Design:
  - Each party appears in BOTH incoming (Invoice) and outgoing (InvoiceEntry)
  - Incoming qty is always LARGER than outgoing qty → all values positive
  - Incoming invoices have customer_code
  - Outgoing InvoiceRetailPartMap has customer_code = NULL (as per requirement)

Parties:
  Code 1000 → Cooper Corp
  Code 1001 → Global Supplies
  Code 1002 → Techno Parts Ltd
  Code 2000 → Honda
  Code 2001 → Maruti
  Code 2002 → Hyundai
  Code 2003 → Tata Motors

Parts: PART-X100, PART-Y200, PART-Z300, PART-A400, PART-B500
"""

from django.core.management.base import BaseCommand
from sales.models import Invoice, InvoiceRetailPartMap
from retail.models import InvoiceEntry
from django.contrib.auth import get_user_model
from datetime import date
import random

User = get_user_model()

# All parties: each has a name, code, and a retail part they despatch
PARTIES = [
    {"name": "Cooper Corp",      "code": "1000", "part": "PART-X100", "retail": "RETAIL-X100"},
    {"name": "Global Supplies",  "code": "1001", "part": "PART-Y200", "retail": "RETAIL-Y200"},
    {"name": "Techno Parts Ltd", "code": "1002", "part": "PART-Z300", "retail": "RETAIL-Z300"},
    {"name": "Honda",            "code": "2000", "part": "PART-A400", "retail": "RETAIL-A400"},
    {"name": "Maruti",           "code": "2001", "part": "PART-B500", "retail": "RETAIL-B500"},
    {"name": "Hyundai",          "code": "2002", "part": "PART-X100", "retail": "RETAIL-X100-H"},
    {"name": "Tata Motors",      "code": "2003", "part": "PART-Y200", "retail": "RETAIL-Y200-T"},
]

INR_RATE = 83.5


class Command(BaseCommand):
    help = "Seed 1 year of dummy Stock Ledger data (Jan–Dec 2025) with all-positive values"

    def handle(self, *args, **options):
        self.stdout.write("Clearing existing data...")
        InvoiceEntry.objects.all().delete()
        InvoiceRetailPartMap.objects.all().delete()
        Invoice.objects.all().delete()

        user, _ = User.objects.get_or_create(
            username="seeder",
            defaults={"email": "seeder@example.com"}
        )

        # ── 1. Create Part Maps (Outgoing mapping, NO customer_code) ────────
        # Each party has a retail part they despatch to
        for party in PARTIES:
            InvoiceRetailPartMap.objects.create(
                sale_part_number=party["part"],
                retail_part_number=party["retail"],
                company_name=party["name"],
                customer_code=None,   # NO CODE as per requirement
                created_by=user,
            )
            self.stdout.write(f"  Map: {party['part']} → {party['retail']} ({party['name']})")

        # ── 2. Seed Incoming Invoices (Jan–Dec 2025) ─────────────────────────
        # Each party gets 3–5 incoming shipments per month
        # Incoming qty range: 300–600 per shipment (always > outgoing)
        invoice_count = 0
        for party in PARTIES:
            for month in range(1, 13):
                num_shipments = random.randint(3, 5)
                for i in range(num_shipments):
                    day = random.randint(1, 28)
                    inv_date = date(2025, month, day)
                    qty = random.randint(300, 600)          # large incoming
                    usd_rate = round(random.uniform(20.0, 60.0), 2)

                    Invoice.objects.create(
                        invoice_number=f"INV-{party['code']}-{month:02d}-{i+1:02d}",
                        part_number=party["part"],
                        date=inv_date,
                        qty=qty,
                        dollar_rate=usd_rate,
                        inr_rate=round(usd_rate * INR_RATE, 4),
                        dollar_total=round(qty * usd_rate, 2),
                        inr_total=round(qty * usd_rate * INR_RATE, 2),
                        customer_name=party["name"],
                        customer_code=party["code"],   # HAS CODE on incoming
                        created_by=user,
                    )
                    invoice_count += 1

        self.stdout.write(f"  Created {invoice_count} incoming invoices.")

        # ── 3. Seed Outgoing Entries (Jan–Dec 2025) ──────────────────────────
        # Each party despatches 2–4 times per month
        # Outgoing qty range: 50–150 per despatch (always < incoming)
        entry_count = 0
        for party in PARTIES:
            for month in range(1, 13):
                num_despatches = random.randint(2, 4)
                for i in range(num_despatches):
                    day = random.randint(1, 28)
                    entry_date = date(2025, month, day)
                    qty = random.randint(50, 150)           # small outgoing
                    usd_rate = round(random.uniform(20.0, 60.0), 2)

                    InvoiceEntry.objects.create(
                        part_number=party["retail"],
                        date=entry_date,
                        qty=qty,
                        usd_rate=usd_rate,
                        inr_rate=round(usd_rate * INR_RATE, 4),
                        usd_total=round(qty * usd_rate, 2),
                        inr_total=round(qty * usd_rate * INR_RATE, 2),
                        conversion_rate=INR_RATE,
                        created_by=user,
                    )
                    entry_count += 1

        self.stdout.write(f"  Created {entry_count} outgoing entries.")

        # ── Summary ──────────────────────────────────────────────────────────
        self.stdout.write(self.style.SUCCESS(
            f"\n✅ Done! {invoice_count} incoming invoices + {entry_count} outgoing entries seeded."
        ))
        self.stdout.write("   Parties: Cooper Corp (1000), Global Supplies (1001), Techno Parts Ltd (1002),")
        self.stdout.write("            Honda (2000), Maruti (2001), Hyundai (2002), Tata Motors (2003)")
        self.stdout.write("   Period: Jan 2025 – Dec 2025")
        self.stdout.write("   Incoming qty per shipment: 300–600 | Outgoing qty per despatch: 50–150")
        self.stdout.write("   → All Opening/Closing values will be POSITIVE ✅")
