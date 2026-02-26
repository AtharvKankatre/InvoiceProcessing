import os

bulk_upload_path = r"d:\Inpinite\InvoiceTest\sap-invoice-backend-main\sap-invoice-backend-main\retail\bulk_upload.py"

views_code = """

class BulkPreviewView(APIView):
    \"\"\"POST — Upload Excel file and return parsed rows with validation and stock availability without saving.\"\"\"
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

        headers = [str(cell.value or '').strip().lower() for cell in ws[1]]
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
            
            # Application Logic Validation (Duplicate)
            inv_num = str(row_data.get("retail_invoice_number") or "").strip()
            if inv_num:
                if inv_num in seen_invoice_numbers:
                    is_valid = False
                    errors["retail_invoice_number"] = f"Duplicate within file (row {seen_invoice_numbers[inv_num]})"
                elif InvoiceEntry.objects.filter(retail_invoice_number=inv_num).exists():
                    is_valid = False
                    errors["retail_invoice_number"] = "Already exists in database"
                else:
                    seen_invoice_numbers[inv_num] = row_num
            else:
                 is_valid = False
                 errors["retail_invoice_number"] = "Missing"
                 
            # Application Logic Validation (Stock)
            part_num = str(row_data.get("part_number") or "").strip()
            req_qty = cleaned["qty"] if cleaned and cleaned.get("qty") else 0
            
            if part_num:
                if part_num not in part_inventory:
                    is_valid = False
                    errors["part_number"] = "Part number not found in system"
                else:
                    avail_qty = part_inventory[part_num]["available_qty"]
                    if req_qty and req_qty > avail_qty:
                        is_valid = False
                        errors["qty"] = f"Not enough stock. Requested: {req_qty}, Available: {avail_qty}"
            
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
    \"\"\"POST — Accepts a JSON array of validated rows and commits them atomically.\"\"\"
    
    def post(self, request):
        try:
            user_instance = User.objects.get(id=request.user.id)
        except User.DoesNotExist:
            return Response({"error": "User not found."}, status=status.HTTP_401_UNAUTHORIZED)
            
        rows = request.data.get("rows", [])
        if not isinstance(rows, list) or not rows:
            return Response({"error": "No rows provided to commit."}, status=status.HTTP_400_BAD_REQUEST)
            
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
                    
                    if InvoiceEntry.objects.filter(retail_invoice_number=retail_invoice_number).exists():
                        raise Exception(f"Row {row_id}: retail_invoice_number '{retail_invoice_number}' already exists in database.")
                        
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

"""

with open(bulk_upload_path, 'a') as f:
    f.write(views_code)
    
print("Appended views successfully")
