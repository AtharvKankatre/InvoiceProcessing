import os
import django
from django.core.management.base import BaseCommand
from decimal import Decimal

class Command(BaseCommand):
    help = 'Backfills the conversion_rate field for invoices where it is 0.0'

    def handle(self, *args, **kwargs):
        from sales.models import Invoice

        # Find invoices where conversion_rate is exactly 0
        invoices = Invoice.objects.filter(conversion_rate=0)
        total_found = invoices.count()
        
        self.stdout.write(self.style.WARNING(f"Found {total_found} invoices with a 0.0 conversion rate."))

        if total_found == 0:
            self.stdout.write(self.style.SUCCESS("All invoices already have a conversion rate. Nothing to do!"))
            return

        updated_count = 0

        for inv in invoices:
            # We need to make sure dollar_rate is not 0 to avoid division by zero errors
            if inv.dollar_rate and inv.dollar_rate > 0:
                # Calculate: conversion_rate = inr_rate / dollar_rate
                new_rate = inv.inr_rate / inv.dollar_rate
                
                # Round it to a reasonable number of decimal places (e.g., 4)
                # Some databases get mad if the floating point is infinitely long
                inv.conversion_rate = round(new_rate, 4)
                
                # Save ONLY the conversion_rate column
                inv.save(update_fields=['conversion_rate'])
                
                updated_count += 1
                self.stdout.write(f"Updated Invoice {inv.invoice_number}: INR ({inv.inr_rate}) / USD ({inv.dollar_rate}) = Rate ({inv.conversion_rate})")
            else:
                self.stdout.write(self.style.ERROR(f"Skipped Invoice {inv.invoice_number}: Dollar rate is 0, cannot calculate conversion."))

        self.stdout.write(self.style.SUCCESS(f"\nSuccessfully backfilled {updated_count} conversion rates!"))
