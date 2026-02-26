from datetime import datetime, date
from decimal import Decimal
from django.db.models import Sum, F, DecimalField, Value
from django.db.models.functions import Coalesce
from sales.models import Invoice, InvoiceRetailPartMap
from retail.models import InvoiceEntry

class StockLedgerService:
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
                    total_qty=Coalesce(Sum('qty'), 0),
                    total_fc=Coalesce(Sum('dollar_total'), Decimal(0), output_field=DecimalField()),
                    total_inr=Coalesce(Sum('inr_total'), Decimal(0), output_field=DecimalField())
                )
                
                # Outgoing (Subtract)
                # Need to find retail parts mapped to this customer
                retail_parts = InvoiceRetailPartMap.objects.filter(company_name=party_name).values_list('retail_part_number', flat=True)
                
                outgoing_opening = InvoiceEntry.objects.filter(
                    part_number__in=retail_parts,
                    date__lt=start_date
                ).aggregate(
                    total_qty=Coalesce(Sum('qty'), 0),
                    total_fc=Coalesce(Sum('usd_total'), Decimal(0), output_field=DecimalField()),
                    total_inr=Coalesce(Sum('inr_total'), Decimal(0), output_field=DecimalField())
                )
                
                # Net Opening
                opening_qty = (incoming_opening['total_qty'] or 0) - (outgoing_opening['total_qty'] or 0)
                opening_fc_val = (incoming_opening['total_fc'] or Decimal(0)) - (outgoing_opening['total_fc'] or Decimal(0))
                opening_inr_val = (incoming_opening['total_inr'] or Decimal(0)) - (outgoing_opening['total_inr'] or Decimal(0))

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
                total_qty=Coalesce(Sum('qty'), 0),
                total_fc=Coalesce(Sum('dollar_total'), Decimal(0), output_field=DecimalField()),
                total_inr=Coalesce(Sum('inr_total'), Decimal(0), output_field=DecimalField())
            )

            # Outgoing (Despatch to Customer)
            retail_parts = InvoiceRetailPartMap.objects.filter(company_name=party_name).values_list('retail_part_number', flat=True)
            
            outgoing_period_filter = {
                'part_number__in': retail_parts
            }
            # Re-apply date filter
            if start_date:
                outgoing_period_filter['date__gte'] = start_date
            if end_date:
                outgoing_period_filter['date__lte'] = end_date
                
            outgoing_period = InvoiceEntry.objects.filter(
                **outgoing_period_filter
            ).aggregate(
                total_qty=Coalesce(Sum('qty'), 0),
                total_fc=Coalesce(Sum('usd_total'), Decimal(0), output_field=DecimalField()),
                total_inr=Coalesce(Sum('inr_total'), Decimal(0), output_field=DecimalField())
            )

            # Extract values safely
            inc_qty = incoming_period['total_qty'] or 0
            inc_fc = incoming_period['total_fc'] or Decimal(0)
            inc_inr = incoming_period['total_inr'] or Decimal(0)
            
            out_qty = outgoing_period['total_qty'] or 0
            out_fc = outgoing_period['total_fc'] or Decimal(0)
            out_inr = outgoing_period['total_inr'] or Decimal(0)

            # --- CLOSING BALANCE ---
            closing_qty = opening_qty + inc_qty - out_qty
            closing_fc_val = opening_fc_val + inc_fc - out_fc
            closing_inr_val = opening_inr_val + inc_inr - out_inr

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
                    "Opening Stock FC Value": opening_fc_val,
                    "Opening Stock INR Value": opening_inr_val,
                    
                    "Shipment to WH (Add) Qty": inc_qty,
                    "Shipment to WH (Add) FC": inc_fc,
                    "Shipment to WH (Add) INR": inc_inr,
                    
                    "Despatch (Less) Qty": out_qty,
                    "Despatch (Less) FC": out_fc,
                    "Despatch (Less) INR": out_inr,
                    
                    "Closing Stock Qty": closing_qty,
                    "Closing Stock FC Value": closing_fc_val,
                    "Closing Stock INR Value": closing_inr_val,
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

        # Build part → company mapping
        retail_to_company = {}
        for pm in InvoiceRetailPartMap.objects.all():
            retail_to_company[pm.retail_part_number] = pm.company_name

        # Get all entries in period
        entries = InvoiceEntry.objects.filter(**date_filter).order_by('date')

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
                    qty=Coalesce(Sum('qty'), 0),
                    fc=Coalesce(Sum('dollar_total'), Decimal(0), output_field=DecimalField()),
                    inr=Coalesce(Sum('inr_total'), Decimal(0), output_field=DecimalField()),
                )
                retail_parts = InvoiceRetailPartMap.objects.filter(
                    company_name=party_name
                ).values_list('retail_part_number', flat=True)
                out_open = InvoiceEntry.objects.filter(
                    part_number__in=retail_parts, date__lt=start_date
                ).aggregate(
                    qty=Coalesce(Sum('qty'), 0),
                    fc=Coalesce(Sum('usd_total'), Decimal(0), output_field=DecimalField()),
                    inr=Coalesce(Sum('inr_total'), Decimal(0), output_field=DecimalField()),
                )
                opening_qty = (inc_open['qty'] or 0) - (out_open['qty'] or 0)
                opening_fc = (inc_open['fc'] or Decimal(0)) - (out_open['fc'] or Decimal(0))
                opening_inr = (inc_open['inr'] or Decimal(0)) - (out_open['inr'] or Decimal(0))

            # --- Calculate Shipment (Incoming) in period ---
            inc_filter = {'customer_name': party_name}
            if start_date:
                inc_filter['date__gte'] = start_date
            if end_date:
                inc_filter['date__lte'] = end_date

            inc_period = Invoice.objects.filter(**inc_filter).aggregate(
                qty=Coalesce(Sum('qty'), 0),
                fc=Coalesce(Sum('dollar_total'), Decimal(0), output_field=DecimalField()),
                inr=Coalesce(Sum('inr_total'), Decimal(0), output_field=DecimalField()),
            )
            ship_qty = inc_period['qty'] or 0
            ship_fc = inc_period['fc'] or Decimal(0)
            ship_inr = inc_period['inr'] or Decimal(0)

            # --- Despatch totals from individual entries ---
            desp_qty = sum(e.qty or 0 for e in entries_list)
            desp_fc = sum(e.usd_total or Decimal(0) for e in entries_list)
            desp_inr = sum(e.inr_total or Decimal(0) for e in entries_list)

            # --- Closing Stock ---
            closing_qty = opening_qty + ship_qty - desp_qty
            closing_fc = opening_fc + ship_fc - desp_fc
            closing_inr = opening_inr + ship_inr - desp_inr

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
                'Opening FC': float(opening_fc),
                'Opening INR': float(opening_inr),
                'Shipment Qty': ship_qty,
                'Shipment FC': float(ship_fc),
                'Shipment INR': float(ship_inr),
                'Closing Qty': closing_qty,
                'Closing FC': float(closing_fc),
                'Closing INR': float(closing_inr),
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
                    result_rows.append({
                        '_row_type': 'detail',
                        'Code No. Stock AC': party_code,
                        'Party Name': party_name,
                        'Part Number': entry.part_number,
                        'Qty': entry.qty,
                        'FC Value': float(entry.usd_total or 0),
                        'INR Value': float(entry.inr_total or 0),
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
                part_qty = sum(e.qty or 0 for e in part_entries)
                part_fc = sum(float(e.usd_total or 0) for e in part_entries)
                part_inr = sum(float(e.inr_total or 0) for e in part_entries)
                result_rows.append({
                    '_row_type': 'part_subtotal',
                    'Code No. Stock AC': '',
                    'Party Name': '',
                    'Part Number': f'{part_number} — Total',
                    'Qty': part_qty,
                    'FC Value': round(part_fc, 2),
                    'INR Value': round(part_inr, 2),
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
                'FC Value': float(desp_fc),
                'INR Value': float(desp_inr),
                'Date': '',
                'Opening Qty': '',
                'Opening FC': '',
                'Opening INR': '',
                'Shipment Qty': '',
                'Shipment FC': '',
                'Shipment INR': '',
                'Closing Qty': closing_qty,
                'Closing FC': float(closing_fc),
                'Closing INR': float(closing_inr),
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
        company_to_code = {}
        for pm in InvoiceRetailPartMap.objects.all():
            retail_to_company[pm.retail_part_number] = pm.company_name
            if pm.customer_code:
                company_to_code[pm.company_name] = pm.customer_code
                
        for c in Invoice.objects.values('customer_name', 'customer_code').distinct():
            name = c['customer_name'] or "Cooper"
            if name not in company_to_code and c['customer_code']:
                company_to_code[name] = c['customer_code']

        entries = InvoiceEntry.objects.filter(**date_filter).order_by('date')
        
        inc_filter = {}
        if start_date:
            inc_filter['date__gte'] = start_date
        if end_date:
            inc_filter['date__lte'] = end_date
        incoming_invoices = Invoice.objects.filter(**inc_filter)
        
        all_parts = set()
        for e in entries:
            all_parts.add(e.part_number)
        for i in incoming_invoices:
            all_parts.add(i.part_number)
            
        opening_inc = {}
        opening_out = {}
        if start_date:
            prev_inc = Invoice.objects.filter(date__lt=start_date).values('part_number', 'customer_name').annotate(
                qty=Coalesce(Sum('qty'), 0),
                fc=Coalesce(Sum('dollar_total'), Decimal(0), output_field=DecimalField()),
                inr=Coalesce(Sum('inr_total'), Decimal(0), output_field=DecimalField())
            )
            for p in prev_inc:
                part = p['part_number']
                cust = p['customer_name'] or "Cooper"
                opening_inc[(part, cust)] = p
                all_parts.add(part)
                
            prev_out = InvoiceEntry.objects.filter(date__lt=start_date).values('part_number').annotate(
                qty=Coalesce(Sum('qty'), 0),
                fc=Coalesce(Sum('usd_total'), Decimal(0), output_field=DecimalField()),
                inr=Coalesce(Sum('inr_total'), Decimal(0), output_field=DecimalField())
            )
            for p in prev_out:
                part = p['part_number']
                cust = retail_to_company.get(part, "Unknown")
                if (part, cust) not in opening_out:
                    opening_out[(part, cust)] = {'qty': 0, 'fc': Decimal(0), 'inr': Decimal(0)}
                opening_out[(part, cust)]['qty'] += p['qty']
                opening_out[(part, cust)]['fc'] += p['fc']
                opening_out[(part, cust)]['inr'] += p['inr']
                all_parts.add(part)

        period_inc = {}
        period_inc_qs = Invoice.objects.filter(**inc_filter).values('part_number', 'customer_name').annotate(
            qty=Coalesce(Sum('qty'), 0),
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
            part = e.part_number
            cust = retail_to_company.get(part, "Unknown")
            if (part, cust) not in period_out_entries:
                period_out_entries[(part, cust)] = []
            period_out_entries[(part, cust)].append(e)

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
            
            result_rows.append({
                '_row_type': 'part_header',
                'Code No. Stock AC': '',
                'Party Name': '',
                'Part Number': f'{part}',
                'Qty': '', 'FC Value': '', 'INR Value': '', 'Date': '',
                'Opening Qty': '', 'Opening FC': '', 'Opening INR': '',
                'Shipment Qty': '', 'Shipment FC': '', 'Shipment INR': '',
                'Closing Qty': '', 'Closing FC': '', 'Closing INR': '',
            })
            
            for cust in sorted(list(customers_for_part)):
                o_inc = opening_inc.get((part, cust), {'qty': 0, 'fc': Decimal(0), 'inr': Decimal(0)})
                o_out = opening_out.get((part, cust), {'qty': 0, 'fc': Decimal(0), 'inr': Decimal(0)})
                
                open_qty = (o_inc['qty'] or 0) - (o_out['qty'] or 0)
                open_fc = (o_inc['fc'] or Decimal(0)) - (o_out['fc'] or Decimal(0))
                open_inr = (o_inc['inr'] or Decimal(0)) - (o_out['inr'] or Decimal(0))
                
                p_inc = period_inc.get((part, cust), {'qty': 0, 'fc': Decimal(0), 'inr': Decimal(0)})
                ship_qty = p_inc['qty'] or 0
                ship_fc = p_inc['fc'] or Decimal(0)
                ship_inr = p_inc['inr'] or Decimal(0)
                
                cust_entries = period_out_entries.get((part, cust), [])
                
                desp_qty = sum(e.qty for e in cust_entries)
                desp_fc = sum((e.usd_total or Decimal(0)) for e in cust_entries)
                desp_inr = sum((e.inr_total or Decimal(0)) for e in cust_entries)
                
                part_grand_desp_qty += desp_qty
                part_grand_desp_fc += desp_fc
                part_grand_desp_inr += desp_inr
                
                close_qty = open_qty + ship_qty - desp_qty
                close_fc = open_fc + ship_fc - desp_fc
                close_inr = open_inr + ship_inr - desp_inr
                
                has_activity = (open_qty != 0 or ship_qty > 0 or desp_qty > 0 or close_qty != 0)
                if not has_activity:
                    continue
                
                cust_code = company_to_code.get(cust, '')
                
                # We skip individual 'detail' transaction rows to make this a clean summary sheet
                
                if start_date:
                    open_qty_val = open_qty
                    open_fc_val = float(open_fc)
                    open_inr_val = float(open_inr)
                else:
                    open_qty_val = ''
                    open_fc_val = ''
                    open_inr_val = ''

                result_rows.append({
                    '_row_type': 'customer_subtotal',
                    'Code No. Stock AC': cust_code,
                    'Party Name': f'{cust} — Subtotal',
                    'Part Number': '',
                    'Qty': desp_qty,
                    'FC Value': float(desp_fc),
                    'INR Value': float(desp_inr),
                    'Date': '',
                    'Opening Qty': open_qty_val,
                    'Opening FC': open_fc_val,
                    'Opening INR': open_inr_val,
                    'Shipment Qty': ship_qty,
                    'Shipment FC': float(ship_fc),
                    'Shipment INR': float(ship_inr),
                    'Closing Qty': close_qty,
                    'Closing FC': float(close_fc),
                    'Closing INR': float(close_inr),
                })
                
            result_rows.append({
                '_row_type': 'part_grand_total',
                'Code No. Stock AC': '',
                'Party Name': '',
                'Part Number': f'{part} — Grand Total',
                'Qty': part_grand_desp_qty,
                'FC Value': float(part_grand_desp_fc),
                'INR Value': float(part_grand_desp_inr),
                'Date': '',
                'Opening Qty': '', 'Opening FC': '', 'Opening INR': '',
                'Shipment Qty': '', 'Shipment FC': '', 'Shipment INR': '',
                'Closing Qty': '', 'Closing FC': '', 'Closing INR': '',
            })
            
            # Spacer row
            result_rows.append({
                '_row_type': 'spacer',
                'Code No. Stock AC': '', 'Party Name': '', 'Part Number': '',
                'Qty': '', 'FC Value': '', 'INR Value': '', 'Date': '',
                'Opening Qty': '', 'Opening FC': '', 'Opening INR': '',
                'Shipment Qty': '', 'Shipment FC': '', 'Shipment INR': '',
                'Closing Qty': '', 'Closing FC': '', 'Closing INR': '',
            })
            
        return result_rows


