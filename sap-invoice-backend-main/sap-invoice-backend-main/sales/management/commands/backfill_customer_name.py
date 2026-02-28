"""
Backfill customer_name on Invoice records by matching
Invoice.part_number -> InvoiceRetailPartMap.sale_part_number -> company_name

Run:  python manage.py backfill_customer_name
"""
from django.core.management.base import BaseCommand
from sales.models import Invoice, InvoiceRetailPartMap


class Command(BaseCommand):
    help = "Backfill customer_name on Invoice records using InvoiceRetailPartMap part mapping"

    def handle(self, *args, **options):
        # Build a lookup: sale_part_number -> company_name
        part_to_company = {}
        for m in InvoiceRetailPartMap.objects.all():
            if m.sale_part_number and m.company_name:
                part_to_company[m.sale_part_number] = m.company_name

        self.stdout.write(f"Found {len(part_to_company)} part->company mappings in InvoiceRetailPartMap")

        # Find invoices missing customer_name
        missing = Invoice.objects.filter(customer_name__isnull=True) | Invoice.objects.filter(customer_name='')
        total = missing.count()
        self.stdout.write(f"Found {total} invoices missing customer_name")

        if total == 0:
            self.stdout.write(self.style.SUCCESS("Nothing to backfill!"))
            return

        updated = 0
        skipped = 0

        for inv in missing:
            company = part_to_company.get(inv.part_number)
            if company:
                inv.customer_name = company
                inv.save(update_fields=['customer_name'])
                updated += 1
            else:
                skipped += 1
                self.stdout.write(
                    self.style.WARNING(f"  No mapping for Invoice #{inv.id} part={inv.part_number} code={inv.customer_code}")
                )

        self.stdout.write(self.style.SUCCESS(f"\nDone! Updated: {updated}, Skipped: {skipped}"))
