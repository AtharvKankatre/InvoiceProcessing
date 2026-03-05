"""
Seed dummy Stock Ledger data with InvoiceEntryConsumption records.

This creates a realistic dataset where:
  - Each party has multiple incoming invoices (with invoice_qty)
  - Each party has outgoing retail entries
  - Consumption records link outgoing entries to incoming invoices (FIFO)
  - Some invoices are partially consumed → visible in invoice-wise closing breakdown

Parties:
  Code 1000 → Cooper Corp        (PART-X100)
  Code 2000 → Honda              (PART-A400)
  Code 2001 → Kawasaki           (PART-A400, shared part with Honda)
  Code 2002 → Hyundai            (PART-Y200)
"""

from django.core.management.base import BaseCommand
from sales.models import Invoice, InvoiceRetailPartMap, InvoiceEntryConsumption
from retail.models import InvoiceEntry
from django.contrib.auth import get_user_model
from datetime import date
from decimal import Decimal

User = get_user_model()

INR_RATE = Decimal("83.50")


class Command(BaseCommand):
    help = "Seed dummy data with consumption records for testing invoice-wise closing breakdown"

    def handle(self, *args, **options):
        self.stdout.write("Clearing existing data...")
        InvoiceEntryConsumption.objects.all().delete()
        InvoiceEntry.objects.all().delete()
        InvoiceRetailPartMap.objects.all().delete()
        Invoice.objects.all().delete()

        user, _ = User.objects.get_or_create(
            username="seeder",
            defaults={"email": "seeder@example.com"}
        )

        # ── 1. Part Maps ────────────────────────────────────────────────
        part_maps = [
            {"sale": "PART-X100", "retail": "RETAIL-X100",   "company": "Cooper Corp",  "code": None},
            {"sale": "PART-A400", "retail": "RETAIL-A400-H", "company": "Honda",         "code": None},
            {"sale": "PART-A400", "retail": "RETAIL-A400-K", "company": "Kawasaki",      "code": None},
            {"sale": "PART-Y200", "retail": "RETAIL-Y200",   "company": "Hyundai",       "code": None},
        ]
        for pm in part_maps:
            InvoiceRetailPartMap.objects.create(
                sale_part_number=pm["sale"],
                retail_part_number=pm["retail"],
                company_name=pm["company"],
                customer_code=pm["code"],
                created_by=user,
            )
            self.stdout.write(f"  Map: {pm['sale']} → {pm['retail']} ({pm['company']})")

        # ── 2. Incoming Invoices ────────────────────────────────────────
        invoices = {}  # key → Invoice object for later consumption linking

        invoice_data = [
            # Cooper Corp — PART-X100: 3 invoices, 2 partially consumed
            {"key": "C1", "inv_no": "INV-1000-01", "part": "PART-X100", "date": date(2025, 1, 15),
             "qty": 500, "usd_rate": Decimal("25.00"), "customer": "Cooper Corp", "code": "1000"},
            {"key": "C2", "inv_no": "INV-1000-02", "part": "PART-X100", "date": date(2025, 3, 10),
             "qty": 300, "usd_rate": Decimal("27.50"), "customer": "Cooper Corp", "code": "1000"},
            {"key": "C3", "inv_no": "INV-1000-03", "part": "PART-X100", "date": date(2025, 6, 5),
             "qty": 400, "usd_rate": Decimal("26.00"), "customer": "Cooper Corp", "code": "1000"},

            # Honda — PART-A400: 3 invoices
            {"key": "H1", "inv_no": "INV-2000-01", "part": "PART-A400", "date": date(2025, 2, 1),
             "qty": 600, "usd_rate": Decimal("45.00"), "customer": "Honda", "code": "2000"},
            {"key": "H2", "inv_no": "INV-2000-02", "part": "PART-A400", "date": date(2025, 4, 15),
             "qty": 400, "usd_rate": Decimal("47.00"), "customer": "Honda", "code": "2000"},
            {"key": "H3", "inv_no": "INV-2000-03", "part": "PART-A400", "date": date(2025, 7, 20),
             "qty": 350, "usd_rate": Decimal("44.50"), "customer": "Honda", "code": "2000"},

            # Kawasaki — PART-A400 (shared part): 2 invoices
            {"key": "K1", "inv_no": "INV-2001-01", "part": "PART-A400", "date": date(2025, 1, 20),
             "qty": 200, "usd_rate": Decimal("46.00"), "customer": "Kawasaki", "code": "2001"},
            {"key": "K2", "inv_no": "INV-2001-02", "part": "PART-A400", "date": date(2025, 5, 10),
             "qty": 300, "usd_rate": Decimal("48.00"), "customer": "Kawasaki", "code": "2001"},

            # Hyundai — PART-Y200: 2 invoices
            {"key": "Y1", "inv_no": "INV-2002-01", "part": "PART-Y200", "date": date(2025, 3, 1),
             "qty": 800, "usd_rate": Decimal("30.00"), "customer": "Hyundai", "code": "2002"},
            {"key": "Y2", "inv_no": "INV-2002-02", "part": "PART-Y200", "date": date(2025, 8, 1),
             "qty": 500, "usd_rate": Decimal("32.00"), "customer": "Hyundai", "code": "2002"},
        ]

        for d in invoice_data:
            usd_total = d["qty"] * d["usd_rate"]
            inr_rate = d["usd_rate"] * INR_RATE
            inr_total = d["qty"] * inr_rate
            inv = Invoice.objects.create(
                invoice_number=d["inv_no"],
                part_number=d["part"],
                date=d["date"],
                qty=d["qty"],
                invoice_qty=d["qty"],
                dollar_rate=d["usd_rate"],
                dollar_total=usd_total,
                inr_rate=inr_rate,
                inr_total=inr_total,
                conversion_rate=INR_RATE,
                customer_name=d["customer"],
                customer_code=d["code"],
                created_by=user,
            )
            invoices[d["key"]] = inv
            self.stdout.write(f"  Invoice: {d['inv_no']} | {d['customer']} | {d['part']} | Qty={d['qty']}")

        # ── 3. Outgoing Entries + Consumption Records ───────────────────
        # We create retail entries and link them to invoices via consumption (FIFO style)
        outgoing_data = [
            # Cooper Corp dispatches against PART-X100
            # Consumes 400 from C1 (leaving 100), 0 from C2, 0 from C3
            {"retail": "RETAIL-X100", "date": date(2025, 2, 15), "qty": 200, "usd_rate": Decimal("25.00"),
             "consumptions": [("C1", 200)]},
            {"retail": "RETAIL-X100", "date": date(2025, 4, 20), "qty": 200, "usd_rate": Decimal("27.50"),
             "consumptions": [("C1", 200)]},
            {"retail": "RETAIL-X100", "date": date(2025, 7, 10), "qty": 150, "usd_rate": Decimal("26.00"),
             "consumptions": [("C1", 100), ("C2", 50)]},  # C1 fully consumed, C2 partially

            # Honda dispatches against PART-A400
            # Consumes 600 from H1 (fully consumed), 100 from H2 (leaving 300)
            {"retail": "RETAIL-A400-H", "date": date(2025, 3, 10), "qty": 300, "usd_rate": Decimal("45.00"),
             "consumptions": [("H1", 300)]},
            {"retail": "RETAIL-A400-H", "date": date(2025, 5, 5), "qty": 400, "usd_rate": Decimal("46.00"),
             "consumptions": [("H1", 300), ("H2", 100)]},  # H1 done, start H2

            # Kawasaki dispatches against PART-A400
            # Consumes 150 from K1 (leaving 50)
            {"retail": "RETAIL-A400-K", "date": date(2025, 3, 15), "qty": 150, "usd_rate": Decimal("46.00"),
             "consumptions": [("K1", 150)]},

            # Hyundai dispatches against PART-Y200
            # Consumes 500 from Y1 (leaving 300)
            {"retail": "RETAIL-Y200", "date": date(2025, 5, 10), "qty": 300, "usd_rate": Decimal("30.00"),
             "consumptions": [("Y1", 300)]},
            {"retail": "RETAIL-Y200", "date": date(2025, 9, 15), "qty": 200, "usd_rate": Decimal("31.00"),
             "consumptions": [("Y1", 200)]},
        ]

        entry_count = 0
        cons_count = 0
        for od in outgoing_data:
            usd_total = od["qty"] * od["usd_rate"]
            inr_rate = od["usd_rate"] * INR_RATE
            inr_total = od["qty"] * inr_rate

            entry = InvoiceEntry.objects.create(
                part_number=od["retail"],
                date=od["date"],
                qty=od["qty"],
                usd_rate=od["usd_rate"],
                usd_total=usd_total,
                inr_rate=inr_rate,
                inr_total=inr_total,
                conversion_rate=INR_RATE,
                created_by=user,
            )
            entry_count += 1

            # Create consumption records linking to invoices
            for inv_key, consumed_qty in od["consumptions"]:
                inv = invoices[inv_key]
                fc_rate = inv.dollar_rate or Decimal(0)
                fc_value = consumed_qty * fc_rate

                InvoiceEntryConsumption.objects.create(
                    invoice_entry=entry,
                    invoice=inv,
                    consumed_qty=consumed_qty,
                    fc_value=fc_value,
                    created_by=user,
                )
                cons_count += 1

            self.stdout.write(f"  Entry: {od['retail']} | {od['date']} | Qty={od['qty']} | Consumptions={len(od['consumptions'])}")

        # ── Summary ────────────────────────────────────────────────────
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"✅ Done! Seeded:"))
        self.stdout.write(f"   {len(invoice_data)} incoming invoices")
        self.stdout.write(f"   {entry_count} outgoing entries")
        self.stdout.write(f"   {cons_count} consumption records")
        self.stdout.write(f"   {len(part_maps)} part maps")
        self.stdout.write("")
        self.stdout.write("  Expected closing breakdown:")
        self.stdout.write("   PART-A400 / Honda:    INV-2000-01 → 0 (fully consumed)")
        self.stdout.write("                         INV-2000-02 → 300 remaining")
        self.stdout.write("                         INV-2000-03 → 350 remaining (untouched)")
        self.stdout.write("   PART-A400 / Kawasaki: INV-2001-01 → 50 remaining")
        self.stdout.write("                         INV-2001-02 → 300 remaining (untouched)")
        self.stdout.write("   PART-X100 / Cooper:   INV-1000-01 → 0 (fully consumed)")
        self.stdout.write("                         INV-1000-02 → 250 remaining")
        self.stdout.write("                         INV-1000-03 → 400 remaining (untouched)")
        self.stdout.write("   PART-Y200 / Hyundai:  INV-2002-01 → 300 remaining")
        self.stdout.write("                         INV-2002-02 → 500 remaining (untouched)")
