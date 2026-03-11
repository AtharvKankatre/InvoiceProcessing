from datetime import datetime

import pandas as pd
from django.db.models import Q, Sum
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, action
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from django.http import HttpResponse

from .models import Invoice, InvoiceRetailPartMap, InvoiceEntryConsumption
from .serializers import InvoiceSerializer, InvoiceRetailPartMapSerializer, InvoiceEntryConsumptionSerializer
from user.models import User
from retail.models import InvoiceEntry
from datetime import date, datetime
from rest_framework import generics
import traceback
import logging

from .utils import TransactionMerger, BalanceCalculator
from rest_framework.exceptions import AuthenticationFailed, NotAuthenticated
from django.db import OperationalError, DatabaseError

logger = logging.getLogger(__name__)


@api_view(["GET"])
def available_invoices(request):
    """
    Get available Cooper invoices for a given retail part number.
    Used for manual invoice selection before reconciliation.
    """
    try:
        part_number = request.query_params.get("part_number")
        
        if not part_number:
            return Response(
                {"error": "part_number query parameter is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Map retail part number to sale part number
        try:
            part_mapping = InvoiceRetailPartMap.objects.filter(
                retail_part_number=part_number
            ).first()
            
            if not part_mapping:
                # FALLBACK: If no mapping found, assume Retail Part = Sale Part
                sale_part_number = part_number
                company_name = "Unknown" # Or fetch from elsewhere if needed
            else:
                sale_part_number = part_mapping.sale_part_number
                company_name = part_mapping.company_name or ""
            
        except Exception as e:
            return Response(
                {"error": f"Error looking up part mapping: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Get all invoices with available quantity for this part
        invoices = Invoice.objects.filter(
            part_number=sale_part_number,
            qty__gt=0
        ).order_by("date", "id")
        
        # Build response
        invoice_list = []
        total_available = 0
        
        for inv in invoices:
            invoice_list.append({
                "id": inv.id,
                "invoice_number": inv.invoice_number,
                "part_number": inv.part_number,
                "date": inv.date.isoformat(),
                "available_qty": inv.qty,
                "original_qty": inv.invoice_qty,
                "dollar_rate": float(inv.dollar_rate),
                "conversion_rate": float(inv.conversion_rate),
                "inr_rate": float(inv.inr_rate),
                "customer_code": inv.customer_code or "",
            })
            total_available += inv.qty
        
        return Response({
            "retail_part_number": part_number,
            "sale_part_number": sale_part_number,
            "company_name": company_name,
            "invoices": invoice_list,
            "total_available_qty": total_available,
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(["POST"])
@parser_classes([MultiPartParser])
def upload_invoice_excel(request):
    excel_file = request.FILES.get("file")

    if not excel_file:
        return Response(
            {"error": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST
        )

    try:
        df = pd.read_excel(excel_file)
        df = df.rename(columns=lambda x: x.strip().lower())
        # required_columns = [
        #     'Part Number', 'Date', 'Qty', '$ rate', '$ total',
        #     'INR Rate', 'INR Total', 'Conversion Rate'
        # ]

        required_columns = [
            "invoice number",
            "part number",
            "date",
            "qty",
            "$ rate",
            "$ total",
            "inr rate",
            "inr total",
            "conversion rate",
            "customer code",
        ]

        # for col in df.columns:
        # print("col is ", col)

        if not all(col in df.columns for col in required_columns):
            return Response(
                {"error": f"Missing required columns in Excel "}, status=status.HTTP_400_BAD_REQUEST
            )

        # print("request user id is", request.user.exp)
        # return 0
        seen_invoice_keys = set()
        created_invoice_records = []
        user_instance = User.objects.get(id=request.user.id)
        for _, row in df.iterrows():
            invoice_number = row["invoice number"]
            invoice_date = pd.to_datetime(row["date"], dayfirst=True).date()
            fiscal_year_start = get_fiscal_year(invoice_date)
            fiscal_year_end = fiscal_year_start + 1
            # Key to detect duplicate in current file
            invoice_key = (invoice_number, fiscal_year_start)
            # disable duplicate invoice check because same invoice can be
            # present in the same file multipe times

            # if invoice_key in seen_invoice_keys:
            #     return Response(
            #         {
            #             "error": f"Duplicate invoice number '{invoice_number}' in the same fiscal year ({fiscal_year_start}-{fiscal_year_end}) within this file."
            #         },
            #         status=status.HTTP_400_BAD_REQUEST,
            #     )
            # seen_invoice_keys.add(invoice_key)

            # Check for duplicate in database
            # duplicate_exists = Invoice.objects.filter(
            #     invoice_number=invoice_number,
            #     date__gte=date(fiscal_year_start, 4, 1),
            #     date__lte=date(fiscal_year_end, 3, 31),
            # ).exists()

            invoice = Invoice.objects.create(
                invoice_number=row["invoice number"],
                part_number=row["part number"],
                date=pd.to_datetime(row["date"], dayfirst=True).date(),  # "08.03.2022"
                qty=int(row["qty"]),
                invoice_qty = int(row["qty"]),
                dollar_rate=row["$ rate"],
                dollar_total=row["$ total"],
                inr_rate=row["inr rate"],
                inr_total=row["inr total"],
                conversion_rate=row["conversion rate"],
                customer_code=row["customer code"],
                customer_name = row["customer name"],
                created_by=user_instance,
            )
            created_invoice_records.append(invoice)

        # print("Created data is ", created_invoice_records)
        serializer = InvoiceSerializer(created_invoice_records, many=True)

        return Response(
            {"message": "Data imported successfully", "data": serializer.data},
            status=status.HTTP_201_CREATED,
        )

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
def view_invoice_file(request):
    try:
        invoice_number = request.query_params.get("invoiceNo")
        invoice_month = request.query_params.get(
            "invoiceMonth"
        )  # Expected format: YYYY-MM

        if not invoice_number and not invoice_month:
            return Response(
                {"error": "Either 'invoiceNo' or 'invoiceMonth' must be provided."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        filters = Q()

        if invoice_number:
            filters |= Q(invoice_number=invoice_number)

        if invoice_month:
            try:
                month_date = datetime.strptime(invoice_month, "%Y-%m")
                filters |= Q(date__year=month_date.year, date__month=month_date.month)
            except ValueError:
                return Response(
                    {"error": "Invalid 'invoiceMonth' format. Use YYYY-MM."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        invoices = Invoice.objects.filter(filters)
        serializer = InvoiceSerializer(invoices, many=True)
        return Response({"data": serializer.data}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
def view_invoices(request):
    try:
        # Get the query parameters from the request
        filter_params = request.query_params

        # Start with the base queryset
        all_invoices = Invoice.objects.all()

        # Build Q objects for dynamic filtering
        query = Q()

        # List of fields we want to allow filtering on
        filterable_fields = [
            "invoice_number",
            "part_number",
            "date",
            "qty", 
            "dollar_rate",
            "dollar_total", 
            "inr_rate", 
            "inr_total",
            "conversion_rate",
            "invoice_qty"
        ]

        # Apply filters for each field if the field exists in the query params
        numeric_fields = ["qty", "invoice_qty", "dollar_rate", "dollar_total", "inr_rate", "inr_total", "conversion_rate"]
        for field in filterable_fields:
            value = filter_params.get(field)
            if value:
                if field in numeric_fields:
                    # Validate numeric input before filtering
                    try:
                        float(value)  # Validate it's a valid number
                        query &= Q(**{f"{field}__exact": value})
                    except (ValueError, TypeError):
                        continue  # Skip invalid numeric filters silently
                elif field == "date":
                    query &= Q(**{f"{field}__exact": value})
                else:
                    # For string fields, apply 'icontains' for partial matching
                    query &= Q(**{f"{field}__icontains": value})

        # Apply the filters to the queryset
        if query:
            all_invoices = all_invoices.filter(query)

        # Pagination setup
        paginator = PageNumberPagination()
        paginator.page_size = (
            10  # Adjust this number to control the number of items per page
        )
        paginated_invoices = paginator.paginate_queryset(all_invoices, request)

        # Serialize the paginated invoices
        serializer = InvoiceSerializer(paginated_invoices, many=True)

        # Return paginated response
        return paginator.get_paginated_response(serializer.data)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
def dashboard(request):
    try:
        # Total number of distinct invoices
        distinct_invoice_count = (
            Invoice.objects.values("invoice_number").distinct().count()
        )

        # Total quantity across all invoices
        total_qty = Invoice.objects.aggregate(total_qty=Sum("qty"))["total_qty"] or 0

        reconciled_invoices = (
            InvoiceEntry.objects.values("retail_invoice_number").distinct().count()
        )

        # Total dollar value across all invoices
        total_dollar = (
            Invoice.objects.aggregate(total_dollar=Sum("dollar_total"))["total_dollar"]
            or 0
        )

        return Response(
            {
                "total_distinct_invoices": distinct_invoice_count,
                "total_qty": total_qty,
                "total_dollar_total": total_dollar,
                "reconciled_invoices": reconciled_invoices,
            },
            status=status.HTTP_200_OK,
        )
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def get_fiscal_year(date):
    if date.month >= 4:
        return date.year  # April to Dec: current year is fiscal start
    else:
        return date.year - 1  # Jan to Mar: previous year is fiscal start


@api_view(["POST"])
@parser_classes([MultiPartParser])
def upload_part_map_excel(request):
    try:
        excel_file = request.FILES.get("file")
        if not excel_file:
            return Response(
                {"error": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST
            )
        df = pd.read_excel(excel_file)
        df = df.rename(columns=lambda x: x.strip().lower())
        required_columns = [
            "sales register material number",
            "sale invoice material number",
            "customer name",
        ]

        if not all(col in df.columns for col in required_columns):
            return Response(
                {"error": f"Missing required columns in excel "}, status=status.HTTP_400_BAD_REQUEST
            )

        user_instance = User.objects.get(id=request.user.id)
        created_part_records = []
        for _, row in df.iterrows():
            sale_part_number = row["sales register material number"]
            retail_part_number = row["sale invoice material number"]
            customer_name = row["customer name"]
            customer_code = row.get("customer code", None)
            
            # Put None if it's NaN (pandas behavior for missing values)
            if pd.isna(customer_code):
                customer_code = None

            invoice_retail_part_map = InvoiceRetailPartMap.objects.create(
                sale_part_number=sale_part_number,
                retail_part_number=retail_part_number,
                company_name=customer_name,
                customer_code=customer_code,
                created_by=user_instance,
            )
            created_part_records.append(invoice_retail_part_map)

        serializer = InvoiceRetailPartMapSerializer(created_part_records, many=True)

        return Response(
            {"message": "Data imported successfully", "data": serializer.data},
            status=status.HTTP_201_CREATED,
        )

    except Exception as e:
        # trace = traceback.format_exc()
        # print("trace is ", trace)
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RetailPartMapListView(generics.ListAPIView):
    queryset = InvoiceRetailPartMap.objects.all()
    serializer_class = InvoiceRetailPartMapSerializer

    filterset_fields = ["sale_part_number", "retail_part_number", "company_name"]

    ordering_fields = ["company_name", "created_date"]

    def get_queryset(self):
        queryset = InvoiceRetailPartMap.objects.all()

        filter_params = self.request.query_params

        query = Q()

        for field in self.filterset_fields:
            value = filter_params.get(field)
            if value:
                query &= Q(**{f"{field}__icontains": value})

        if query:
            queryset = queryset.filter(query)

        return queryset

    # if there is already a queryset, why another helper method is required

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.filter_queryset(self.get_queryset())
            paginator = PageNumberPagination()
            paginated_queryset = paginator.paginate_queryset(queryset, request)
            serializer = self.get_serializer(paginated_queryset, many=True)
            return paginator.get_paginated_response(serializer.data)
        except Exception as e:
            # tb = traceback.format_exc()
            # print("traceback", tb)
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@api_view(["GET"])
def invoice_balance_history(request):
    """
    Get combined history of invoice creation (credit) and consumption (debit).
    """
    try:
        # Get all invoices for the dropdown list
        all_invoices_qs = Invoice.objects.all().order_by("-date")
        all_invoices_data = InvoiceSerializer(all_invoices_qs, many=True).data

        invoice_id = request.query_params.get("invoice_id")
        
        response_data = {
            "all_invoices": all_invoices_data,
            "history": [],
            "invoice": None
        }

        if invoice_id:
            try:
                selected_invoice = Invoice.objects.get(id=invoice_id)
                response_data["invoice"] = InvoiceSerializer(selected_invoice).data
                
                # Build history for this SPECIFIC invoice
                history = []
                
                # Guard against NULL invoice_qty (some invoices may not have this set)
                inv_qty = float(selected_invoice.invoice_qty) if selected_invoice.invoice_qty is not None else float(selected_invoice.qty or 0)

                # 1. Creation Event
                history.append({
                    "id": f"inv_{selected_invoice.id}",
                    "date": selected_invoice.date,
                    "type": "Invoice Created",
                    "reference": selected_invoice.invoice_number,
                    "part_number": selected_invoice.part_number,
                    "change": inv_qty,
                    "price": float(selected_invoice.dollar_rate) if selected_invoice.dollar_rate is not None else 0.0,
                    "currency": "USD",
                    "action": "Created",
                    "balance": inv_qty  # Initial balance
                })

                # 2. Consumption Events
                consumptions = InvoiceEntryConsumption.objects.filter(invoice=selected_invoice).order_by("invoice_entry__date")

                running_balance = inv_qty

                for cons in consumptions:
                    # Skip orphaned consumption records
                    if not cons.invoice_entry:
                        continue
                    consumed_qty = float(cons.consumed_qty) if cons.consumed_qty is not None else 0.0
                    running_balance -= consumed_qty
                    
                    history.append({
                        "id": f"cons_{cons.id}",
                        "date": cons.invoice_entry.date.isoformat(),
                        "type": "Retail Consumption",
                        "reference": cons.invoice_entry.retail_invoice_number or f"OUT-{cons.invoice_entry.date}",
                        "part_number": cons.invoice.part_number,
                        "change": -consumed_qty,
                        "price": float(cons.invoice_entry.usd_rate) if cons.invoice_entry.usd_rate is not None else 0.0,
                        "currency": "USD",
                        "action": "Retail Sales",
                        "balance": running_balance
                    })
                
                # Sort by date (newest first)
                def parse_date(item):
                    d = item["date"]
                    if isinstance(d, str):
                        try:
                            return datetime.strptime(d, "%Y-%m-%d").date()
                        except ValueError:
                            return datetime.strptime(d, "%Y-%m-%dT%H:%M:%S").date()
                    return d

                history.sort(key=lambda x: parse_date(x), reverse=True)
                
                # Pagination
                from django.core.paginator import Paginator
                page_number = request.query_params.get("page", 1)
                page_size = request.query_params.get("page_size", 10)
                paginator = Paginator(history, page_size)
                page_obj = paginator.get_page(page_number)

                response_data["history"] = {
                    "results": list(page_obj.object_list),
                    "count": paginator.count,
                    "num_pages": paginator.num_pages,
                    "current_page": page_obj.number,
                    "has_next": page_obj.has_next(),
                    "has_previous": page_obj.has_previous(),
                }

            except Invoice.DoesNotExist:
                return Response({"error": "Invoice not found"}, status=status.HTTP_404_NOT_FOUND)

        return Response(response_data)

    except Exception as e:
        traceback.print_exc()
        return Response(
            {"error": str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


from rest_framework import viewsets
from rest_framework.exceptions import AuthenticationFailed, NotAuthenticated
from datetime import datetime
from django.db import OperationalError, DatabaseError
from .services.transaction_merger import TransactionMerger
from .services.balance_calculator import BalanceCalculator
import logging

logger = logging.getLogger(__name__)


class PartHistoryViewSet(viewsets.ViewSet):
    """
    ViewSet for retrieving part-wise transaction history.
    """
    
    @action(detail=False, url_path='export')
    def export_history(self, request, part_number=None):
        try:
            # Export Part History to Excel
            # Instantiate helpers
            merger = TransactionMerger()
            calculator = BalanceCalculator()
            
            # Optional date filters
            from_date = request.query_params.get("from_date")
            to_date = request.query_params.get("to_date")
            
            # Determine part_number: prefer URL kwarg, fallback to query param
            part_number = self.kwargs.get('part_number') or request.query_params.get('part_number')
            
            # Strip whitespace only — preserve original case so it matches DB values (e.g. "PART-A400")
            clean_part = str(part_number).strip() if part_number else None
            fetch_part = clean_part if clean_part and clean_part.lower() != 'all' else None

            # Get transactions
            incoming_transactions = merger.get_incoming_transactions(
                fetch_part, from_date, to_date
            )
            outgoing_transactions = merger.get_outgoing_transactions(
                fetch_part, from_date, to_date
            )
            


            # Merge and sort transactions
            merged_transactions = merger.merge_and_sort(
                incoming_transactions, outgoing_transactions
            )
            
            # Calculate running balance (Only if SINGLE part is selected)
            # For ALL parts, running balance across mixed part numbers is meaningless
            # So we only calculate it if a specific part is selected.
            if fetch_part:
                transactions_with_balance = calculator.calculate_running_balance(
                    merged_transactions
                )
            else:
                 # Group transactions by part number
                 from collections import defaultdict
                 grouped_txns = defaultdict(list)
                 for txn in merged_transactions:
                     p_num = txn.get('part_number', 'UNKNOWN')
                     grouped_txns[p_num].append(txn)
                 
                 transactions_with_balance = []
                 for p_num, p_txns in grouped_txns.items():
                     p_bals = calculator.calculate_running_balance(p_txns)
                     transactions_with_balance.extend(p_bals)
                 # Final sort by Part Number only — preserve invoice-wise grouping within each part
                 transactions_with_balance.sort(key=lambda x: x.get('part_number', ''))
            # ── Compute Surcharge & Exchange Gain for outgoing rows ──
            from decimal import Decimal
            from sales.models import InvoiceEntryConsumption as IEC

            # Collect all outgoing entry IDs to batch-query consumption records
            all_entry_ids = set()
            for txn in transactions_with_balance:
                if txn.get('type') == 'OUTGOING' and txn.get('invoice_entry_id'):
                    all_entry_ids.add(txn['invoice_entry_id'])

            # Build lookup: (entry_id, invoice_id) -> consumption record
            # AND fallback: entry_id -> list of all consumption records
            consumption_by_key = {}  # (entry_id, invoice_id) -> consumption
            consumption_by_entry = {}  # entry_id -> [consumptions]
            if all_entry_ids:
                cons_qs = IEC.objects.filter(
                    invoice_entry_id__in=all_entry_ids
                ).select_related('invoice', 'invoice_entry')
                for c in cons_qs:
                    eid = c.invoice_entry_id
                    iid = c.invoice_id
                    consumption_by_key[(eid, iid)] = c
                    if eid not in consumption_by_entry:
                        consumption_by_entry[eid] = []
                    consumption_by_entry[eid].append(c)

            def _calc_surcharge_exchange(txn):
                """Calculate surcharge and exchange gain for an outgoing transaction."""
                entry_id = txn.get('invoice_entry_id')
                consumed_qty = abs(txn.get('qty', 0))
                if not entry_id or not consumed_qty:
                    return 0, 0

                # Try to find the SPECIFIC consumption record for this split row
                consumption_invoice_id = txn.get('consumption_invoice_id')
                
                if consumption_invoice_id:
                    # Precise match: use the specific consumption record
                    c = consumption_by_key.get((entry_id, consumption_invoice_id))
                    if c:
                        inv = c.invoice
                        entry = c.invoice_entry
                        c_qty = consumed_qty

                        inv_dollar_rate = inv.dollar_rate or Decimal(0)
                        entry_usd_rate = entry.usd_rate or Decimal(0)
                        plating = entry.plating_charges or Decimal(0)
                        adjusted_rate = entry_usd_rate - plating
                        inv_er = inv.conversion_rate or Decimal(0)
                        entry_er = entry.conversion_rate or Decimal(0)

                        s_fc = (inv_dollar_rate - adjusted_rate) * c_qty
                        surcharge = float(round(s_fc * inv_er, 2))
                        exchange_gain = float(round((inv_er - entry_er) * c_qty * adjusted_rate, 2))

                        return surcharge, exchange_gain

                # Fallback: bill-to-bill or orphan rows without consumption_invoice_id
                # Use all consumption records for this entry
                cons_list = consumption_by_entry.get(entry_id, [])
                if not cons_list:
                    return 0, 0

                # If only one consumption record, use it directly
                if len(cons_list) == 1:
                    c = cons_list[0]
                    inv = c.invoice
                    entry = c.invoice_entry

                    inv_dollar_rate = inv.dollar_rate or Decimal(0)
                    entry_usd_rate = entry.usd_rate or Decimal(0)
                    plating = entry.plating_charges or Decimal(0)
                    adjusted_rate = entry_usd_rate - plating
                    inv_er = inv.conversion_rate or Decimal(0)
                    entry_er = entry.conversion_rate or Decimal(0)

                    s_fc = (inv_dollar_rate - adjusted_rate) * consumed_qty
                    surcharge = float(round(s_fc * inv_er, 2))
                    exchange_gain = float(round((inv_er - entry_er) * consumed_qty * adjusted_rate, 2))
                    return surcharge, exchange_gain

                # Multiple consumptions without specific match: sum all
                total_surcharge = Decimal(0)
                total_exchange_gain = Decimal(0)
                for c in cons_list:
                    inv = c.invoice
                    entry = c.invoice_entry
                    c_qty = c.consumed_qty or 0

                    inv_dollar_rate = inv.dollar_rate or Decimal(0)
                    entry_usd_rate = entry.usd_rate or Decimal(0)
                    plating = entry.plating_charges or Decimal(0)
                    adjusted_rate = entry_usd_rate - plating
                    inv_er = inv.conversion_rate or Decimal(0)
                    entry_er = entry.conversion_rate or Decimal(0)

                    s_fc = (inv_dollar_rate - adjusted_rate) * c_qty
                    total_surcharge += s_fc * inv_er
                    total_exchange_gain += (inv_er - entry_er) * c_qty * adjusted_rate

                return float(round(total_surcharge, 2)), float(round(total_exchange_gain, 2))

            # Group transactions by SAP part number for Excel sheet layout
            final_grouped = {}
            for txn in transactions_with_balance:
                p_num = txn.get('part_number', 'UNKNOWN')
                if p_num not in final_grouped:
                    final_grouped[p_num] = []

                surcharge = ''
                exchange_gain = ''
                if txn['type'] == 'OUTGOING':
                    surcharge, exchange_gain = _calc_surcharge_exchange(txn)
                    # Surcharge and Exchange Gain shown as POSITIVE (cost amounts)
                    # No negation needed - they come out positive from the formula

                # Compute values for display and calculation
                inr_val = float(txn.get('inr_value', 0) or 0)
                fc_val = float(txn.get('fc_value', 0) or 0)
                surcharge_num = surcharge if isinstance(surcharge, (int, float)) else 0
                exchange_gain_num = exchange_gain if isinstance(exchange_gain, (int, float)) else 0

                # For outgoing: negate INR Value and FC Value (goods going OUT = negative)
                display_inr = -inr_val if txn['type'] == 'OUTGOING' else inr_val
                display_fc = -fc_val if txn['type'] == 'OUTGOING' else fc_val
                # Rate FC stays positive (per-unit rate is always positive)
                display_rate_fc = abs(float(txn.get('rate_fc', 0) or 0)) if txn.get('rate_fc') else ''

                if txn['type'] == 'INCOMING':
                    calculation = inr_val  # For incoming, Calculation = INR Value (positive)
                else:
                    # For outgoing: (-INR) - (+Surcharge) - (+Exchange Gain) = -(incoming cost)
                    calculation = display_inr - surcharge_num - exchange_gain_num

                final_grouped[p_num].append({
                    'Date': txn['date'],
                    'Invoice No': txn['invoice_number'],
                    'Customer Name': txn.get('name', ''),
                    'Customer Code': txn.get('customer_code', ''),
                    'Qty': txn['qty'],
                    'FC Value': display_fc if fc_val else '',
                    'Rate FC': display_rate_fc,
                    'INR Value': display_inr if inr_val else '',
                    'Exchange Rate': txn.get('exchange_rate', ''),
                    'On Hand': txn['on_hand'],
                    'Surcharge': surcharge,
                    'Exchange Gain': exchange_gain,
                    'Calculation': round(calculation, 2),
                    'Type': txn['type'],
                    '_calculation_raw': calculation,
                })

            # Compute Closing Balance Value per part (running cumulative of Calculation)
            for p_num, rows in final_grouped.items():
                running_balance = 0.0
                for row in rows:
                    calc_val = row.pop('_calculation_raw', 0)
                    running_balance += calc_val
                    row['Closing Balance Value'] = round(running_balance, 2)

            # Create response
            response = HttpResponse(
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            filename = f"Part_History_{part_number if part_number else 'ALL'}.xlsx"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            
            # Use ExcelWriter to write grouped data
            try:
                with pd.ExcelWriter(response, engine='openpyxl') as writer:
                    workbook = writer.book
                    worksheet = workbook.create_sheet('History')
                    writer.sheets['History'] = worksheet
                    
                    row_idx = 0
                    
                    # Sort keys to ensure alphabetical order of parts
                    for p_num in sorted(final_grouped.keys()):
                        rows = final_grouped[p_num]
                        
                        # Write Header for Part
                        # We use the underlying openpyxl worksheet object to write the cell
                        cell = worksheet.cell(row=row_idx + 1, column=1, value=f"Part Number: {p_num}")
                        # cell.font = Font(bold=True) # Requires import, skipping to minimize diffs
                        
                        row_idx += 1
                        
                        # Convert to DataFrame
                        df_part = pd.DataFrame(rows)
                        
                        # Write DataFrame
                        df_part.to_excel(writer, sheet_name='History', startrow=row_idx, index=False)
                        
                        # Advance row index: Header + Data Rows + Header of Table + Spacing
                        row_idx += len(df_part) + 1 + 2 
                        
            except Exception as e:
                # Fallback to simple export if openpyxl fails
                logger.error(f"Excel formatting failed: {e}")
                data = [] 
                for txn in transactions_with_balance:
                     data.append(txn)
                df = pd.DataFrame(data)
                df.to_excel(response, index=False)
            
            return response

        except (AuthenticationFailed, NotAuthenticated) as e:
            logger.warning(f"Authentication error in PartHistoryViewSet export: {str(e)}")
            return Response(
                {"error": "Authentication required."},
                status=status.HTTP_401_UNAUTHORIZED
            )
        except Exception as e:
            logger.error(
                f"Unexpected error in PartHistoryViewSet export for part {part_number}: {str(e)}",
                exc_info=True
            )
            return Response(
                {"error": "An error occurred while generating the export."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def list(self, request, part_number=None):
        """
        Retrieve transaction history for a specific part number.
        
        Path parameters:
            part_number: The part number to retrieve history for
            
        Query parameters:
            from_date (optional): Start date in YYYY-MM-DD format
            to_date (optional): End date in YYYY-MM-DD format
            
        Returns:
            HTTP 200: JSON response with part_number and history array
            HTTP 400: Invalid date format
            HTTP 401: Authentication required
            HTTP 503: Service temporarily unavailable (database error)
            HTTP 500: Unexpected server error
        """
        try:
            # Parse and validate query parameters
            from_date_str = request.query_params.get('from_date')
            to_date_str = request.query_params.get('to_date')
            
            from_date = None
            to_date = None
            
            # Validate from_date format
            if from_date_str:
                try:
                    from_date = datetime.strptime(from_date_str, '%Y-%m-%d').date()
                except ValueError:
                    return Response(
                        {"error": "Invalid date format for from_date. Use YYYY-MM-DD."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Validate to_date format
            if to_date_str:
                try:
                    to_date = datetime.strptime(to_date_str, '%Y-%m-%d').date()
                except ValueError:
                    return Response(
                        {"error": "Invalid date format for to_date. Use YYYY-MM-DD."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Instantiate TransactionMerger
            merger = TransactionMerger()
            
            # Get incoming and outgoing transactions
            incoming_transactions = merger.get_incoming_transactions(
                part_number, from_date, to_date
            )
            outgoing_transactions = merger.get_outgoing_transactions(
                part_number, from_date, to_date
            )
            
            # Merge and sort transactions
            merged_transactions = merger.merge_and_sort(
                incoming_transactions, outgoing_transactions
            )
            
            # Instantiate BalanceCalculator
            calculator = BalanceCalculator()
            
            # Calculate running balance
            transactions_with_balance = calculator.calculate_running_balance(
                merged_transactions
            )
            
            # Format response - convert dates to ISO 8601 strings
            history = []
            for transaction in transactions_with_balance:
                history.append({
                    'date': transaction['date'].isoformat(),
                    'invoice_number': transaction['invoice_number'],
                    'name': transaction.get('name', ''),
                    'customer_code': transaction.get('customer_code', ''),
                    'qty': transaction['qty'],
                    'on_hand': transaction['on_hand'],
                    'type': transaction['type']
                })
            
            response_data = {
                'part_number': part_number,
                'history': history
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
        
        except (AuthenticationFailed, NotAuthenticated) as e:
            # Handle authentication errors
            logger.warning(f"Authentication error in PartHistoryViewSet: {str(e)}")
            return Response(
                {"error": "Authentication required."},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        except (OperationalError, DatabaseError) as e:
            # Handle database connection errors
            logger.error(f"Database error in PartHistoryViewSet for part {part_number}: {str(e)}")
            return Response(
                {"error": "Service temporarily unavailable. Please try again later."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        except Exception as e:
            # Handle unexpected exceptions
            logger.error(
                f"Unexpected error in PartHistoryViewSet for part {part_number}: {str(e)}",
                exc_info=True
            )
            return Response(
                {"error": "An unexpected error occurred. Please contact support."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


from .services.stock_ledger import StockLedgerService

class StockLedgerViewSet(viewsets.ViewSet):
    """
    ViewSet to generate the Stock Ledger Report (Customer-wise Summary)
    """

    @action(detail=False, methods=["get"], url_path="export-ledger")
    def export_ledger(self, request):
        try:
            from_date_str = request.query_params.get("from_date")
            to_date_str = request.query_params.get("to_date")
            
            # Helper to parse dd-mm-yyyy or yyyy-mm-dd
            def parse_date_param(d_str):
                if not d_str:
                    return None
                try:
                    return datetime.strptime(d_str, "%d-%m-%Y").date()
                except ValueError:
                    try:
                        return datetime.strptime(d_str, "%Y-%m-%d").date()
                    except ValueError:
                        return None 

            from_date = parse_date_param(from_date_str)
            to_date = parse_date_param(to_date_str)

            # Generate Summary data
            report_data = StockLedgerService.get_ledger_data(from_date, to_date)
            
            # Generate Detailed data
            detailed_data = StockLedgerService.get_detailed_consumption_data(from_date, to_date)
            
            if not report_data and not detailed_data:
                 return Response({"error": "No data found for the selected period"}, status=status.HTTP_404_NOT_FOUND)

            # Create Excel
            df_summary = pd.DataFrame(report_data)

            response = HttpResponse(
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            response["Content-Disposition"] = f'attachment; filename="Stock_Ledger_Report.xlsx"'

            from openpyxl.styles import Font

            with pd.ExcelWriter(response, engine="openpyxl") as writer:
                # 1. Summary Sheet
                if not df_summary.empty:
                    df_summary.to_excel(writer, index=False, sheet_name="Stock Ledger")

                    worksheet = writer.sheets["Stock Ledger"]

                    # Write descriptive column headers (overwrite pandas-generated ones)
                    headers = [
                        "Code No. Stock AC", "Party Name",
                        "Opening Stock Qty", "Opening Stock FC Value", "Opening Stock INR Value",
                        "Shipment to WH (Add) Qty", "Shipment to WH (Add) FC Value", "Shipment to WH (Add) INR Value",
                        "Despatch (Less) Qty", "Despatch (Less) FC Value", "Despatch (Less) INR Value",
                        "Closing Stock Qty", "Closing Stock FC Value", "Closing Stock INR Value",
                    ]
                    for col_num, value in enumerate(headers):
                        worksheet.cell(row=1, column=col_num+1, value=value)

                    # --- TOTAL ROW ---
                    # These key names must exactly match the keys used in report_data (stock_ledger.py)
                    numeric_cols = [
                        "Opening Stock Qty", "Opening Stock FC Value", "Opening Stock INR Value",
                        "Shipment to WH (Add) Qty", "Shipment to WH (Add) FC", "Shipment to WH (Add) INR",
                        "Despatch (Less) Qty", "Despatch (Less) FC", "Despatch (Less) INR",
                        "Closing Stock Qty", "Closing Stock FC Value", "Closing Stock INR Value",
                    ]
                    totals = {col: df_summary[col].sum() for col in numeric_cols}

                    total_row_num = len(df_summary) + 2  # +1 for header row, +1 for 1-based indexing

                    bold_font = Font(bold=True)
                    total_label_cell = worksheet.cell(row=total_row_num, column=2, value="Total")
                    total_label_cell.font = bold_font

                    df_cols = list(df_summary.columns)
                    for col_name, total_val in totals.items():
                        col_idx = df_cols.index(col_name) + 1  # 1-based column index
                        cell = worksheet.cell(row=total_row_num, column=col_idx, value=round(float(total_val), 2))
                        cell.font = bold_font

                # 2. Enhanced Consumption Details Sheet (with Stock Ledger columns)
                if detailed_data:
                    from openpyxl.styles import PatternFill, Alignment, Border, Side

                    ws_details = writer.book.create_sheet("Consumption Details")
                    bold_font = Font(bold=True)
                    header_font = Font(bold=True, color="FFFFFF")
                    header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
                    customer_fill = PatternFill(start_color="D6E4F0", end_color="D6E4F0", fill_type="solid")
                    subtotal_fill = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")
                    part_subtotal_fill = PatternFill(start_color="FDEBD0", end_color="FDEBD0", fill_type="solid")
                    thin_border = Border(
                        bottom=Side(style='thin', color='CCCCCC')
                    )

                    # Column headers
                    detail_headers = [
                        "Code No.", "Customer Name", "Part Number",
                        "Qty", "FC Value", "INR Value", "Date",
                        "Opening Qty", "Opening FC", "Opening INR",
                        "CCPL to WH Qty", "CCPL to WH FC Value", "CCPL to WH INR Value",
                        "Closing Qty", "Closing FC", "Closing INR",
                    ]
                    for col_idx, h in enumerate(detail_headers, 1):
                        cell = ws_details.cell(row=1, column=col_idx, value=h)
                        cell.font = header_font
                        cell.fill = header_fill
                        cell.alignment = Alignment(horizontal="center")

                    # Data column keys (matching dict keys from service)
                    col_keys = [
                        'Code No. Stock AC', 'Party Name', 'Part Number',
                        'Qty', 'FC Value', 'INR Value', 'Date',
                        'Opening Qty', 'Opening FC', 'Opening INR',
                        'Shipment Qty', 'Shipment FC', 'Shipment INR',
                        'Closing Qty', 'Closing FC', 'Closing INR',
                    ]

                    # Grand totals accumulators
                    grand_desp_qty = 0
                    grand_desp_fc = 0.0
                    grand_desp_inr = 0.0

                    current_row = 2
                    for row_data in detailed_data:
                        row_type = row_data.get('_row_type', 'detail')

                        for col_idx, key in enumerate(col_keys, 1):
                            val = row_data.get(key, '')
                            cell = ws_details.cell(row=current_row, column=col_idx, value=val if val != '' else None)

                            # Apply styles by row type
                            if row_type == 'customer_header':
                                cell.font = bold_font
                                cell.fill = customer_fill
                            elif row_type == 'part_subtotal':
                                cell.font = bold_font
                                cell.fill = part_subtotal_fill
                                cell.border = thin_border
                            elif row_type == 'subtotal':
                                cell.font = bold_font
                                cell.fill = subtotal_fill
                                cell.border = thin_border

                        # Accumulate grand totals from subtotal rows
                        if row_type == 'subtotal':
                            grand_desp_qty += (row_data.get('Qty') or 0)
                            grand_desp_fc += (row_data.get('FC Value') or 0)
                            grand_desp_inr += (row_data.get('INR Value') or 0)

                        current_row += 1

                    # --- GRAND TOTAL ROW ---
                    current_row += 1  # blank row separator
                    grand_row = current_row
                    grand_font = Font(bold=True, size=12)
                    grand_fill = PatternFill(start_color="FFC000", end_color="FFC000", fill_type="solid")

                    ws_details.cell(row=grand_row, column=2, value="GRAND TOTAL").font = grand_font
                    ws_details.cell(row=grand_row, column=2).fill = grand_fill
                    for col_idx in range(3, len(col_keys) + 1):
                        ws_details.cell(row=grand_row, column=col_idx).fill = grand_fill

                    ws_details.cell(row=grand_row, column=4, value=grand_desp_qty).font = grand_font
                    ws_details.cell(row=grand_row, column=5, value=round(grand_desp_fc, 2)).font = grand_font
                    ws_details.cell(row=grand_row, column=6, value=round(grand_desp_inr, 2)).font = grand_font

                    # Set column widths
                    from openpyxl.utils import get_column_letter
                    col_widths = [14, 25, 18, 10, 14, 14, 12, 12, 14, 14, 12, 14, 14, 12, 14, 14]
                    for i, w in enumerate(col_widths, 1):
                        ws_details.column_dimensions[get_column_letter(i)].width = w

                    # Freeze header row
                    ws_details.freeze_panes = "A2"

                else:
                    pd.DataFrame(columns=[
                        "Code No.", "Customer Name", "Part Number",
                        "Qty", "FC Value", "INR Value", "Date",
                        "Opening Qty", "Opening FC", "Opening INR",
                        "CCPL to WH Qty", "CCPL to WH FC Value", "CCPL to WH INR Value",
                        "Closing Qty", "Closing FC", "Closing INR",
                    ]).to_excel(writer, index=False, sheet_name="Consumption Details")

                # 3. Part-Wise Tracking Sheet 
                # (Shows Part -> Customer hierarchy)
                partwise_data = StockLedgerService.get_partwise_consumption_data(from_date, to_date)
                if partwise_data:
                    ws_part = writer.book.create_sheet("Part-Wise Tracking")
                    
                    part_header_fill = PatternFill(start_color="D6EAF8", end_color="D6EAF8", fill_type="solid") # Light blue
                    cust_subtotal_fill = PatternFill(start_color="D5F5E3", end_color="D5F5E3", fill_type="solid") # Light green
                    part_grand_fill = PatternFill(start_color="FDEBD0", end_color="FDEBD0", fill_type="solid") # Light peach

                    # Column order matching Sheet 1 (Stock Ledger):
                    # Identity → Opening → Shipment → Consumption (Despatch) → Closing
                    part_headers = [
                        "Code No.", "Customer Name", "Part Number", "Invoice No.", "Invoice Date",
                        "Opening Qty", "Opening FC", "Opening INR",
                        "CCPL to WH Qty", "CCPL to WH FC Value", "CCPL to WH INR Value",
                        "WH to Customer Qty", "WH to Customer FC Value", "WH to Customer INR Value",
                        "Closing Qty", "Closing FC", "Closing INR",
                    ]
                    part_keys = [
                        'Code No. Stock AC', 'Party Name', 'Part Number', 'Invoice No.', 'Invoice Date',
                        'Opening Qty', 'Opening FC', 'Opening INR',
                        'Shipment Qty', 'Shipment FC', 'Shipment INR',
                        'Qty', 'FC Value', 'INR Value',
                        'Closing Qty', 'Closing FC', 'Closing INR',
                    ]
                    part_col_widths = [
                        14, 25, 18, 18, 14,
                        12, 14, 14,
                        12, 14, 14,
                        12, 14, 14,
                        12, 14, 14,
                    ]

                    for col_idx, h in enumerate(part_headers, 1):
                        cell = ws_part.cell(row=1, column=col_idx, value=h)
                        cell.font = header_font
                        cell.fill = header_fill
                        cell.alignment = Alignment(horizontal="center")

                    invoice_detail_fill = PatternFill(start_color="E8DAEF", end_color="E8DAEF", fill_type="solid")  # Light lavender
                    invoice_detail_font = Font(italic=True)

                    current_row = 2
                    for row_data in partwise_data:
                        row_type = row_data.get('_row_type', 'detail')

                        for col_idx, key in enumerate(part_keys, 1):
                            val = row_data.get(key, '')
                            cell = ws_part.cell(row=current_row, column=col_idx, value=val if val != '' else None)

                            # Apply styling based on the row type
                            if row_type == 'part_header':
                                cell.font = bold_font
                                cell.fill = part_header_fill
                            elif row_type == 'customer_subtotal':
                                cell.font = bold_font
                                cell.fill = cust_subtotal_fill
                                cell.border = thin_border
                            elif row_type == 'invoice_detail':
                                cell.font = invoice_detail_font
                                cell.fill = invoice_detail_fill
                            elif row_type == 'part_grand_total':
                                cell.font = bold_font
                                cell.fill = part_grand_fill
                                cell.border = thin_border

                        current_row += 1

                    for i, w in enumerate(part_col_widths, 1):
                        ws_part.column_dimensions[get_column_letter(i)].width = w

                    ws_part.freeze_panes = "A2"
                else:
                    # Create empty sheet if no data
                    pd.DataFrame(columns=[
                        "Code No.", "Customer Name", "Part Number", "Invoice No.", "Invoice Date",
                        "Opening Qty", "Opening FC", "Opening INR",
                        "CCPL to WH Qty", "CCPL to WH FC Value", "CCPL to WH INR Value",
                        "WH to Customer Qty", "WH to Customer FC Value", "WH to Customer INR Value",
                        "Closing Qty", "Closing FC", "Closing INR",
                    ]).to_excel(writer, index=False, sheet_name="Part-Wise Tracking")

            # ── Auto-refresh PartWiseTracking DB table ──
            from sales.models import PartWiseTracking

            def _to_decimal_or_none(val):
                """Convert a value to Decimal or None (for empty strings)."""
                if val == '' or val is None:
                    return None
                try:
                    return round(float(val), 4)
                except (TypeError, ValueError):
                    return None

            try:
                # Clear existing records and bulk-insert fresh data
                PartWiseTracking.objects.all().delete()

                if partwise_data:
                    rows_to_create = []
                    for row_data in partwise_data:
                        row_type = row_data.get('_row_type', '')
                        if row_type not in ('customer_subtotal', 'invoice_detail', 'part_grand_total'):
                            continue  # Skip headers, spacers

                        rows_to_create.append(PartWiseTracking(
                            row_type=row_type,
                            customer_code=row_data.get('Code No. Stock AC', '') or '',
                            customer_name=(row_data.get('Party Name', '') or '').replace(' — Subtotal', ''),
                            part_number=row_data.get('Part Number', '') or '',
                            invoice_number=row_data.get('Invoice No.', '') or '',
                            invoice_date=row_data.get('Invoice Date', '') or '',
                            opening_qty=_to_decimal_or_none(row_data.get('Opening Qty')),
                            opening_fc=_to_decimal_or_none(row_data.get('Opening FC')),
                            opening_inr=_to_decimal_or_none(row_data.get('Opening INR')),
                            ccpl_to_wh_qty=_to_decimal_or_none(row_data.get('Shipment Qty')),
                            ccpl_to_wh_fc=_to_decimal_or_none(row_data.get('Shipment FC')),
                            ccpl_to_wh_inr=_to_decimal_or_none(row_data.get('Shipment INR')),
                            wh_to_customer_qty=_to_decimal_or_none(row_data.get('Qty')),
                            wh_to_customer_fc=_to_decimal_or_none(row_data.get('FC Value')),
                            wh_to_customer_inr=_to_decimal_or_none(row_data.get('INR Value')),
                            closing_qty=_to_decimal_or_none(row_data.get('Closing Qty')),
                            closing_fc=_to_decimal_or_none(row_data.get('Closing FC')),
                            closing_inr=_to_decimal_or_none(row_data.get('Closing INR')),
                            from_date=from_date,
                            to_date=to_date,
                        ))

                    if rows_to_create:
                        PartWiseTracking.objects.bulk_create(rows_to_create)
                        logger.info(f"PartWiseTracking table refreshed: {len(rows_to_create)} rows created")

            except Exception as refresh_err:
                # Don't fail the export if the DB refresh fails
                logger.error(f"Error refreshing PartWiseTracking table: {refresh_err}")

            return response

        except Exception as e:
            logger.error(f"Error exporting stock ledger: {e}")
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
