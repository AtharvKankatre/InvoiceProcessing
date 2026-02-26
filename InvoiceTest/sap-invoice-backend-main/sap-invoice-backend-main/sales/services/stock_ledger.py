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

            # --- INDIVIDUAL TRANSACTION ROWS ---
            for entry in entries_list:
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

            # --- SUBTOTAL ROW ---
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


