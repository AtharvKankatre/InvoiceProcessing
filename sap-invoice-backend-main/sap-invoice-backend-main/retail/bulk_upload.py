"""
Bulk FX Reconciliation Upload Views.

Provides:
  GET  /api/retail/bulk-template/  â€” Download a blank Excel template
  POST /api/retail/bulk-upload/    â€” Upload an Excel file to process multiple FX entries
"""

import io
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from django.db import transaction
from django.http import HttpResponse
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from sales.models import Invoice, InvoiceEntryConsumption, InvoiceRetailPartMap
from retail.models import InvoiceEntry
from user.models import User


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Constants
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

MAX_FILE_SIZE_MB = 50
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
MAX_ROWS = 500

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Helpers
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

TEMPLATE_COLUMNS = [
    "part_number",
    "date",
    "qty",
    "usd_rate",
    "conversion_rate",
    "retail_invoice_number",
]

COLUMN_DESCRIPTIONS = [
    "Retail Part Number (e.g. RETAIL-X100)",
    "Date (YYYY-MM-DD)",
    "Quantity to dispatch",
    "Selling USD rate per unit",
    "INR/USD Conversion (FX) rate",
    "Retail Invoice Number (must be unique)",
]


def _to_decimal(value, places='0.0001'):
    """Safely convert a value to Decimal."""
    if value is None or str(value).strip() == '':
        return None  # Return None so the caller can tell "missing" from "zero"
    try:
        return Decimal(str(value)).quantize(Decimal(places), rounding=ROUND_HALF_UP)
    except Exception:
        return None


def _parse_date(value):
    """Parse a date value from Excel (could be datetime object or string)."""
    if value is None:
        return None
    # Check datetime BEFORE date â€” datetime is a subclass of date,
    # so isinstance(datetime_obj, date) is True.
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    date_str = str(value).strip()
    for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y', '%m/%d/%Y'):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def _validate_row(row_num, row_data):
    """
    Validate a single row dict.  Returns (cleaned_data, error_string).
    If error_string is not None the row is invalid.
    """
    errors = []

    part_number = str(row_data.get("part_number") or "").strip()
    if not part_number:
        errors.append("part_number is required")

    row_date = _parse_date(row_data.get("date"))
    if row_date is None:
        errors.append("date is required (format: YYYY-MM-DD)")

    qty_raw = row_data.get("qty")
    qty = _to_decimal(qty_raw, '1')
    if qty is None or qty <= 0:
        errors.append("qty must be a positive number")

    usd_rate = _to_decimal(row_data.get("usd_rate"))
    if usd_rate is None:
        errors.append("usd_rate is required and must be a number")

    conversion_rate = _to_decimal(row_data.get("conversion_rate"))
    if conversion_rate is None:
        errors.append("conversion_rate is required and must be a number")

    retail_inv = str(row_data.get("retail_invoice_number") or "").strip()
    if not retail_inv:
        errors.append("retail_invoice_number is required")

    if errors:
        return None, f"Row {row_num}: {'; '.join(errors)}"

    # Auto-calculate inr_rate = usd_rate Ã— conversion_rate
    inr_rate = (usd_rate * conversion_rate).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)

    return {
        "part_number": part_number,
        "date": row_date,
        "qty": qty,
        "usd_rate": usd_rate,
        "inr_rate": inr_rate,
        "conversion_rate": conversion_rate,
        "retail_invoice_number": retail_inv,
    }, None


def _process_single_row(row_num, cleaned, user_instance):
    """
    Process one validated row using FIFO logic.
    This mirrors InvoiceEntryCreateView.create but without manual invoice selection.

    Returns (success_bool, message_string).
    """

    part_number = cleaned["part_number"]
    qty_to_consume = cleaned["qty"]
    conversion_rate = cleaned["conversion_rate"]
    retail_dollar_rate = cleaned["usd_rate"]
    retail_inr_rate = cleaned["inr_rate"]  # auto-calculated: usd_rate Ã— conversion_rate
    entry_date = cleaned["date"]
    retail_invoice_number = cleaned["retail_invoice_number"]

    # ── Duplicate check (invoice + part combo) ──
    if InvoiceEntry.objects.filter(retail_invoice_number=retail_invoice_number, part_number=part_number).exists():
        return False, f"retail_invoice_number '{retail_invoice_number}' with part '{part_number}' already exists"

    # â”€â”€ Part mapping â”€â”€
    part_mapping = InvoiceRetailPartMap.objects.filter(
        retail_part_number=part_number
    ).first()

    if part_mapping:
        sale_part_number = part_mapping.sale_part_number
    else:
        # Fallback: assume retail part = sale part
        sale_part_number = part_number

    # â”€â”€ FIFO selection â”€â”€
    matching_invoices = Invoice.objects.filter(
        part_number=sale_part_number,
        qty__gt=0,
    ).order_by("date", "id")

    total_available = sum(inv.qty for inv in matching_invoices)
    if total_available < qty_to_consume:
        return False, f"Not enough stock. Requested: {qty_to_consume}, Available: {total_available}"

    # â”€â”€ Consume from invoices (FIFO) â”€â”€
    qty_remaining = qty_to_consume
    consumed_records = []

    for invoice in matching_invoices:
        if qty_remaining == 0:
            break

        consumed_qty = min(qty_remaining, Decimal(invoice.qty))
        qty_remaining -= consumed_qty
        invoice.qty -= int(consumed_qty)
        invoice.created_by = user_instance
        invoice.save()
        consumed_records.append((invoice, consumed_qty))

    # â”€â”€ Build consumption data (same calculations as InvoiceEntryCreateView) â”€â”€
    consumption_data_list = []
    total_usd = Decimal('0')
    total_inr = Decimal('0')
    total_qty = Decimal('0')

    for invoice, consumed_qty in consumed_records:
        inv_dollar_rate = _safe_decimal(invoice.dollar_rate)
        inv_inr_rate = _safe_decimal(invoice.inr_rate)
        inv_conversion_rate = _safe_decimal(invoice.conversion_rate)
        dnd = _safe_decimal(invoice.dnd_charges)

        usd_rate = retail_dollar_rate

        # Value calculations
        base_value = consumed_qty * usd_rate
        taxable_value = base_value - dnd
        fc_value = taxable_value

        # INR received vs cost
        inr_received = consumed_qty * usd_rate * conversion_rate
        inr_cost = consumed_qty * inv_dollar_rate * inv_conversion_rate

        # Profit decomposition
        profit_absolute = inr_received - inr_cost
        selling_profit_inr = (usd_rate - inv_dollar_rate) * consumed_qty * conversion_rate
        fx_profit = inv_dollar_rate * consumed_qty * (conversion_rate - inv_conversion_rate)
        profit_fx_only = profit_absolute - selling_profit_inr - fx_profit
        selling_profit_usd = (usd_rate - inv_dollar_rate) * consumed_qty

        consumption_data_list.append({
            "invoice": invoice,
            "consumed_qty": consumed_qty,
            "selling_price_inr": (inv_inr_rate * consumed_qty).quantize(Decimal('0.01')),
            "profit_absolute": profit_absolute.quantize(Decimal('0.01')),
            "profit_selling_rate": selling_profit_usd.quantize(Decimal('0.01')),
            "profit_fx_rate": fx_profit.quantize(Decimal('0.01')),
            "profit_fx_only": profit_fx_only.quantize(Decimal('0.01')),
            "base_value": base_value.quantize(Decimal('0.01')),
            "dnd_charges": dnd.quantize(Decimal('0.01')),
            "taxable_value": taxable_value.quantize(Decimal('0.01')),
            "fc_value": fc_value.quantize(Decimal('0.01')),
            "fc_rate_with_discount": (fc_value / consumed_qty).quantize(Decimal('0.01')) if consumed_qty else Decimal('0'),
            "created_by": user_instance,
            "rate_sale_from_wh_per_unit": (inv_inr_rate / inv_conversion_rate).quantize(Decimal('0.01')) if inv_conversion_rate else Decimal('0'),
            "rate_sale_from_wh": retail_dollar_rate,
            "diff": ((inv_inr_rate / inv_conversion_rate) - retail_dollar_rate).quantize(Decimal('0.01')) if inv_conversion_rate else Decimal('0'),
            "surcharge": (((inv_inr_rate / inv_conversion_rate) - retail_dollar_rate) * consumed_qty * conversion_rate).quantize(Decimal('0.01')) if inv_conversion_rate else Decimal('0'),
        })

        total_usd += inv_dollar_rate * consumed_qty
        total_inr += inv_inr_rate * consumed_qty
        total_qty += consumed_qty

    # â”€â”€ Create InvoiceEntry â”€â”€
    usd_total_final = (retail_dollar_rate * qty_to_consume).quantize(Decimal('0.01'))
    inr_total_final = (retail_inr_rate * qty_to_consume).quantize(Decimal('0.01'))

    invoice_entry = InvoiceEntry.objects.create(
        part_number=part_number,
        date=entry_date,
        qty=int(qty_to_consume),
        usd_rate=retail_dollar_rate,
        usd_total=usd_total_final,
        inr_rate=retail_inr_rate,
        inr_total=inr_total_final,
        conversion_rate=conversion_rate,
        retail_invoice_number=retail_invoice_number,
        created_by=user_instance,
    )

    # â”€â”€ Create consumption records â”€â”€
    for data in consumption_data_list:
        InvoiceEntryConsumption.objects.create(
            invoice_entry=invoice_entry, **data
        )

    # Clean up any orphan consumption records (matches original InvoiceEntryCreateView)
    InvoiceEntryConsumption.objects.filter(invoice_entry=None).update(
        invoice_entry=invoice_entry
    )

    return True, f"Processed successfully (consumed from {len(consumed_records)} invoice(s))"


def _safe_decimal(value):
    """Convert DB value to Decimal, returning 0 for None."""
    if value is None:
        return Decimal('0')
    return Decimal(str(value))


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Views
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class BulkTemplateView(APIView):
    """GET â€” Download a blank Excel template for bulk FX upload."""

    def get(self, request):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "FX Bulk Upload"

        # Styles
        header_font = Font(bold=True, color="FFFFFF", size=12)
        header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
        desc_font = Font(italic=True, color="808080", size=10)
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin'),
        )

        # Row 1: Headers
        for col_idx, header in enumerate(TEMPLATE_COLUMNS, start=1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal='center')
            cell.border = thin_border

        # Row 2: Descriptions (helper row)
        for col_idx, desc in enumerate(COLUMN_DESCRIPTIONS, start=1):
            cell = ws.cell(row=2, column=col_idx, value=desc)
            cell.font = desc_font
            cell.alignment = Alignment(horizontal='center')

        # Column widths
        widths = [25, 15, 12, 15, 18, 28]
        for col_idx, w in enumerate(widths, start=1):
            ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = w

        # Save to buffer
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="fx_bulk_upload_template.xlsx"'
        return response


class BulkUploadView(APIView):
    """POST â€” Upload Excel file and process each row as an FX reconciliation entry."""

    parser_classes = [MultiPartParser]

    def post(self, request):
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            return Response(
                {"error": "No file uploaded. Please attach an Excel file."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verify file extension
        if not uploaded_file.name.endswith(('.xlsx', '.xls')):
            return Response(
                {"error": "Invalid file format. Please upload an .xlsx file."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # File size check
        if uploaded_file.size > MAX_FILE_SIZE_BYTES:
            return Response(
                {"error": f"File too large. Maximum allowed size is {MAX_FILE_SIZE_MB}MB."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user_instance = User.objects.get(id=request.user.id)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Parse the Excel file
        try:
            wb = openpyxl.load_workbook(uploaded_file, read_only=True, data_only=True)
            ws = wb.active
        except Exception as e:
            return Response(
                {"error": f"Failed to read Excel file: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Read headers from row 1
        raw_headers = [str(cell.value or '').strip().lower() for cell in ws[1]]
        
        # Mapping from human readable headers to internal names
        HEADER_MAPPING = {
            desc.lower(): internal
            for desc, internal in zip(COLUMN_DESCRIPTIONS, TEMPLATE_COLUMNS)
        }
        
        # Translate anything that looks like a description back into the internal column name
        headers = [HEADER_MAPPING.get(h, h) for h in raw_headers]

        # Validate headers
        missing_headers = [col for col in TEMPLATE_COLUMNS if col not in headers]
        if missing_headers:
            return Response(
                {"error": f"Missing required columns: {', '.join(missing_headers)}. "
                          f"Expected columns: {', '.join(TEMPLATE_COLUMNS)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        col_indices = {col: headers.index(col) for col in TEMPLATE_COLUMNS}

        # Process rows (skip row 1 = headers, skip row 2 if it looks like descriptions)
        results = []
        successful = 0
        failed = 0
        total_rows = 0
        seen_invoice_numbers = {}  # Track invoice numbers within THIS upload file

        for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            # Skip completely empty rows
            if not row or all(cell is None or str(cell).strip() == '' for cell in row):
                continue

            # Skip the description row (row 2 if it starts with text like "Retail Part Number")
            first_val = str(row[0] or "").strip().lower() if row else ""
            if row_idx == 2 and ("retail part" in first_val or "example" in first_val
                                 or "description" in first_val or "e.g." in first_val):
                continue

            total_rows += 1
            row_num = total_rows  # User-facing row number

            # Check max row limit
            if total_rows > MAX_ROWS:
                failed += 1
                results.append({
                    "row": row_num,
                    "status": "failed",
                    "retail_invoice_number": "",
                    "error": f"Row {row_num}: Exceeds maximum limit of {MAX_ROWS} rows per upload. Please split into multiple files.",
                })
                continue

            # Extract row data
            row_data = {}
            for col_name, col_idx in col_indices.items():
                row_data[col_name] = row[col_idx] if col_idx < len(row) else None

            # Check for duplicate invoice number within THIS file
            inv_num = str(row_data.get("retail_invoice_number") or "").strip()
            if inv_num and inv_num in seen_invoice_numbers:
                failed += 1
                results.append({
                    "row": row_num,
                    "status": "failed",
                    "retail_invoice_number": inv_num,
                    "error": f"Row {row_num}: Duplicate retail_invoice_number '{inv_num}' in this file (first appeared in row {seen_invoice_numbers[inv_num]})",
                })
                continue
            if inv_num:
                seen_invoice_numbers[inv_num] = row_num

            # Validate
            cleaned, error = _validate_row(row_num, row_data)
            if error:
                failed += 1
                results.append({
                    "row": row_num,
                    "status": "failed",
                    "retail_invoice_number": str(row_data.get("retail_invoice_number", "")),
                    "error": error,
                })
                continue

            # Process within its own atomic transaction
            try:
                with transaction.atomic():
                    success, message = _process_single_row(row_num, cleaned, user_instance)

                if success:
                    successful += 1
                    results.append({
                        "row": row_num,
                        "status": "success",
                        "retail_invoice_number": cleaned["retail_invoice_number"],
                        "message": message,
                    })
                else:
                    failed += 1
                    results.append({
                        "row": row_num,
                        "status": "failed",
                        "retail_invoice_number": cleaned["retail_invoice_number"],
                        "error": f"Row {row_num}: {message}",
                    })
            except Exception as e:
                failed += 1
                results.append({
                    "row": row_num,
                    "status": "failed",
                    "retail_invoice_number": cleaned["retail_invoice_number"],
                    "error": f"Row {row_num}: {str(e)}",
                })

        if total_rows == 0:
            return Response(
                {"error": "No data rows found in the uploaded file. Please add data starting from row 3 (row 2 is for descriptions)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({
            "total_rows": total_rows,
            "successful": successful,
            "failed": failed,
            "results": results,
        }, status=status.HTTP_200_OK)


class BulkPreviewView(APIView):
    """POST — Upload Excel file and return parsed rows with validation and stock availability without saving."""
    parser_classes = [MultiPartParser]

    def post(self, request):
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            return Response(
                {"error": "No file uploaded. Please attach an Excel file."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verify file extension
        if not uploaded_file.name.endswith(('.xlsx', '.xls')):
            return Response(
                {"error": "Invalid file format. Please upload an .xlsx file."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if uploaded_file.size > MAX_FILE_SIZE_BYTES:
            return Response(
                {"error": f"File too large. Maximum allowed size is {MAX_FILE_SIZE_MB}MB."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            wb = openpyxl.load_workbook(uploaded_file, read_only=True, data_only=True)
            ws = wb.active
        except Exception as e:
            return Response(
                {"error": f"Failed to read Excel file: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        raw_headers = [str(cell.value or '').strip().lower() for cell in ws[1]]
        
        HEADER_MAPPING = {
            desc.lower(): internal
            for desc, internal in zip(COLUMN_DESCRIPTIONS, TEMPLATE_COLUMNS)
        }
        headers = [HEADER_MAPPING.get(h, h) for h in raw_headers]

        missing_headers = [col for col in TEMPLATE_COLUMNS if col not in headers]
        if missing_headers:
            return Response(
                {"error": f"Missing required columns: {', '.join(missing_headers)}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        col_indices = {col: headers.index(col) for col in TEMPLATE_COLUMNS}
        
        rows_data = []
        total_rows = 0
        seen_invoice_numbers = {}
        part_numbers = set()

        # Step 1: Parse and validate format
        for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            if not row or all(cell is None or str(cell).strip() == '' for cell in row):
                continue
                
            first_val = str(row[0] or "").strip().lower() if row else ""
            if row_idx == 2 and ("retail part" in first_val or "example" in first_val
                                 or "description" in first_val or "e.g." in first_val):
                continue

            total_rows += 1
            row_num = total_rows
            
            row_dict = {}
            for col_name, col_idx in col_indices.items():
                row_dict[col_name] = row[col_idx] if col_idx < len(row) else None
                
            # Date serialization handle
            if isinstance(row_dict.get('date'), (datetime, date)):
                row_dict['date'] = row_dict['date'].strftime('%Y-%m-%d')
            elif row_dict.get('date'):
                # Try to parse and re-format
                parsed = _parse_date(row_dict['date'])
                row_dict['date'] = parsed.strftime('%Y-%m-%d') if parsed else row_dict['date']
                
            # Decimal to string mapping
            for key in ['qty', 'usd_rate', 'conversion_rate']:
                if row_dict.get(key) is not None:
                    row_dict[key] = str(row_dict[key])
                    
            if row_dict.get('part_number'):
                part_numbers.add(str(row_dict['part_number']).strip())
                
            rows_data.append({
                "row": row_num,
                "data": row_dict
            })
            
        # Step 2: Live Stock checking and DB validation
        # Pre-fetch all available wholesale invoices for the needed parts
        part_inventory = {}
        for part in part_numbers:
            mapping = InvoiceRetailPartMap.objects.filter(retail_part_number=part).first()
            sale_part = mapping.sale_part_number if mapping else part
            
            invoices = Invoice.objects.filter(part_number=sale_part, qty__gt=0).order_by("date", "id")
            total_qty = sum(inv.qty for inv in invoices)
            
            part_inventory[part] = {
                "sale_part_number": sale_part,
                "available_qty": total_qty,
                "invoices": [
                    {
                        "id": inv.id,
                        "invoice_number": inv.invoice_number,
                        "available_qty": inv.qty,
                        "dollar_rate": float(inv.dollar_rate) if inv.dollar_rate else 0,
                        "conversion_rate": float(inv.conversion_rate) if inv.conversion_rate else 0,
                        "date": inv.date.strftime('%Y-%m-%d') if inv.date else ""
                    } for inv in invoices
                ]
            }

        # Step 3: Decorate rows with errors / readiness
        results = []
        consumed_qty_tracker = {}  # Track cumulative consumption per part for cross-row validation
        
        for item in rows_data:
            row_num = item["row"]
            row_data = item["data"]
            
            is_valid = True
            errors = {}
            
            # Format validation
            cleaned, format_error = _validate_row(row_num, row_data)
            if format_error:
                is_valid = False
                errors["format"] = format_error
            
            # Application Logic Validation (Duplicate — invoice + part combo)
            inv_num = str(row_data.get("retail_invoice_number") or "").strip()
            part_for_dupe = str(row_data.get("part_number") or "").strip()
            dupe_key = f"{inv_num}__{part_for_dupe}"
            if inv_num:
                if dupe_key in seen_invoice_numbers:
                    is_valid = False
                    errors["retail_invoice_number"] = f"Duplicate within file (row {seen_invoice_numbers[dupe_key]})"
                elif InvoiceEntry.objects.filter(retail_invoice_number=inv_num, part_number=part_for_dupe).exists():
                    is_valid = False
                    errors["retail_invoice_number"] = "Already exists in database"
                else:
                    seen_invoice_numbers[dupe_key] = row_num
            else:
                 is_valid = False
                 errors["retail_invoice_number"] = "Missing"
                 
            # Application Logic Validation (Stock) — cumulative across rows
            part_num = str(row_data.get("part_number") or "").strip()
            req_qty = cleaned["qty"] if cleaned and cleaned.get("qty") else 0
            
            if part_num:
                if part_num not in part_inventory:
                    is_valid = False
                    errors["part_number"] = "Part number not found in system"
                else:
                    total_avail = part_inventory[part_num]["available_qty"]
                    already_consumed = consumed_qty_tracker.get(part_num, 0)
                    remaining = total_avail - already_consumed
                    
                    if req_qty and req_qty > remaining:
                        is_valid = False
                        errors["qty"] = f"Not enough stock. Need: {req_qty}, Only {remaining} left (total: {total_avail})"
                    elif req_qty:
                        consumed_qty_tracker[part_num] = already_consumed + int(req_qty)
            
            results.append({
                "row_id": row_num,
                "data": row_data,
                "errors": errors,
                "is_valid": is_valid
            })
            
        return Response({
            "rows": results,
            "part_inventory": part_inventory,
        }, status=status.HTTP_200_OK)


class BulkCommitView(APIView):
    """POST — Accepts a JSON array of validated rows and commits them atomically."""
    
    def post(self, request):
        try:
            user_instance = User.objects.get(id=request.user.id)
        except User.DoesNotExist:
            return Response({"error": "User not found."}, status=status.HTTP_401_UNAUTHORIZED)
            
        rows = request.data.get("rows", [])
        if not isinstance(rows, list) or not rows:
            return Response({"error": "No rows provided to commit."}, status=status.HTTP_400_BAD_REQUEST)
        
        if len(rows) > MAX_ROWS:
            return Response({"error": f"Too many rows. Maximum is {MAX_ROWS}."}, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate payload shape before processing
        for idx, item in enumerate(rows):
            if not isinstance(item, dict) or "data" not in item or "row_id" not in item:
                return Response({"error": f"Invalid payload shape at index {idx}."}, status=status.HTTP_400_BAD_REQUEST)
            sel_invs = item.get("selected_invoices")
            if sel_invs is not None:
                if not isinstance(sel_invs, list):
                    return Response({"error": f"Row {item.get('row_id', idx)}: selected_invoices must be a list."}, status=status.HTTP_400_BAD_REQUEST)
                for si in sel_invs:
                    if not isinstance(si, dict) or "invoice_id" not in si or "qty" not in si:
                        return Response({"error": f"Row {item.get('row_id', idx)}: invalid selected_invoices entry."}, status=status.HTTP_400_BAD_REQUEST)
                    try:
                        int(si["invoice_id"])
                        float(si["qty"])
                    except (ValueError, TypeError):
                        return Response({"error": f"Row {item.get('row_id', idx)}: invoice_id must be integer and qty must be number."}, status=status.HTTP_400_BAD_REQUEST)
            
        successful = 0
        failed = 0
        results = []
        
        try:
            # Atomic transaction spanning ALL rows
            with transaction.atomic():
                for item in rows:
                    row_data = item.get("data", {})
                    row_id = item.get("row_id", 0)
                    selected_invoices = item.get("selected_invoices", None)
                    
                    cleaned, error = _validate_row(row_id, row_data)
                    if error:
                        raise Exception(f"Row {row_id} validation failed: {error}")
                        
                    part_number = cleaned["part_number"]
                    qty_to_consume = cleaned["qty"]
                    conversion_rate = cleaned["conversion_rate"]
                    retail_dollar_rate = cleaned["usd_rate"]
                    retail_inr_rate = cleaned["inr_rate"]
                    entry_date = cleaned["date"]
                    retail_invoice_number = cleaned["retail_invoice_number"]
                    
                    if InvoiceEntry.objects.filter(retail_invoice_number=retail_invoice_number, part_number=part_number).exists():
                        raise Exception(f"Row {row_id}: retail_invoice_number '{retail_invoice_number}' with part '{part_number}' already exists in database.")
                        
                    part_mapping = InvoiceRetailPartMap.objects.filter(retail_part_number=part_number).first()
                    sale_part_number = part_mapping.sale_part_number if part_mapping else part_number
                    
                    # Consume Logic (Custom or FIFO)
                    consumed_records = []
                    
                    if selected_invoices and isinstance(selected_invoices, list) and len(selected_invoices) > 0:
                        total_selected_qty = Decimal('0')
                        for selection in selected_invoices:
                            inv_id = selection.get("invoice_id")
                            sel_qty = Decimal(str(selection.get("qty", 0)))
                            if not inv_id or sel_qty <= 0:
                                continue
                            try:
                                invoice = Invoice.objects.get(id=inv_id, part_number=sale_part_number, qty__gt=0)
                            except Invoice.DoesNotExist:
                                raise Exception(f"Row {row_id}: Invoice ID {inv_id} not found or empty.")
                                
                            if sel_qty > invoice.qty:
                                raise Exception(f"Row {row_id}: Invoice {invoice.invoice_number} has only {invoice.qty} available.")
                                
                            invoice.qty -= int(sel_qty)
                            invoice.created_by = user_instance
                            invoice.save()
                            consumed_records.append((invoice, sel_qty))
                            total_selected_qty += sel_qty
                            
                        if total_selected_qty != qty_to_consume:
                            raise Exception(f"Row {row_id}: Selected quantity ({total_selected_qty}) != Requested quantity ({qty_to_consume}).")
                    else:
                        # FIFO
                        matching_invoices = Invoice.objects.filter(part_number=sale_part_number, qty__gt=0).order_by("date", "id")
                        total_available = sum(inv.qty for inv in matching_invoices)
                        if total_available < qty_to_consume:
                            raise Exception(f"Row {row_id}: Not enough stock. Requested {qty_to_consume}, Available {total_available}.")
                            
                        qty_remaining = qty_to_consume
                        for invoice in matching_invoices:
                            if qty_remaining == 0: break
                            consumed_qty = min(qty_remaining, Decimal(invoice.qty))
                            qty_remaining -= consumed_qty
                            invoice.qty -= int(consumed_qty)
                            invoice.created_by = user_instance
                            invoice.save()
                            consumed_records.append((invoice, consumed_qty))
                            
                    # Calculate values
                    consumption_data_list = []
                    for invoice, consumed_qty in consumed_records:
                        inv_dollar_rate = _safe_decimal(invoice.dollar_rate)
                        inv_inr_rate = _safe_decimal(invoice.inr_rate)
                        inv_conversion_rate = _safe_decimal(invoice.conversion_rate)
                        dnd = _safe_decimal(invoice.dnd_charges)
                        usd_rate = retail_dollar_rate
                        
                        base_value = consumed_qty * usd_rate
                        taxable_value = base_value - dnd
                        fc_value = taxable_value
                        inr_received = consumed_qty * usd_rate * conversion_rate
                        inr_cost = consumed_qty * inv_dollar_rate * inv_conversion_rate
                        
                        profit_absolute = inr_received - inr_cost
                        selling_profit_inr = (usd_rate - inv_dollar_rate) * consumed_qty * conversion_rate
                        fx_profit = inv_dollar_rate * consumed_qty * (conversion_rate - inv_conversion_rate)
                        profit_fx_only = profit_absolute - selling_profit_inr - fx_profit
                        selling_profit_usd = (usd_rate - inv_dollar_rate) * consumed_qty
                        
                        consumption_data_list.append({
                            "invoice": invoice,
                            "consumed_qty": consumed_qty,
                            "selling_price_inr": (inv_inr_rate * consumed_qty).quantize(Decimal('0.01')),
                            "profit_absolute": profit_absolute.quantize(Decimal('0.01')),
                            "profit_selling_rate": selling_profit_usd.quantize(Decimal('0.01')),
                            "profit_fx_rate": fx_profit.quantize(Decimal('0.01')),
                            "profit_fx_only": profit_fx_only.quantize(Decimal('0.01')),
                            "base_value": base_value.quantize(Decimal('0.01')),
                            "dnd_charges": dnd.quantize(Decimal('0.01')),
                            "taxable_value": taxable_value.quantize(Decimal('0.01')),
                            "fc_value": fc_value.quantize(Decimal('0.01')),
                            "fc_rate_with_discount": (fc_value / consumed_qty).quantize(Decimal('0.01')) if consumed_qty else Decimal('0'),
                            "created_by": user_instance,
                            "rate_sale_from_wh_per_unit": (inv_inr_rate / inv_conversion_rate).quantize(Decimal('0.01')) if inv_conversion_rate else Decimal('0'),
                            "rate_sale_from_wh": retail_dollar_rate,
                            "diff": ((inv_inr_rate / inv_conversion_rate) - retail_dollar_rate).quantize(Decimal('0.01')) if inv_conversion_rate else Decimal('0'),
                            "surcharge": (((inv_inr_rate / inv_conversion_rate) - retail_dollar_rate) * consumed_qty * conversion_rate).quantize(Decimal('0.01')) if inv_conversion_rate else Decimal('0'),
                        })
                        
                    # Save InvoiceEntry
                    usd_total_final = (retail_dollar_rate * qty_to_consume).quantize(Decimal('0.01'))
                    inr_total_final = (retail_inr_rate * qty_to_consume).quantize(Decimal('0.01'))
                    invoice_entry = InvoiceEntry.objects.create(
                        part_number=part_number, date=entry_date, qty=int(qty_to_consume),
                        usd_rate=retail_dollar_rate, usd_total=usd_total_final,
                        inr_rate=retail_inr_rate, inr_total=inr_total_final,
                        conversion_rate=conversion_rate, retail_invoice_number=retail_invoice_number,
                        created_by=user_instance,
                    )
                    
                    # Consumptions
                    for data in consumption_data_list:
                        InvoiceEntryConsumption.objects.create(invoice_entry=invoice_entry, **data)
                        
                    successful += 1
                    results.append({"row_id": row_id, "status": "success", "retail_invoice_number": retail_invoice_number})

        except Exception as e:
            # Trigger rollback for ALL successfully processed rows so far
            return Response({"error": str(e), "batch_status": "rolled_back"}, status=status.HTTP_400_BAD_REQUEST)
            
        return Response({
            "successful": successful,
            "failed": failed,
            "results": results,
            "message": f"Successfully processed {successful} rows."
        }, status=status.HTTP_200_OK)

