import os
import django
from django.core.management.base import BaseCommand
from django.db.models import Sum

class Command(BaseCommand):
    help = 'Backfills the new invoice_qty field for older invoices using historical consumption data'

    def handle(self, *args, **kwargs):
        from sales.models import Invoice, InvoiceEntryConsumption

        # 1. Find all invoices where invoice_qty is currently null (empty)
        invoices = Invoice.objects.filter(invoice_qty__isnull=True)
        total_found = invoices.count()
        
        self.stdout.write(self.style.WARNING(f"Found {total_found} old invoices missing their original invoice_qty."))

        if total_found == 0:
            self.stdout.write(self.style.SUCCESS("All invoices already have an invoice_qty. Nothing to do!"))
            return

        updated_count = 0

        for inv in invoices:
            # 2. Look up all the times this specific invoice was consumed/sold out of
            # and add up all those quantities.
            total_consumed_dict = InvoiceEntryConsumption.objects.filter(
                invoice=inv
            ).aggregate(total=Sum('consumed_qty'))
            
            # If it was never consumed, the sum is None, so we default to 0
            total_consumed = total_consumed_dict['total'] or 0

            # 3. Math: Original Quantity = What is sitting in stock right now + What was already sold
            original_qty = inv.qty + total_consumed

            # 4. Save *ONLY* the new invoice_qty field.
            # We explicitly tell Django to ONLY update the 'invoice_qty' column, 
            # so it is physically impossible to accidentally overwrite 'qty' or anything else.
            inv.invoice_qty = original_qty
            inv.save(update_fields=['invoice_qty'])
            
            updated_count += 1
            self.stdout.write(f"Updated Invoice {inv.invoice_number}: Remaining ({inv.qty}) + Consumed ({total_consumed}) = Original ({original_qty})")

        self.stdout.write(self.style.SUCCESS(f"\nSuccessfully backfilled {updated_count} invoices!"))
