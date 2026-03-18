from datetime import datetime, date
from decimal import Decimal
from django.db.models import Sum, F, DecimalField, Value, Q
from django.db.models.functions import Coalesce, NullIf
from sales.models import Invoice, InvoiceRetailPartMap, InvoiceEntryConsumption
from retail.models import InvoiceEntry

class StockLedgerService:

    @staticmethod
    def _get_hybrid_outgoing(entry_qs, consumption_cutoff_date=None):
        """
        Calculate outgoing qty/fc/inr using entry-based values (usd_total, inr_total)
        to match Part History export. Uses consumption records only for qty tracking
        and cutoff-date filtering (opening balance calculations).
        Plating charges are subtracted from FC/INR to reflect actual part values.
        Returns (total_qty, total_fc, total_inr).
        """
        total_qty = 0
        total_fc = Decimal(0)
        total_inr = Decimal(0)

        for entry in entry_qs:
            plating = entry.plating_charges or Decimal(0)
            entry_conv = entry.conversion_rate or Decimal(0)
            entry_qty = 0

            cons = entry.consumptions.all()
            if cons.exists() and consumption_cutoff_date:
                # Opening balance: need to filter by cutoff date
                # Use consumption qty for filtering, but entry FC/INR (prorated)
                total_entry_consumed_qty = sum(c.consumed_qty or 0 for c in cons)
                valid_consumed_qty = 0

                for c in cons:
                    if c.invoice.date >= consumption_cutoff_date:
                        continue
                    cq = c.consumed_qty or 0
                    valid_consumed_qty += cq
                    entry_qty += cq

                # Prorate entry FC/INR based on valid consumption ratio
                if total_entry_consumed_qty > 0 and valid_consumed_qty > 0:
                    entry_fc = entry.usd_total or Decimal(0)
                    entry_inr = entry.inr_total or Decimal(0)
                    ratio = Decimal(str(valid_consumed_qty)) / Decimal(str(total_entry_consumed_qty))
                    total_fc += round(entry_fc * ratio, 2)
                    total_inr += round(entry_inr * ratio, 2)
                elif total_entry_consumed_qty > 0 and valid_consumed_qty == 0:
                    # ALL consumptions are after the cutoff date, but the entry
                    # itself shipped before the period. Fall back to entry values
                    # so its outgoing value is not silently dropped.
                    entry_qty = entry.qty or 0
                    total_fc += round(entry.usd_total or Decimal(0), 2)
                    total_inr += round(entry.inr_total or Decimal(0), 2)
            else:
                # Period calculation or no consumption: use entry values directly
                entry_qty = entry.qty or 0
                total_fc += round(entry.usd_total or Decimal(0), 2)
                total_inr += round(entry.inr_total or Decimal(0), 2)

            total_qty += entry_qty

            # Subtract plating from FC/INR (plating is a service, not stock)
            if plating and entry_qty > 0:
                total_fc -= round(plating * entry_qty, 2)
                total_inr -= round(plating * entry_conv * entry_qty, 2)

        return total_qty, round(total_fc, 2), round(total_inr, 2)

    @staticmethod
    def _get_cost_adjustments(entry_qs):
        """
        Calculate total surcharge and exchange gain for outgoing entries.
        Surcharge = FC rate difference between incoming and selling rates.
        Exchange Gain = exchange rate difference between incoming and selling.
        Returns (surcharge_fc, surcharge_inr, exchange_gain_inr).
        """
        surcharge_fc = Decimal(0)
        surcharge_inr = Decimal(0)
        exchange_gain_inr = Decimal(0)

        entry_ids = [e.id for e in entry_qs]
        if not entry_ids:
            return surcharge_fc, surcharge_inr, exchange_gain_inr

        consumptions = InvoiceEntryConsumption.objects.filter(
            invoice_entry_id__in=entry_ids
        ).select_related('invoice', 'invoice_entry')

        for c in consumptions:
            inv = c.invoice              # Incoming (warehouse) invoice
            
            entry = c.invoice_entry      # Outgoing (retail) entry
            consumed_qty = c.consumed_qty or 0

            # Round to 2 decimal places to prevent micro-discrepancies between
            # Sap's 15-decimal precision and the user's manual 2-decimal Excel entry
            inv_dollar_rate = round(inv.dollar_rate or Decimal(0), 2)
            entry_usd_rate = round(entry.usd_rate or Decimal(0), 2)
            plating = round(entry.plating_charges or Decimal(0), 2)
            adjusted_usd_rate = entry_usd_rate - plating

            inv_conversion_rate = round(inv.conversion_rate or Decimal(0), 2)
            entry_conversion_rate = round(entry.conversion_rate or Decimal(0), 2)

            # To ensure the closing balance cancels out EXACTLY, we must ensure:
            # entry_inr + surcharge_inr + exchange_gain_inr == incoming_inr
            # So we calculate the exact raw difference from the original totals
            inv_qty = inv.invoice_qty or inv.qty or 0
            if inv_qty > 0 and consumed_qty > 0:
                ratio = Decimal(str(consumed_qty)) / Decimal(str(inv_qty))
                exact_incoming_inr = round((inv.inr_total or Decimal(0)) * ratio, 2)
                raw_entry_inr = round((entry.inr_total or Decimal(0)) * Decimal(str(consumed_qty)) / Decimal(str(entry.qty or consumed_qty)), 2)
                plating_inr = round(plating * entry_conversion_rate * consumed_qty, 2)
                exact_entry_inr = raw_entry_inr - plating_inr
                
                # Surcharge FC = (incoming FC rate - adjusted selling FC rate) * qty
                s_fc = (inv_dollar_rate - adjusted_usd_rate) * consumed_qty
                surcharge_fc += s_fc
                
                # If rates are perfectly matched (bill-to-bill), force surcharge and exchange to absorb the exact rounding diff
                if s_fc == 0 and inv_conversion_rate == entry_conversion_rate:
                    surcharge_inr += Decimal(0)
                    exchange_gain_inr += (exact_incoming_inr - exact_entry_inr)
                else:
                    # Regular calculation
                    calc_surcharge_inr = Decimal(str(round(s_fc * inv_conversion_rate, 2)))
                    calc_exchange_inr = Decimal(str(round((inv_conversion_rate - entry_conversion_rate) * consumed_qty * adjusted_usd_rate, 2)))
                    
                    surcharge_inr += calc_surcharge_inr
                    exchange_gain_inr += calc_exchange_inr

        return surcharge_fc, surcharge_inr, exchange_gain_inr

    @staticmethod
    def get_ledger_data(from_date=None, to_date=None):
        """
        Generates stock ledger data grouped by Customer/Party.
        Returns a list of dictionaries suitable for the Excel report.
        """
        
        # 1. Identify distinct parties from BOTH sources.
        # Build a name → code dict, preferring the non-empty code.
        # This prevents duplicate rows when the same party appears in
        # Invoice (with code) AND InvoiceRetailPartMap (without code).

        party_code_map = {}  # name → best code

        for c in Invoice.objects.values('customer_name', 'customer_code').distinct():
            name = c['customer_name'] or "Cooper"
            code = c['customer_code'] or ""
            # Prefer non-empty code
            if name not in party_code_map or (not party_code_map[name] and code):
                party_code_map[name] = code

        for c in InvoiceRetailPartMap.objects.values('company_name', 'customer_code').distinct():
            name = c['company_name']
            code = c['customer_code'] or ""
            if name not in party_code_map or (not party_code_map[name] and code):
                party_code_map[name] = code

        # Final deduplicated list: one row per party name
        parties = [(name, code) for name, code in party_code_map.items()]
            
        report_data = []

        # Convert simple date filters to dates
        start_date = None
        end_date = None
        if from_date:
            if isinstance(from_date, str):
                start_date = datetime.strptime(from_date, "%d-%m-%Y").date()
            else:
                start_date = from_date
        
        if to_date:
            if isinstance(to_date, str):
                end_date = datetime.strptime(to_date, "%d-%m-%Y").date()
            else:
                end_date = to_date


        # 2. Iterate through each party and calculate metrics
        for party_name, party_code in parties:
            
            # --- OPENING BALANCE ---
            # Calculate total transactions BEFORE start_date
            opening_qty = 0
            opening_fc_val = Decimal(0)
            opening_inr_val = Decimal(0)
            
            if start_date:
                # Incoming (Add)
                incoming_opening = Invoice.objects.filter(
                    customer_name=party_name,
                    date__lt=start_date
                ).aggregate(
                    total_qty=Coalesce(Sum(Coalesce(NullIf(F('invoice_qty'), Value(0)), F('qty'))), 0),
                    total_fc=Coalesce(Sum('dollar_total'), Decimal(0), output_field=DecimalField()),
                    total_inr=Coalesce(Sum('inr_total'), Decimal(0), output_field=DecimalField())
                )
                
                # Outgoing (Subtract) — hybrid: prefer consumption data
                mappings = InvoiceRetailPartMap.objects.filter(company_name=party_name)
                all_parts = list(set(
                    list(mappings.values_list('retail_part_number', flat=True)) +
                    [p for p in mappings.values_list('sale_part_number', flat=True) if p]
                ))
                out_entries = InvoiceEntry.objects.filter(
                    part_number__in=all_parts,
                    date__lt=start_date
                ).prefetch_related('consumptions', 'consumptions__invoice')
                out_qty, out_fc, out_inr = StockLedgerService._get_hybrid_outgoing(out_entries, consumption_cutoff_date=start_date)
                
                # Subtract surcharge and exchange gain from opening balance
                open_surcharge_fc, open_surcharge_inr, open_exchange_inr = StockLedgerService._get_cost_adjustments(out_entries)
                
                # Net Opening
                opening_qty = (incoming_opening['total_qty'] or 0) - out_qty
                opening_fc_val = (incoming_opening['total_fc'] or Decimal(0)) - out_fc - open_surcharge_fc
                opening_inr_val = (incoming_opening['total_inr'] or Decimal(0)) - out_inr - open_surcharge_inr - open_exchange_inr

            # --- PERIOD TRANSACTIONS ---
            # Filter by date range (inclusive)
            date_filter = {}
            if start_date:
                date_filter['date__gte'] = start_date
            if end_date:
                date_filter['date__lte'] = end_date

            # Incoming (Shipment to WH)
            incoming_period = Invoice.objects.filter(
                customer_name=party_name,
                **date_filter
            ).aggregate(
                total_qty=Coalesce(Sum(Coalesce(NullIf(F('invoice_qty'), Value(0)), F('qty'))), 0),
                total_fc=Coalesce(Sum('dollar_total'), Decimal(0), output_field=DecimalField()),
                total_inr=Coalesce(Sum('inr_total'), Decimal(0), output_field=DecimalField())
            )

            # Outgoing (Despatch to Customer) — hybrid: prefer consumption data
            mappings = InvoiceRetailPartMap.objects.filter(company_name=party_name)
            all_parts = list(set(
                list(mappings.values_list('retail_part_number', flat=True)) +
                [p for p in mappings.values_list('sale_part_number', flat=True) if p]
            ))
            
            outgoing_period_filter = {
                'part_number__in': all_parts
            }
            if start_date:
                outgoing_period_filter['date__gte'] = start_date
            if end_date:
                outgoing_period_filter['date__lte'] = end_date
                
            out_entries = InvoiceEntry.objects.filter(
                **outgoing_period_filter
            ).prefetch_related('consumptions', 'consumptions__invoice')
            out_qty, out_fc, out_inr = StockLedgerService._get_hybrid_outgoing(out_entries)

            # Get surcharge and exchange gain for outgoing entries
            surcharge_fc, surcharge_inr, exchange_gain_inr = StockLedgerService._get_cost_adjustments(out_entries)

            # Extract values safely
            inc_qty = incoming_period['total_qty'] or 0
            inc_fc = incoming_period['total_fc'] or Decimal(0)
            inc_inr = incoming_period['total_inr'] or Decimal(0)

            # --- CLOSING BALANCE ---
            closing_qty = opening_qty + inc_qty - out_qty
            closing_fc_val = opening_fc_val + inc_fc - out_fc - surcharge_fc
            closing_inr_val = opening_inr_val + inc_inr - out_inr - surcharge_inr - exchange_gain_inr


            # Only add to report if there is ANY activity or non-zero balance
            has_activity = (
                opening_qty != 0 or 
                inc_qty > 0 or 
                out_qty > 0 or
                closing_qty != 0
            )

            if has_activity:
                report_data.append({
                    "Code No. Stock AC": party_code,
                    "Party Name": party_name,
                    "Opening Stock Qty": opening_qty,
                    "Opening Stock FC Value": round(float(opening_fc_val), 2),
                    "Opening Stock INR Value": round(float(opening_inr_val), 2),
                    
                    "Shipment to WH (Add) Qty": inc_qty,
                    "Shipment to WH (Add) FC": round(float(inc_fc), 2),
                    "Shipment to WH (Add) INR": round(float(inc_inr), 2),
                    
                    "Despatch (Less) Qty": out_qty,
                    "Despatch (Less) FC": round(float(out_fc), 2),
                    "Despatch (Less) INR": round(float(out_inr), 2),
                    
                    "Closing Stock Qty": closing_qty,
                    "Closing Stock FC Value": round(float(closing_fc_val), 2),
                    "Closing Stock INR Value": round(float(closing_inr_val), 2),
                })

        return report_data
        
    @staticmethod
    def get_detailed_consumption_data(from_date=None, to_date=None):
        """
        Generates detailed consumption data grouped by customer.
        Each customer group includes:
          - Opening stock (qty, FC, INR)
          - Shipment in period (qty, FC, INR)
          - Individual consumption rows
          - Despatch subtotals
          - Closing stock
        Returns a list of dicts with a '_row_type' key for Excel rendering.
        """
        # Convert date params
        start_date = None
        end_date = None
        if from_date:
            if isinstance(from_date, str):
                start_date = datetime.strptime(from_date, "%d-%m-%Y").date()
            else:
                start_date = from_date
        if to_date:
            if isinstance(to_date, str):
                end_date = datetime.strptime(to_date, "%d-%m-%Y").date()
            else:
                end_date = to_date

        date_filter = {}
        if start_date:
            date_filter['date__gte'] = start_date
        if end_date:
            date_filter['date__lte'] = end_date

        # Build party name → code mapping
        party_code_map = {}
        for c in Invoice.objects.values('customer_name', 'customer_code').distinct():
            name = c['customer_name'] or "Cooper"
            code = c['customer_code'] or ""
            if name not in party_code_map or (not party_code_map[name] and code):
                party_code_map[name] = code
        for c in InvoiceRetailPartMap.objects.values('company_name', 'customer_code').distinct():
            name = c['company_name']
            code = c['customer_code'] or ""
            if name not in party_code_map or (not party_code_map[name] and code):
                party_code_map[name] = code

        # Build part → company mapping (include BOTH retail and sale part numbers)
        retail_to_company = {}
        for pm in InvoiceRetailPartMap.objects.all():
            retail_to_company[pm.retail_part_number] = pm.company_name
            if pm.sale_part_number:
                retail_to_company[pm.sale_part_number] = pm.company_name

        # Get all entries in period with consumptions prefetched
        entries = InvoiceEntry.objects.filter(**date_filter).prefetch_related('consumptions', 'consumptions__invoice').order_by('date')

        # Group entries by company
        company_entries = {}
        for entry in entries:
            company = retail_to_company.get(entry.part_number, "Unknown")
            if company not in company_entries:
                company_entries[company] = []
            company_entries[company].append(entry)

        # Also include companies that have Invoices (incoming) but no outgoing in period
        all_parties = set(party_code_map.keys()) | set(company_entries.keys())

        result_rows = []

        for party_name in sorted(all_parties):
            party_code = party_code_map.get(party_name, "")
            entries_list = company_entries.get(party_name, [])

            # --- Calculate Opening Stock ---
            opening_qty = 0
            opening_fc = Decimal(0)
            opening_inr = Decimal(0)

            if start_date:
                inc_open = Invoice.objects.filter(
                    customer_name=party_name, date__lt=start_date
                ).aggregate(
                    qty=Coalesce(Sum(Coalesce(NullIf(F('invoice_qty'), Value(0)), F('qty'))), 0),
                    fc=Coalesce(Sum('dollar_total'), Decimal(0), output_field=DecimalField()),
                    inr=Coalesce(Sum('inr_total'), Decimal(0), output_field=DecimalField()),
                )
                mappings = InvoiceRetailPartMap.objects.filter(
                    company_name=party_name
                )
                all_parts = list(set(
                    list(mappings.values_list('retail_part_number', flat=True)) +
                    [p for p in mappings.values_list('sale_part_number', flat=True) if p]
                ))
                out_entries = InvoiceEntry.objects.filter(
                    part_number__in=all_parts, date__lt=start_date
                ).prefetch_related('consumptions', 'consumptions__invoice')
                out_qty, out_fc, out_inr = StockLedgerService._get_hybrid_outgoing(out_entries, consumption_cutoff_date=start_date)
                
                # Subtract surcharge and exchange gain from opening balance
                open_surcharge_fc, open_surcharge_inr, open_exchange_inr = StockLedgerService._get_cost_adjustments(out_entries)
                
                opening_qty = (inc_open['qty'] or 0) - out_qty
                opening_fc = (inc_open['fc'] or Decimal(0)) - out_fc - open_surcharge_fc
                opening_inr = (inc_open['inr'] or Decimal(0)) - out_inr - open_surcharge_inr - open_exchange_inr

            # --- Calculate Shipment (Incoming) in period ---
            inc_filter = {'customer_name': party_name}
            if start_date:
                inc_filter['date__gte'] = start_date
            if end_date:
                inc_filter['date__lte'] = end_date

            inc_period = Invoice.objects.filter(**inc_filter).aggregate(
                qty=Coalesce(Sum(Coalesce(NullIf(F('invoice_qty'), Value(0)), F('qty'))), 0),
                fc=Coalesce(Sum('dollar_total'), Decimal(0), output_field=DecimalField()),
                inr=Coalesce(Sum('inr_total'), Decimal(0), output_field=DecimalField()),
            )
            ship_qty = inc_period['qty'] or 0
            ship_fc = inc_period['fc'] or Decimal(0)
            ship_inr = inc_period['inr'] or Decimal(0)

            # --- Despatch totals from individual entries (hybrid) ---
            desp_qty, desp_fc, desp_inr = StockLedgerService._get_hybrid_outgoing(entries_list)
            
            # Get surcharge and exchange gain for outgoing entries
            surcharge_fc, surcharge_inr, exchange_gain_inr = StockLedgerService._get_cost_adjustments(entries_list)

            # --- Closing Stock ---
            closing_qty = opening_qty + ship_qty - desp_qty
            closing_fc = opening_fc + ship_fc - desp_fc - surcharge_fc
            closing_inr = opening_inr + ship_inr - desp_inr - surcharge_inr - exchange_gain_inr

            # Skip customers with zero activity
            has_activity = (opening_qty != 0 or ship_qty > 0 or desp_qty > 0 or closing_qty != 0)
            if not has_activity:
                continue

            # --- CUSTOMER HEADER ROW ---
            result_rows.append({
                '_row_type': 'customer_header',
                'Code No. Stock AC': party_code,
                'Party Name': party_name,
                'Part Number': '',
                'Qty': '',
                'FC Value': '',
                'INR Value': '',
                'Date': '',
                'Opening Qty': opening_qty,
                'Opening FC': round(float(opening_fc), 2),
                'Opening INR': round(float(opening_inr), 2),
                'Shipment Qty': ship_qty,
                'Shipment FC': round(float(ship_fc), 2),
                'Shipment INR': round(float(ship_inr), 2),
                'Closing Qty': closing_qty,
                'Closing FC': round(float(closing_fc), 2),
                'Closing INR': round(float(closing_inr), 2),
            })

            # --- SUB-GROUP ENTRIES BY PART NUMBER ---
            from collections import OrderedDict
            part_groups = OrderedDict()
            sorted_entries = sorted(entries_list, key=lambda e: (e.part_number or '', e.date or ''))
            for entry in sorted_entries:
                pn = entry.part_number or 'Unknown'
                if pn not in part_groups:
                    part_groups[pn] = []
                part_groups[pn].append(entry)

            has_multiple_parts = len(part_groups) > 1

            for part_number, part_entries in part_groups.items():
                # --- INDIVIDUAL TRANSACTION ROWS ---
                for entry in part_entries:
                    # Use consumption data if available
                    cons = entry.consumptions.all()
                    plating = entry.plating_charges or Decimal(0)
                    entry_conv = entry.conversion_rate or Decimal(0)
                    if cons.exists():
                        entry_qty = sum(c.consumed_qty or 0 for c in cons)
                        entry_fc = float(entry.usd_total or 0)
                        entry_inr = float(entry.inr_total or 0)
                    else:
                        entry_qty = entry.qty
                        entry_fc = float(entry.usd_total or 0)
                        entry_inr = float(entry.inr_total or 0)
                    # Subtract plating from FC/INR
                    if plating:
                        entry_fc -= float(plating * entry_qty)
                        entry_inr -= float(plating * entry_conv * entry_qty)
                    
                    result_rows.append({
                        '_row_type': 'detail',
                        'Code No. Stock AC': party_code,
                        'Party Name': party_name,
                        'Part Number': entry.part_number,
                        'Qty': entry_qty,
                        'FC Value': round(entry_fc, 2),
                        'INR Value': round(entry_inr, 2),
                        'Date': entry.date.strftime("%d-%m-%Y") if entry.date else "",
                        'Opening Qty': '',
                        'Opening FC': '',
                        'Opening INR': '',
                        'Shipment Qty': '',
                        'Shipment FC': '',
                        'Shipment INR': '',
                        'Closing Qty': '',
                        'Closing FC': '',
                        'Closing INR': '',
                    })

                # --- PART SUBTOTAL ROW (always show) ---
                part_qty, part_fc_dec, part_inr_dec = StockLedgerService._get_hybrid_outgoing(part_entries)
                result_rows.append({
                    '_row_type': 'part_subtotal',
                    'Code No. Stock AC': '',
                    'Party Name': '',
                    'Part Number': f'{part_number} — Total',
                    'Qty': part_qty,
                    'FC Value': round(float(part_fc_dec), 2),
                    'INR Value': round(float(part_inr_dec), 2),
                    'Date': '',
                    'Opening Qty': '',
                    'Opening FC': '',
                    'Opening INR': '',
                    'Shipment Qty': '',
                    'Shipment FC': '',
                    'Shipment INR': '',
                    'Closing Qty': '',
                    'Closing FC': '',
                    'Closing INR': '',
                })

            # --- CUSTOMER SUBTOTAL ROW ---
            result_rows.append({
                '_row_type': 'subtotal',
                'Code No. Stock AC': '',
                'Party Name': f'{party_name} — Despatch Total',
                'Part Number': '',
                'Qty': desp_qty,
                'FC Value': round(float(desp_fc), 2),
                'INR Value': round(float(desp_inr), 2),
                'Date': '',
                'Opening Qty': '',
                'Opening FC': '',
                'Opening INR': '',
                'Shipment Qty': '',
                'Shipment FC': '',
                'Shipment INR': '',
                'Closing Qty': closing_qty,
                'Closing FC': round(float(closing_fc), 2),
                'Closing INR': round(float(closing_inr), 2),
            })

        return result_rows

    @staticmethod
    def get_partwise_consumption_data(from_date=None, to_date=None):
        """
        Generates consumption data grouped by PART -> CUSTOMER.
        Shows where each part was consumed by which customer, providing 
        a subtotal per customer and a grand total per part.
        """
        from django.db.models import Sum, DecimalField
        from django.db.models.functions import Coalesce
        from decimal import Decimal
        from datetime import datetime
        
        start_date = None
        end_date = None
        if from_date:
            if isinstance(from_date, str):
                start_date = datetime.strptime(from_date, "%d-%m-%Y").date()
            else:
                start_date = from_date
        if to_date:
            if isinstance(to_date, str):
                end_date = datetime.strptime(to_date, "%d-%m-%Y").date()
            else:
                end_date = to_date

        date_filter = {}
        if start_date:
            date_filter['date__gte'] = start_date
        if end_date:
            date_filter['date__lte'] = end_date

        retail_to_company = {}
        retail_to_sale_part = {}  # retail_part_number -> sale_part_number
        company_to_code = {}
        for pm in InvoiceRetailPartMap.objects.all():
            retail_to_company[pm.retail_part_number] = pm.company_name
            if pm.sale_part_number:
                retail_to_sale_part[pm.retail_part_number] = pm.sale_part_number
                
                # Also map the sale part number to the company in case Cooper uploads the sale part 
                # instead of the retail part in the outgoing invoices
                if pm.sale_part_number not in retail_to_company:
                    retail_to_company[pm.sale_part_number] = pm.company_name
                # And map sale part to itself to safely resolve canonical names
                if pm.sale_part_number not in retail_to_sale_part:
                    retail_to_sale_part[pm.sale_part_number] = pm.sale_part_number
                
            if pm.customer_code:
                company_to_code[pm.company_name] = pm.customer_code
                
        for c in Invoice.objects.values('customer_name', 'customer_code').distinct():
            name = c['customer_name'] or "Cooper"
            if name not in company_to_code and c['customer_code']:
                company_to_code[name] = c['customer_code']

        entries = InvoiceEntry.objects.filter(**date_filter).prefetch_related('consumptions', 'consumptions__invoice').order_by('date')
        
        inc_filter = {}
        if start_date:
            inc_filter['date__gte'] = start_date
        if end_date:
            inc_filter['date__lte'] = end_date
        incoming_invoices = Invoice.objects.filter(**inc_filter)
        
        all_parts = set()
        for e in entries:
            # Translate retail part number to sale/wholesale part number
            canonical = retail_to_sale_part.get(e.part_number, e.part_number)
            all_parts.add(canonical)
        for i in incoming_invoices:
            all_parts.add(i.part_number)
            
        opening_inc = {}
        opening_out = {}
        opening_adj = {}  # surcharge/exchange adjustments per (part, customer)
        if start_date:
            prev_inc = Invoice.objects.filter(date__lt=start_date).values('part_number', 'customer_name').annotate(
                qty=Coalesce(Sum(Coalesce(NullIf(F('invoice_qty'), Value(0)), F('qty'))), 0),
                fc=Coalesce(Sum('dollar_total'), Decimal(0), output_field=DecimalField()),
                inr=Coalesce(Sum('inr_total'), Decimal(0), output_field=DecimalField())
            )
            for p in prev_inc:
                part = p['part_number']
                cust = p['customer_name'] or "Cooper"
                opening_inc[(part, cust)] = p
                all_parts.add(part)
                
            # Opening outgoing — use the SAME helpers as Sheet 1 (get_ledger_data)
            # Group pre-period entries by (canonical_part, customer)
            prev_out_entries = InvoiceEntry.objects.filter(date__lt=start_date).prefetch_related('consumptions', 'consumptions__invoice')
            grouped_entries = {}
            for entry in prev_out_entries:
                retail_part = entry.part_number
                canonical = retail_to_sale_part.get(retail_part, retail_part)
                cust = retail_to_company.get(retail_part, "Unknown")
                if (canonical, cust) not in grouped_entries:
                    grouped_entries[(canonical, cust)] = []
                grouped_entries[(canonical, cust)].append(entry)
                all_parts.add(canonical)
            
            # Calculate opening outgoing and adjustments using the SAME helpers as Sheet 1
            for (part, cust), entries_list in grouped_entries.items():
                out_qty, out_fc, out_inr = StockLedgerService._get_hybrid_outgoing(
                    entries_list, consumption_cutoff_date=start_date
                )
                opening_out[(part, cust)] = {'qty': out_qty, 'fc': out_fc, 'inr': out_inr}
                
                s_fc, s_inr, e_inr = StockLedgerService._get_cost_adjustments(entries_list)
                opening_adj[(part, cust)] = {'s_fc': s_fc, 's_inr': s_inr, 'e_inr': e_inr}

        period_inc = {}
        period_inc_qs = Invoice.objects.filter(**inc_filter).values('part_number', 'customer_name').annotate(
            qty=Coalesce(Sum(Coalesce(NullIf(F('invoice_qty'), Value(0)), F('qty'))), 0),
            fc=Coalesce(Sum('dollar_total'), Decimal(0), output_field=DecimalField()),
            inr=Coalesce(Sum('inr_total'), Decimal(0), output_field=DecimalField())
        )
        for p in period_inc_qs:
            part = p['part_number']
            cust = p['customer_name'] or "Cooper"
            if (part, cust) not in period_inc:
                period_inc[(part, cust)] = {'qty': 0, 'fc': Decimal(0), 'inr': Decimal(0)}
            period_inc[(part, cust)]['qty'] += p['qty']
            period_inc[(part, cust)]['fc'] += p['fc']
            period_inc[(part, cust)]['inr'] += p['inr']
            
        period_out_entries = {}
        for e in entries:
            retail_part = e.part_number
            canonical = retail_to_sale_part.get(retail_part, retail_part)
            cust = retail_to_company.get(retail_part, "Unknown")
            if (canonical, cust) not in period_out_entries:
                period_out_entries[(canonical, cust)] = []
            period_out_entries[(canonical, cust)].append(e)

        result_rows = []
        
        for part in sorted(list(all_parts)):
            customers_for_part = set()
            for (p, c) in opening_inc.keys():
                if p == part: customers_for_part.add(c)
            for (p, c) in opening_out.keys():
                if p == part: customers_for_part.add(c)
            for (p, c) in period_inc.keys():
                if p == part: customers_for_part.add(c)
            for (p, c) in period_out_entries.keys():
                if p == part: customers_for_part.add(c)
                
            if not customers_for_part:
                continue
                
            part_grand_desp_qty = 0
            part_grand_desp_fc = Decimal(0)
            part_grand_desp_inr = Decimal(0)
            part_grand_open_qty = 0
            part_grand_open_fc = Decimal(0)
            part_grand_open_inr = Decimal(0)
            part_grand_ship_qty = 0
            part_grand_ship_fc = Decimal(0)
            part_grand_ship_inr = Decimal(0)
            part_grand_close_qty = 0
            part_grand_close_fc = Decimal(0)
            part_grand_close_inr = Decimal(0)
            part_first_cust_code = ''
            part_first_cust_name = ''
            
            result_rows.append({
                '_row_type': 'part_header',
                'Code No. Stock AC': '',
                'Party Name': '',
                'Part Number': f'{part}',
                'Invoice No.': '',
                'Invoice Date': '',
                'Qty': '', 'FC Value': '', 'INR Value': '', 'Date': '',
                'Opening Qty': '', 'Opening FC': '', 'Opening INR': '',
                'Shipment Qty': '', 'Shipment FC': '', 'Shipment INR': '',
                'Closing Qty': '', 'Closing FC': '', 'Closing INR': '',
            })
            
            for cust in sorted(list(customers_for_part)):
                o_inc = opening_inc.get((part, cust), {'qty': 0, 'fc': Decimal(0), 'inr': Decimal(0)})
                o_out = opening_out.get((part, cust), {'qty': 0, 'fc': Decimal(0), 'inr': Decimal(0)})
                
                open_qty = (o_inc['qty'] or 0) - (o_out['qty'] or 0)
                o_adj = opening_adj.get((part, cust), {'s_fc': Decimal(0), 's_inr': Decimal(0), 'e_inr': Decimal(0)})
                open_fc = (o_inc['fc'] or Decimal(0)) - (o_out['fc'] or Decimal(0)) - o_adj['s_fc']
                open_inr = (o_inc['inr'] or Decimal(0)) - (o_out['inr'] or Decimal(0)) - o_adj['s_inr'] - o_adj['e_inr']
                
                p_inc = period_inc.get((part, cust), {'qty': 0, 'fc': Decimal(0), 'inr': Decimal(0)})
                ship_qty = p_inc['qty'] or 0
                ship_fc = p_inc['fc'] or Decimal(0)
                ship_inr = p_inc['inr'] or Decimal(0)
                
                cust_entries = period_out_entries.get((part, cust), [])
                
                desp_qty, desp_fc, desp_inr = StockLedgerService._get_hybrid_outgoing(cust_entries)
                
                # Get surcharge and exchange gain to adjust closing values
                surcharge_fc, surcharge_inr, exchange_gain_inr = StockLedgerService._get_cost_adjustments(cust_entries)
                
                part_grand_desp_qty += desp_qty
                part_grand_desp_fc += desp_fc
                part_grand_desp_inr += desp_inr
                
                close_qty = open_qty + ship_qty - desp_qty
                close_fc = open_fc + ship_fc - desp_fc - surcharge_fc
                close_inr = open_inr + ship_inr - desp_inr - surcharge_inr - exchange_gain_inr

                # Accumulate for Grand Total
                part_grand_open_qty += open_qty
                part_grand_open_fc += open_fc
                part_grand_open_inr += open_inr
                part_grand_ship_qty += ship_qty
                part_grand_ship_fc += ship_fc
                part_grand_ship_inr += ship_inr
                part_grand_close_qty += close_qty
                part_grand_close_fc += close_fc
                part_grand_close_inr += close_inr
                
                has_activity = (open_qty != 0 or ship_qty > 0 or desp_qty > 0 or close_qty != 0)
                if not has_activity:
                    continue
                
                cust_code = company_to_code.get(cust, '')

                # Track first customer code/name for Grand Total row
                if not part_first_cust_code and cust_code:
                    part_first_cust_code = cust_code
                if not part_first_cust_name and cust:
                    part_first_cust_name = cust
                
                # We skip individual 'detail' transaction rows to make this a clean summary sheet
                
                if start_date:
                    open_qty_val = open_qty
                    open_fc_val = round(float(open_fc), 2)
                    open_inr_val = round(float(open_inr), 2)
                else:
                    open_qty_val = ''
                    open_fc_val = ''
                    open_inr_val = ''

                result_rows.append({
                    '_row_type': 'customer_subtotal',
                    'Code No. Stock AC': cust_code,
                    'Party Name': f'{cust} — Subtotal',
                    'Part Number': '',
                    'Invoice No.': '',
                    'Invoice Date': '',
                    'Qty': desp_qty,
                    'FC Value': round(float(desp_fc), 2),
                    'INR Value': round(float(desp_inr), 2),
                    'Date': '',
                    'Opening Qty': open_qty_val,
                    'Opening FC': open_fc_val,
                    'Opening INR': open_inr_val,
                    'Shipment Qty': ship_qty,
                    'Shipment FC': round(float(ship_fc), 2),
                    'Shipment INR': round(float(ship_inr), 2),
                    'Closing Qty': close_qty,
                    'Closing FC': round(float(close_fc), 2),
                    'Closing INR': round(float(close_inr), 2),
                })

                # --- INVOICE-LEVEL CLOSING BREAKDOWN ---
                # For each sales invoice of this (part, customer), calculate
                # remaining stock = invoice_qty - sum(consumed_qty).
                # Only show invoices that still have remaining stock.
                inv_filter = {'part_number': part, 'customer_name': cust}
                if end_date:
                    inv_filter['date__lte'] = end_date

                invoices_for_part_cust = Invoice.objects.filter(
                    **inv_filter
                ).order_by('date')

                for inv in invoices_for_part_cust:
                    inv_qty = inv.invoice_qty if inv.invoice_qty is not None else (inv.qty or 0)
                    total_consumed = InvoiceEntryConsumption.objects.filter(
                        invoice=inv
                    ).aggregate(
                        total=Coalesce(Sum('consumed_qty'), 0)
                    )['total']
                    remaining_qty = inv_qty - total_consumed

                    if remaining_qty != 0:
                        # Calculate closing FC and INR for this invoice
                        # FC per unit = invoice dollar_rate
                        # INR per unit = invoice inr_rate
                        inv_closing_fc = float(remaining_qty * (inv.dollar_rate or Decimal(0)))
                        inv_closing_inr = float(remaining_qty * (inv.inr_rate or Decimal(0)))

                        result_rows.append({
                            '_row_type': 'invoice_detail',
                            'Code No. Stock AC': '',
                            'Party Name': cust,
                            'Part Number': part,
                            'Invoice No.': inv.invoice_number,
                            'Invoice Date': inv.date.strftime("%d-%m-%Y") if inv.date else '',
                            'Invoice Qty': inv_qty,
                            'Qty': '',
                            'FC Value': '',
                            'INR Value': '',
                            'Date': '',
                            'Opening Qty': '',
                            'Opening FC': '',
                            'Opening INR': '',
                            'Shipment Qty': '',
                            'Shipment FC': '',
                            'Shipment INR': '',
                            'Closing Qty': remaining_qty,
                            'Closing FC': round(inv_closing_fc, 2),
                            'Closing INR': round(inv_closing_inr, 2),
                        })

            # Determine Opening values for Grand Total
            if start_date:
                gt_open_qty = part_grand_open_qty
                gt_open_fc = round(float(part_grand_open_fc), 2)
                gt_open_inr = round(float(part_grand_open_inr), 2)
            else:
                gt_open_qty = ''
                gt_open_fc = ''
                gt_open_inr = ''

            result_rows.append({
                '_row_type': 'part_grand_total',
                'Code No. Stock AC': part_first_cust_code,
                'Party Name': part_first_cust_name,
                'Part Number': part,
                'Invoice No.': '',
                'Invoice Date': '',
                'Qty': part_grand_desp_qty,
                'FC Value': round(float(part_grand_desp_fc), 2),
                'INR Value': round(float(part_grand_desp_inr), 2),
                'Date': '',
                'Opening Qty': gt_open_qty,
                'Opening FC': gt_open_fc,
                'Opening INR': gt_open_inr,
                'Shipment Qty': part_grand_ship_qty,
                'Shipment FC': round(float(part_grand_ship_fc), 2),
                'Shipment INR': round(float(part_grand_ship_inr), 2),
                'Closing Qty': part_grand_close_qty,
                'Closing FC': round(float(part_grand_close_fc), 2),
                'Closing INR': round(float(part_grand_close_inr), 2),
            })
            
            # Spacer row
            result_rows.append({
                '_row_type': 'spacer',
                'Code No. Stock AC': '', 'Party Name': '', 'Part Number': '',
                'Invoice No.': '', 'Invoice Date': '',
                'Qty': '', 'FC Value': '', 'INR Value': '', 'Date': '',
                'Opening Qty': '', 'Opening FC': '', 'Opening INR': '',
                'Shipment Qty': '', 'Shipment FC': '', 'Shipment INR': '',
                'Closing Qty': '', 'Closing FC': '', 'Closing INR': '',
            })
        
        return result_rows


