"""
Management command to auto-create InvoiceEntryConsumption records
for retail dispatch entries that are missing them.

Uses FIFO matching to link each dispatch to wholesale invoices.

NOTE: This command does NOT deduct qty from Invoice records, because
      the qty was already deducted (or was 0) when the original
      InvoiceEntry was created.  It only fills in the missing
      consumption metadata (fc_value, taxable_value, etc.).

Usage:
    python manage.py fix_missing_consumption          # dry-run
    python manage.py fix_missing_consumption --apply   # actually create records
"""

from django.core.management.base import BaseCommand
from decimal import Decimal
from sales.models import Invoice, InvoiceRetailPartMap, InvoiceEntryConsumption
from retail.models import InvoiceEntry


def _safe_decimal(value):
    if value is None:
        return Decimal('0')
    return Decimal(str(value))


class Command(BaseCommand):
    help = 'Auto-create missing InvoiceEntryConsumption records using FIFO matching'

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Actually create the records (default is dry-run)',
        )

    def handle(self, *args, **options):
        apply = options['apply']

        if not apply:
            self.stdout.write(self.style.WARNING(
                '=== DRY RUN === (use --apply to create records)\n'
            ))

        # Build retail part -> sale part mapping
        part_mapping = {}
        for pm in InvoiceRetailPartMap.objects.all():
            part_mapping[pm.retail_part_number] = pm.sale_part_number

        # Find entries without consumption
        missing = InvoiceEntry.objects.filter(
            consumptions__isnull=True
        ).order_by('date')

        self.stdout.write(f'Found {missing.count()} entries without consumption records\n')

        created_count = 0
        skipped_count = 0
        no_invoice_count = 0

        for entry in missing:
            retail_part = entry.part_number
            sale_part = part_mapping.get(retail_part, retail_part)

            # Find matching wholesale invoices (by sale part number, FIFO order)
            # We look at ALL invoices, not just those with qty > 0,
            # because qty may already have been decremented
            matching_invoices = Invoice.objects.filter(
                part_number=sale_part,
            ).order_by('date', 'id')

            if not matching_invoices.exists():
                self.stdout.write(self.style.WARNING(
                    f'  No Invoice found for Entry #{entry.id} '
                    f'part={retail_part} (sale={sale_part}) — SKIPPED'
                ))
                no_invoice_count += 1
                continue

            # Use the first matching invoice (FIFO) for the consumption record
            # Since we can't know which specific invoice was consumed,
            # we use the closest one by date (before or on the dispatch date)
            best_invoice = matching_invoices.filter(
                date__lte=entry.date
            ).order_by('-date', '-id').first()

            if not best_invoice:
                # Fallback: use the earliest invoice available
                best_invoice = matching_invoices.first()

            consumed_qty = Decimal(str(entry.qty))
            inv_dollar_rate = _safe_decimal(best_invoice.dollar_rate)
            inv_inr_rate = _safe_decimal(best_invoice.inr_rate)
            inv_conversion_rate = _safe_decimal(best_invoice.conversion_rate)
            dnd = _safe_decimal(best_invoice.dnd_charges)

            retail_dollar_rate = _safe_decimal(entry.usd_rate)
            conversion_rate = _safe_decimal(entry.conversion_rate)

            # Value calculations (same as bulk_upload.py)
            base_value = consumed_qty * retail_dollar_rate
            taxable_value = base_value - dnd
            fc_value = taxable_value

            # INR received vs cost
            inr_received = consumed_qty * retail_dollar_rate * conversion_rate
            inr_cost = consumed_qty * inv_dollar_rate * inv_conversion_rate

            # Profit decomposition
            profit_absolute = inr_received - inr_cost
            selling_profit_inr = (retail_dollar_rate - inv_dollar_rate) * consumed_qty * conversion_rate
            fx_profit = inv_dollar_rate * consumed_qty * (conversion_rate - inv_conversion_rate)
            profit_fx_only = profit_absolute - selling_profit_inr - fx_profit
            selling_profit_usd = (retail_dollar_rate - inv_dollar_rate) * consumed_qty

            self.stdout.write(
                f'  Entry #{entry.id}: part={retail_part}, qty={consumed_qty}, '
                f'date={entry.date} -> Invoice #{best_invoice.invoice_number} '
                f'(date={best_invoice.date})'
            )

            if apply:
                InvoiceEntryConsumption.objects.create(
                    invoice_entry=entry,
                    invoice=best_invoice,
                    consumed_qty=int(consumed_qty),
                    selling_price_inr=(inv_inr_rate * consumed_qty).quantize(Decimal('0.01')),
                    profit_absolute=profit_absolute.quantize(Decimal('0.01')),
                    profit_selling_rate=selling_profit_usd.quantize(Decimal('0.01')),
                    profit_fx_rate=fx_profit.quantize(Decimal('0.01')),
                    profit_fx_only=profit_fx_only.quantize(Decimal('0.01')),
                    base_value=base_value.quantize(Decimal('0.01')),
                    dnd_charges=dnd.quantize(Decimal('0.01')),
                    taxable_value=taxable_value.quantize(Decimal('0.01')),
                    fc_value=fc_value.quantize(Decimal('0.01')),
                    fc_rate_with_discount=(fc_value / consumed_qty).quantize(Decimal('0.01')) if consumed_qty else Decimal('0'),
                    rate_sale_from_wh_per_unit=(inv_inr_rate / inv_conversion_rate).quantize(Decimal('0.01')) if inv_conversion_rate else Decimal('0'),
                    rate_sale_from_wh=retail_dollar_rate,
                    diff=((inv_inr_rate / inv_conversion_rate) - retail_dollar_rate).quantize(Decimal('0.01')) if inv_conversion_rate else Decimal('0'),
                    surcharge=(((inv_inr_rate / inv_conversion_rate) - retail_dollar_rate) * consumed_qty * conversion_rate).quantize(Decimal('0.01')) if inv_conversion_rate else Decimal('0'),
                )
                created_count += 1
            else:
                created_count += 1  # count what would be created

        self.stdout.write('')
        if apply:
            self.stdout.write(self.style.SUCCESS(
                f'Done! Created: {created_count}, '
                f'Skipped (no invoice): {no_invoice_count}'
            ))
        else:
            self.stdout.write(self.style.WARNING(
                f'DRY RUN complete. Would create: {created_count}, '
                f'Would skip: {no_invoice_count}'
            ))
            self.stdout.write('Run with --apply to actually create records.')
