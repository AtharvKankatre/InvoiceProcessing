from django.core.exceptions import BadRequest
from django.db import transaction
from django.db.models import Count, Avg, Sum
from rest_framework import generics
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from sales.models import Invoice, InvoiceEntryConsumption, InvoiceRetailPartMap
from .models import InvoiceEntry
from .serializers import InvoiceEntrySerializer
import pandas as pd
from rest_framework.views import APIView
from django.http import HttpResponse
from user.models import User
from django.utils.dateparse import parse_datetime
from decimal import Decimal, getcontext, ROUND_HALF_UP
import traceback
from rest_framework.views import APIView

getcontext().prec = 10
getcontext().rounding = ROUND_HALF_UP


# class InvoiceEntryCreateView(generics.CreateAPIView):
#     queryset = InvoiceEntry.objects.all()
#     serializer_class = InvoiceEntrySerializer
#
#     @transaction.atomic
#     def create(self, request, *args, **kwargs):
#         try:
#             user_instance = User.objects.get(id=request.user.id)
#             serializer = self.get_serializer(data=request.data)
#             serializer.is_valid(raise_exception=True)
#
#             part_number = serializer.validated_data["part_number"]
#             qty_to_consume = serializer.validated_data["qty"]
#             conversion_rate = serializer.validated_data["conversion_rate"]
#             invoice_number = request.data.get("invoice_number", None)
#             retail_invoice_number = request.data.get("retail_invoice_number", None)
#             retail_dollar_rate = request.data.get('usd_rate', None)
#             if retail_dollar_rate is None:
#                 raise BadRequest("dollar_rate is required")
#             # retail_dollar_rate = Decimal(retail_dollar_rate)
#             # retail_dollar_rate = float(retail_dollar_rate)
#             # retail_dollar_rate = round(retail_dollar_rate, 4)
#             retail_inr_rate = request.data.get('inr_rate', None)
#             if retail_inr_rate is None:
#                 raise BadRequest('inr rate is required')
#             # retail_inr_rate = Decimal(retail_inr_rate)
#             # retail_inr_rate = float(retail_inr_rate)
#             # retail_inr_rate = round(retail_inr_rate, 4)
#             retail_dollar_rate = Decimal(str(retail_dollar_rate)).quantize(Decimal('0.0001'))
#             retail_inr_rate = Decimal(str(retail_inr_rate)).quantize(Decimal('0.0001'))
#             conversion_rate = Decimal(str(conversion_rate)).quantize(Decimal('0.0001'))
#
#
#             # find out part number receive in request belongs to
#             # which part number in the sales invoice.
#
#             try:
#                 part_mapping = InvoiceRetailPartMap.objects.get(
#                     retail_part_number=part_number
#                 )
#                 sale_part_number = part_mapping.sale_part_number
#             except InvoiceRetailPartMap.DoesNotExist:
#                 raise ValidationError(
#                     {
#                         "part_number": f"No mapping found for retail part '{part_number}'.",
#                     }
#                 )
#
#             # --- Invoice selection logic ---
#             # without retail part number
#             # if invoice_number:
#             #     matching_invoices = Invoice.objects.filter(
#             #         part_number=part_number, invoice_number=invoice_number, qty__gt=0
#             #     ).order_by("date", "id")
#             # else:
#             #     matching_invoices = Invoice.objects.filter(
#             #         part_number=part_number, qty__gt=0
#             #     ).order_by("date", "id")
#
#             # invoice selection with retail part number mapping
#             if invoice_number:
#                 matching_invoices = Invoice.objects.filter(
#                     part_number=sale_part_number,
#                     invoice_number=invoice_number,
#                     qty__gt=0,
#                 ).order_by("date", "id")
#             else:
#                 matching_invoices = Invoice.objects.filter(
#                     part_number=sale_part_number, qty__gt=0
#                 ).order_by("date", "id")
#
#             total_available_qty = sum(invoice.qty for invoice in matching_invoices)
#             if total_available_qty < qty_to_consume:
#                 raise ValidationError(
#                     {
#                         "qty": f"Not enough stock. Requested: {qty_to_consume}, Available: {total_available_qty}"
#                     }
#                 )
#
#             qty_remaining = qty_to_consume
#             consumed_records = []
#
#             for invoice in matching_invoices:
#                 if qty_remaining == 0:
#                     break
#
#                 consumed_qty = min(qty_remaining, invoice.qty)
#                 qty_remaining -= consumed_qty
#                 invoice.qty -= consumed_qty
#                 invoice.created_by = user_instance
#                 invoice.save()
#
#                 consumed_records.append((invoice, consumed_qty))
#
#             # Accumulators for weighted avg
#             total_usd = 0
#             total_inr = 0
#             total_qty = 0
#
#             # Prepare data for consumption entries
#             consumption_data = []
#
#             for invoice, consumed_qty in consumed_records:
#                 # usd_total = consumed_qty * invoice.dollar_rate
#                 # converted_inr_cost = usd_total * invoice.conversion_rate
#                 # final_inr_total = consumed_qty * invoice.inr_rate
#                 #
#                 # profit_absolute = final_inr_total - converted_inr_cost
#                 # fx_base_cost = usd_total * invoice.conversion_rate
#                 # fx_profit = fx_base_cost - converted_inr_cost
#                 # selling_profit = profit_absolute - fx_profit
#
#                 usd_total = consumed_qty * retail_dollar_rate
#                 #                converted_inr_cost = usd_total * invoice.conversion_rate
#                 #                final_inr_total = consumed_qty * invoice.inr_rate
#
#                 usd_rate = retail_dollar_rate
#                 dnd = invoice.dnd_charges or 0
#
#                 # 1. Base value before discounts
#                 base_value = consumed_qty * usd_rate
#
#                 # 2. Taxable value after D&D
#                 taxable_value = base_value - dnd
#
#                 # 3. Final FC value
#                 fc_value = taxable_value
#
#                 # 4. Converted INR cost
#                 # converted_inr_cost = fc_value * invoice.conversion_rate
#                 converted_inr_cost = fc_value * conversion_rate
#
#                 # 5. Final INR selling total
#                 # final_inr_total = consumed_qty * invoice.conversion_rate
#                 final_inr_total = consumed_qty * conversion_rate
#
#                 # 6. FX profit = benefit/loss due to difference in FX rate
#                 fx_profit = fc_value * (conversion_rate - invoice.conversion_rate)
#
#                 # 7. Total profit
#                 profit_absolute = final_inr_total - converted_inr_cost
#                 selling_profit = profit_absolute - fx_profit
#
#                 # FX profit = benefit/loss due to difference in FX rate
#                 fx_profit = usd_total * (conversion_rate - invoice.conversion_rate)
#
#                 # Overall profit
#                 # profit_absolute = final_inr_total - converted_inr_cost
#                 profit_absolute = invoice.inr_rate - final_inr_total
#                 selling_profit = profit_absolute - fx_profit
#
#                 # Weighted avg calculation
#                 total_usd += invoice.dollar_rate * consumed_qty
#                 total_inr += invoice.inr_rate * consumed_qty
#                 total_qty += consumed_qty
#
#                 # consumption_data.append(
#                 #     {
#                 #         "invoice": invoice,
#                 #         "consumed_qty": consumed_qty,
#                 #         "selling_price_inr": invoice.inr_rate,
#                 #         "profit_absolute": round(profit_absolute, 2),
#                 #         "profit_selling_rate": round(selling_profit, 2),
#                 #         "profit_fx_rate": round(fx_profit, 2),
#                 #         "profit_fx_only": round(
#                 #             profit_absolute - (selling_profit + fx_profit), 2
#                 #         ),
#                 #     }
#                 # )
#
#                 consumption_data.append(
#                     {
#                         "invoice": invoice,
#                         "consumed_qty": consumed_qty,
#                         "selling_price_inr": invoice.inr_rate * consumed_qty,
#                         "profit_absolute": round(profit_absolute, 2),
#                         # "profit_selling_rate": round(selling_profit, 2),
#                         "profit_selling_rate": round(usd_total- invoice.dollar_rate* qty_to_consume, 2),
#                         "profit_fx_rate": round(fx_profit, 2),
#                         "profit_fx_only": round(
#                             profit_absolute - (selling_profit + fx_profit), 2
#                         ),
#                         # Optional: log base/taxable/FC values for export
#                         "base_value": round(base_value, 2),
#                         "dnd_charges": round(dnd, 2),
#                         "taxable_value": round(taxable_value, 2),
#                         "fc_value": round(fc_value, 2),
#                         "fc_rate_with_discount": round(fc_value / consumed_qty, 2),
#                         "created_by": user_instance,
#                          "rate_sale_from_wh_per_unit": invoice.inr_rate / invoice.conversion_rate,
#                         "rate_sale_from_wh": retail_dollar_rate,
#                         "diff": (invoice.inr_rate / invoice.conversion_rate) - retail_dollar_rate,
#                         "surcharge": ((
#                                               invoice.inr_rate / invoice.conversion_rate) - retail_dollar_rate) * consumed_qty * conversion_rate,
#                     }
#                 )
#
#             # Save invoice entry first
#             avg_usd_rate = round(total_usd / total_qty, 2)
#             avg_inr_rate = round(total_inr / total_qty, 2)
#             # usd_total_final = round(avg_usd_rate * total_qty, 2)
#             # usd_total_final = round(total)
#             usd_total_final = retail_dollar_rate * qty_to_consume
#             inr_total_final = round(usd_total_final * conversion_rate, 2)
#
#             invoice_entry = serializer.save(
#                 # usd_rate=avg_usd_rate,
#                 usd_rate = retail_dollar_rate,
#                 # usd_total=usd_total_final,
#                 usd_total = total_usd,
#                 # inr_rate=avg_inr_rate,
#                 inr_rate = retail_inr_rate,
#                 inr_total=inr_total_final,
#                 retail_invoice_number=retail_invoice_number,
#                 created_by = user_instance
#             )
#
#             # Now save the consumption entries with invoice_entry
#             for data in consumption_data:
#                 InvoiceEntryConsumption.objects.create(
#                     invoice_entry=invoice_entry, **data
#                 )
#
#             # Now update the previously created InvoiceEntryConsumption records with the entry FK
#             InvoiceEntryConsumption.objects.filter(invoice_entry=None).update(
#                 invoice_entry=invoice_entry
#             )
#
#             # Final response
#             response_data = serializer.data
#             response_data["consumed_invoices"] = [
#                 {
#                     "invoice_id": invoice.id,
#                     "invoice_number": invoice.invoice_number,
#                     "consumed_qty": consumed_qty,
#                     "usd_rate": str(invoice.dollar_rate),
#                     "conversion_rate": str(invoice.conversion_rate),
#                     "inr_rate": str(invoice.inr_rate),
#                 }
#                 for invoice, consumed_qty in consumed_records
#             ]
#
#             return Response(response_data, status=status.HTTP_201_CREATED)
#         except Exception as e:
#             trace = traceback.format_exc()
#             print("trace is ", trace)
#             return Response(str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)

from decimal import Decimal, getcontext, ROUND_HALF_UP
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction

# Set global decimal context
getcontext().prec = 10
getcontext().rounding = ROUND_HALF_UP

def to_decimal(value, places='0.0001'):
    return Decimal(str(value)).quantize(Decimal(places))


# class InvoiceEntryCreateView(generics.CreateAPIView):
#     queryset = InvoiceEntry.objects.all()
#     serializer_class = InvoiceEntrySerializer
#
#     @transaction.atomic
#     def create(self, request, *args, **kwargs):
#         try:
#             user_instance = User.objects.get(id=request.user.id)
#             serializer = self.get_serializer(data=request.data)
#             serializer.is_valid(raise_exception=True)
#
#             part_number = serializer.validated_data["part_number"]
#             qty_to_consume = Decimal(serializer.validated_data["qty"])
#             conversion_rate = to_decimal(serializer.validated_data["conversion_rate"])
#             invoice_number = request.data.get("invoice_number", None)
#             retail_invoice_number = request.data.get("retail_invoice_number", None)
#
#             retail_dollar_rate = request.data.get("usd_rate")
#             if retail_dollar_rate is None:
#                 raise ValidationError("usd_rate is required")
#             retail_dollar_rate = to_decimal(retail_dollar_rate)
#
#             retail_inr_rate = request.data.get("inr_rate")
#             if retail_inr_rate is None:
#                 raise ValidationError("inr_rate is required")
#             retail_inr_rate = to_decimal(retail_inr_rate)
#
#             try:
#                 part_mapping = InvoiceRetailPartMap.objects.get(
#                     retail_part_number=part_number
#                 )
#                 sale_part_number = part_mapping.sale_part_number
#             except InvoiceRetailPartMap.DoesNotExist:
#                 raise ValidationError({
#                     "part_number": f"No mapping found for retail part '{part_number}'.",
#                 })
#
#             # Get matching invoices
#             if invoice_number:
#                 matching_invoices = Invoice.objects.filter(
#                     part_number=sale_part_number,
#                     invoice_number=invoice_number,
#                     qty__gt=0,
#                 ).order_by("date", "id")
#             else:
#                 matching_invoices = Invoice.objects.filter(
#                     part_number=sale_part_number,
#                     qty__gt=0,
#                 ).order_by("date", "id")
#
#             total_available_qty = sum(invoice.qty for invoice in matching_invoices)
#             if total_available_qty < qty_to_consume:
#                 raise ValidationError({
#                     "qty": f"Not enough stock. Requested: {qty_to_consume}, Available: {total_available_qty}"
#                 })
#
#             qty_remaining = qty_to_consume
#             consumed_records = []
#
#             for invoice in matching_invoices:
#                 if qty_remaining == 0:
#                     break
#
#                 consumed_qty = min(qty_remaining, Decimal(invoice.qty))
#                 qty_remaining -= consumed_qty
#                 invoice.qty -= consumed_qty
#                 invoice.created_by = user_instance
#                 invoice.save()
#
#                 consumed_records.append((invoice, consumed_qty))
#
#             total_usd = Decimal('0')
#             total_inr = Decimal('0')
#             total_qty = Decimal('0')
#             consumption_data = []
#
#             for invoice, consumed_qty in consumed_records:
#                 invoice.dollar_rate = to_decimal(invoice.dollar_rate)
#                 invoice.inr_rate = to_decimal(invoice.inr_rate)
#                 invoice.conversion_rate = to_decimal(invoice.conversion_rate)
#                 dnd = to_decimal(invoice.dnd_charges or 0)
#
#                 usd_rate = retail_dollar_rate
#                 base_value = consumed_qty * usd_rate
#                 taxable_value = base_value - dnd
#                 fc_value = taxable_value
#                 converted_inr_cost = fc_value * conversion_rate
#                 final_inr_total = consumed_qty * conversion_rate
#                 fx_profit = usd_rate * consumed_qty * (conversion_rate - invoice.conversion_rate)
#                 profit_absolute = final_inr_total - converted_inr_cost
#                 selling_profit = usd_rate * consumed_qty - invoice.dollar_rate * consumed_qty
#
#                 consumption_data.append({
#                     "invoice": invoice,
#                     "consumed_qty": consumed_qty,
#                     "selling_price_inr": (invoice.inr_rate * consumed_qty).quantize(Decimal('0.01')),
#                     "profit_absolute": profit_absolute.quantize(Decimal('0.01')),
#                     "profit_selling_rate": selling_profit.quantize(Decimal('0.01')),
#                     "profit_fx_rate": fx_profit.quantize(Decimal('0.01')),
#                     "profit_fx_only": (profit_absolute - (selling_profit + fx_profit)).quantize(Decimal('0.01')),
#                     "base_value": base_value.quantize(Decimal('0.01')),
#                     "dnd_charges": dnd.quantize(Decimal('0.01')),
#                     "taxable_value": taxable_value.quantize(Decimal('0.01')),
#                     "fc_value": fc_value.quantize(Decimal('0.01')),
#                     "fc_rate_with_discount": (fc_value / consumed_qty).quantize(Decimal('0.01')),
#                     "created_by": user_instance,
#                     "rate_sale_from_wh_per_unit": (invoice.inr_rate / invoice.conversion_rate).quantize(Decimal('0.01')),
#                     "rate_sale_from_wh": retail_dollar_rate,
#                     "diff": ((invoice.inr_rate / invoice.conversion_rate) - retail_dollar_rate).quantize(Decimal('0.01')),
#                     "surcharge": (((invoice.inr_rate / invoice.conversion_rate) - retail_dollar_rate) * consumed_qty * conversion_rate).quantize(Decimal('0.01')),
#                 })
#
#                 total_usd += invoice.dollar_rate * consumed_qty
#                 total_inr += invoice.inr_rate * consumed_qty
#                 total_qty += consumed_qty
#
#             avg_usd_rate = (total_usd / total_qty).quantize(Decimal('0.01')) if total_qty > 0 else Decimal('0')
#             avg_inr_rate = (total_inr / total_qty).quantize(Decimal('0.01')) if total_qty > 0 else Decimal('0')
#
#             usd_total_final = (retail_dollar_rate * qty_to_consume).quantize(Decimal('0.01'))
#             inr_total_final = (usd_total_final * conversion_rate).quantize(Decimal('0.01'))
#
#             invoice_entry = serializer.save(
#                 usd_rate=retail_dollar_rate,
#                 usd_total=usd_total_final,
#                 inr_rate=retail_inr_rate,
#                 inr_total=inr_total_final,
#                 retail_invoice_number=retail_invoice_number,
#                 created_by=user_instance,
#             )
#
#             for data in consumption_data:
#                 InvoiceEntryConsumption.objects.create(
#                     invoice_entry=invoice_entry, **data
#                 )
#
#             InvoiceEntryConsumption.objects.filter(invoice_entry=None).update(
#                 invoice_entry=invoice_entry
#             )
#
#             response_data = serializer.data
#             response_data["consumed_invoices"] = [
#                 {
#                     "invoice_id": invoice.id,
#                     "invoice_number": invoice.invoice_number,
#                     "consumed_qty": float(consumed_qty),
#                     "usd_rate": str(invoice.dollar_rate),
#                     "conversion_rate": str(invoice.conversion_rate),
#                     "inr_rate": str(invoice.inr_rate),
#                 }
#                 for invoice, consumed_qty in consumed_records
#             ]
#
#             return Response(response_data, status=status.HTTP_201_CREATED)
#
#         except Exception as e:
#             import traceback
#             trace = traceback.format_exc()
#             print("trace is ", trace)
#             return Response(str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# from decimal import Decimal, getcontext, ROUND_HALF_UP
# from rest_framework.exceptions import ValidationError
# from rest_framework.response import Response
# from rest_framework import status
# from django.db import transaction

# Set global decimal context
getcontext().prec = 10
getcontext().rounding = ROUND_HALF_UP

def to_decimal(value, places='0.0001'):
    """Safely convert a value to Decimal. Returns Decimal('0') for None/empty/invalid values."""
    if value is None or value == '':
        return Decimal('0')
    try:
        return Decimal(str(value)).quantize(Decimal(places))
    except Exception:
        return Decimal('0')


class InvoiceEntryCreateView(generics.CreateAPIView):
    queryset = InvoiceEntry.objects.all()
    serializer_class = InvoiceEntrySerializer

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        try:
            user_instance = User.objects.get(id=request.user.id)
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            part_number = serializer.validated_data["part_number"]
            qty_to_consume = Decimal(serializer.validated_data["qty"])
            conversion_rate = to_decimal(serializer.validated_data["conversion_rate"])
            invoice_number = request.data.get("invoice_number", None)
            retail_invoice_number = request.data.get("retail_invoice_number", None)
            if not retail_invoice_number or not str(retail_invoice_number).strip():
                raise ValidationError({"retail_invoice_number": "Retail invoice number is required."})

            retail_dollar_rate = request.data.get("usd_rate")
            if retail_dollar_rate is None:
                raise ValidationError("usd_rate is required")
            retail_dollar_rate = to_decimal(retail_dollar_rate)

            retail_inr_rate = request.data.get("inr_rate")
            if retail_inr_rate is None:
                raise ValidationError("inr_rate is required")
            retail_inr_rate = to_decimal(retail_inr_rate)

            try:
                part_mapping = InvoiceRetailPartMap.objects.filter(
                    retail_part_number=part_number
                ).first()
                if not part_mapping:
                    # FALLBACK: If no mapping found, assume Retail Part = Sale Part
                    sale_part_number = part_number
                else:         
                    sale_part_number = part_mapping.sale_part_number
            except Exception as e:
                raise ValidationError({
                    "part_number": f"Error looking up part mapping: {str(e)}",
                })

            # Check if user provided manual invoice selection
            selected_invoices = request.data.get("selected_invoices", None)
            
            if selected_invoices and isinstance(selected_invoices, list) and len(selected_invoices) > 0:
                # MANUAL SELECTION MODE: Use user-selected invoices
                # selected_invoices format: [{"invoice_id": 1, "qty": 50}, {"invoice_id": 2, "qty": 30}]
                
                # Validate and fetch selected invoices
                selected_invoice_data = []
                total_selected_qty = Decimal('0')
                
                for selection in selected_invoices:
                    inv_id = selection.get("invoice_id")
                    sel_qty = Decimal(str(selection.get("qty", 0)))
                    
                    if not inv_id or sel_qty <= 0:
                        continue
                    
                    try:
                        invoice = Invoice.objects.get(
                            id=inv_id,
                            part_number=sale_part_number,
                            qty__gt=0
                        )
                    except Invoice.DoesNotExist:
                        raise ValidationError({
                            "selected_invoices": f"Invoice ID {inv_id} not found or has no available quantity."
                        })
                    
                    # Check if requested qty is available
                    if sel_qty > invoice.qty:
                        raise ValidationError({
                            "selected_invoices": f"Invoice {invoice.invoice_number} has only {invoice.qty} available, requested {sel_qty}."
                        })
                    
                    selected_invoice_data.append((invoice, sel_qty))
                    total_selected_qty += sel_qty
                
                # Validate total selected qty matches requested qty
                if total_selected_qty != qty_to_consume:
                    raise ValidationError({
                        "qty": f"Selected quantity ({total_selected_qty}) does not match requested quantity ({qty_to_consume})."
                    })
                
                # Use selected invoices for consumption
                consumed_records = []
                for invoice, consumed_qty in selected_invoice_data:
                    invoice.qty -= int(consumed_qty)
                    invoice.created_by = user_instance
                    invoice.save()
                    consumed_records.append((invoice, consumed_qty))
                
            else:
                # AUTO-FIFO MODE: Original behavior - automatically select invoices
                if invoice_number:
                    matching_invoices = Invoice.objects.filter(
                        part_number=sale_part_number,
                        invoice_number=invoice_number,
                        qty__gt=0,
                    ).order_by("date", "id")
                else:
                    matching_invoices = Invoice.objects.filter(
                        part_number=sale_part_number,
                        qty__gt=0,
                    ).order_by("date", "id")

                total_available_qty = sum(invoice.qty for invoice in matching_invoices)
                if total_available_qty < qty_to_consume:
                    raise ValidationError({
                        "qty": f"Not enough stock. Requested: {qty_to_consume}, Available: {total_available_qty}"
                    })

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

            total_usd = Decimal('0')
            total_inr = Decimal('0')
            total_qty = Decimal('0')
            consumption_data = []

            for invoice, consumed_qty in consumed_records:
                invoice.dollar_rate = to_decimal(invoice.dollar_rate)
                invoice.inr_rate = to_decimal(invoice.inr_rate)
                invoice.conversion_rate = to_decimal(invoice.conversion_rate)
                dnd = to_decimal(invoice.dnd_charges or 0)

                usd_rate = retail_dollar_rate  # selling USD rate per unit

                # --- Value calculations ---
                base_value = consumed_qty * usd_rate                          # total USD sold
                taxable_value = base_value - dnd                              # USD after DnD
                fc_value = taxable_value                                      # FC value = taxable USD

                # INR received from customer (selling side)
                inr_received = consumed_qty * usd_rate * conversion_rate

                # INR cost of goods (purchase side, at original invoice rates)
                inr_cost = consumed_qty * invoice.dollar_rate * invoice.conversion_rate

                # --- Profit decomposition ---
                # Total profit in INR
                profit_absolute = inr_received - inr_cost

                # Profit from selling at a higher USD rate (in INR terms)
                selling_profit_inr = (usd_rate - invoice.dollar_rate) * consumed_qty * conversion_rate

                # Profit from FX rate movement on the cost basis
                fx_profit = invoice.dollar_rate * consumed_qty * (conversion_rate - invoice.conversion_rate)

                # Residual profit (neither from rate nor FX — e.g. DnD adjustments)
                profit_fx_only = profit_absolute - selling_profit_inr - fx_profit

                # Selling rate profit in USD terms (for reporting)
                selling_profit_usd = (usd_rate - invoice.dollar_rate) * consumed_qty

                consumption_data.append({
                    "invoice": invoice,
                    "consumed_qty": consumed_qty,
                    "selling_price_inr": (invoice.inr_rate * consumed_qty).quantize(Decimal('0.01')),
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
                    "rate_sale_from_wh_per_unit": (invoice.inr_rate / invoice.conversion_rate).quantize(Decimal('0.01')) if invoice.conversion_rate else Decimal('0'),
                    "rate_sale_from_wh": retail_dollar_rate,
                    "diff": ((invoice.inr_rate / invoice.conversion_rate) - retail_dollar_rate).quantize(Decimal('0.01')) if invoice.conversion_rate else Decimal('0'),
                    "surcharge": (((invoice.inr_rate / invoice.conversion_rate) - retail_dollar_rate) * consumed_qty * conversion_rate).quantize(Decimal('0.01')) if invoice.conversion_rate else Decimal('0'),
                })

                total_usd += invoice.dollar_rate * consumed_qty
                total_inr += invoice.inr_rate * consumed_qty
                total_qty += consumed_qty

            avg_usd_rate = (total_usd / total_qty).quantize(Decimal('0.01')) if total_qty > 0 else Decimal('0')
            avg_inr_rate = (total_inr / total_qty).quantize(Decimal('0.01')) if total_qty > 0 else Decimal('0')

            # Use the explicitly entered retail INR rate × qty for the InvoiceEntry totals
            usd_total_final = (retail_dollar_rate * qty_to_consume).quantize(Decimal('0.01'))
            inr_total_final = (retail_inr_rate * qty_to_consume).quantize(Decimal('0.01'))

            invoice_entry = serializer.save(
                usd_rate=retail_dollar_rate,
                usd_total=usd_total_final,
                inr_rate=retail_inr_rate,
                inr_total=inr_total_final,
                retail_invoice_number=retail_invoice_number,
                created_by=user_instance,
            )

            for data in consumption_data:
                InvoiceEntryConsumption.objects.create(
                    invoice_entry=invoice_entry, **data
                )

            InvoiceEntryConsumption.objects.filter(invoice_entry=None).update(
                invoice_entry=invoice_entry
            )

            response_data = serializer.data
            response_data["consumed_invoices"] = [
                {
                    "invoice_id": invoice.id,
                    "invoice_number": invoice.invoice_number,
                    "consumed_qty": float(consumed_qty),
                    "usd_rate": str(invoice.dollar_rate),
                    "conversion_rate": str(invoice.conversion_rate),
                    "inr_rate": str(invoice.inr_rate),
                }
                for invoice, consumed_qty in consumed_records
            ]

            return Response(response_data, status=status.HTTP_201_CREATED)

        except Exception as e:
            import traceback
            traceback.format_exc()  # captured for logging only
            return Response(str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class InvoiceEntryUpdateView(generics.UpdateAPIView):
    queryset = InvoiceEntry.objects.all()
    serializer_class = InvoiceEntrySerializer

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        # Fetch the InvoiceEntry instance to be updated
        invoice_entry = self.get_object()
        user_instance = request.user

        # Serialize the incoming data to validate and update the entry
        serializer = self.get_serializer(invoice_entry, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        part_number = serializer.validated_data.get(
            "part_number", invoice_entry.part_number
        )
        qty_to_consume = serializer.validated_data.get("qty", invoice_entry.qty)
        conversion_rate = serializer.validated_data.get(
            "conversion_rate", invoice_entry.conversion_rate
        )
        invoice_number = request.data.get("invoice_number", None)

        # --- Invoice selection logic ---
        if invoice_number:
            matching_invoices = Invoice.objects.filter(
                part_number=part_number, invoice_number=invoice_number, qty__gt=0
            ).order_by("date", "id")
        else:
            matching_invoices = Invoice.objects.filter(
                part_number=part_number, qty__gt=0
            ).order_by("date", "id")

        total_available_qty = sum(invoice.qty for invoice in matching_invoices)
        if total_available_qty < qty_to_consume:
            raise ValidationError(
                {
                    "qty": f"Not enough stock. Requested: {qty_to_consume}, Available: {total_available_qty}"
                }
            )

        # If there's a change in quantity, reconcile the connected consumption entries
        qty_remaining = qty_to_consume
        consumed_records = []

        # Get the connected consumption entries
        existing_consumptions = InvoiceEntryConsumption.objects.filter(
            invoice_entry=invoice_entry
        )

        # Process each existing consumption entry
        for consumption in existing_consumptions:
            invoice = consumption.invoice
            consumed_qty = min(
                qty_remaining, consumption.consumed_qty
            )  # Modify the consumed qty as needed
            qty_remaining -= consumed_qty

            # Update the invoice with the new consumed qty
            invoice.qty += consumed_qty
            invoice.save()

            consumed_records.append((invoice, consumed_qty))

        # If there’s still remaining qty to consume, continue the process for new invoices
        for invoice in matching_invoices:
            if qty_remaining == 0:
                break

            consumed_qty = min(qty_remaining, invoice.qty)
            qty_remaining -= consumed_qty
            invoice.qty -= consumed_qty
            invoice.updated_by = user_instance
            invoice.save()

            consumed_records.append((invoice, consumed_qty))

        # Accumulators for weighted average
        total_usd = 0
        total_inr = 0
        total_qty = 0

        # Prepare data for consumption entries
        consumption_data = []

        for invoice, consumed_qty in consumed_records:
            # usd_total = consumed_qty * invoice.dollar_rate
            # converted_inr_cost = usd_total * invoice.conversion_rate
            # final_inr_total = consumed_qty * invoice.inr_rate
            usd_rate = invoice.dollar_rate
            dnd = invoice.dnd_charges or 0

            # 1. Base value before discounts
            base_value = consumed_qty * usd_rate

            # 2. Taxable value after D&D
            taxable_value = base_value - dnd

            # 3. Final FC value
            fc_value = taxable_value

            # 4. Converted INR cost
            converted_inr_cost = fc_value * invoice.conversion_rate

            # 5. Final INR selling total
            final_inr_total = consumed_qty * invoice.inr_rate

            # 6. FX profit = benefit/loss due to difference in FX rate
            fx_profit = fc_value * (conversion_rate - invoice.conversion_rate)

            # 7. Total profit
            profit_absolute = final_inr_total - converted_inr_cost
            selling_profit = profit_absolute - fx_profit

            # FX profit = benefit/loss due to difference in FX rate
            # fx_profit = usd_total * (conversion_rate - invoice.conversion_rate)

            # Overall profit
            # profit_absolute = final_inr_total - converted_inr_cost
            # selling_profit = profit_absolute - fx_profit

            # Weighted avg calculation
            total_usd += invoice.dollar_rate * consumed_qty
            total_inr += invoice.inr_rate * consumed_qty
            total_qty += consumed_qty

            consumption_data.append(
                {
                    "invoice": invoice,
                    "consumed_qty": consumed_qty,
                    "selling_price_inr": invoice.inr_rate * consumed_qty,
                    "profit_absolute": round(profit_absolute, 2),
                    "profit_selling_rate": round(selling_profit, 2),
                    "profit_fx_rate": round(fx_profit, 2),
                    "profit_fx_only": round(
                        profit_absolute - (selling_profit + fx_profit), 2
                    ),
                    "base_value": round(base_value, 2),
                    "dnd_charges": round(dnd, 2),
                    "taxable_value": round(taxable_value, 2),
                    "fc_value": round(fc_value, 2),
                    "fc_rate_with_discount": round(fc_value / consumed_qty, 2),
                    "created_by": user_instance
                }
            )

        # Save updated invoice entry
        avg_usd_rate = round(total_usd / total_qty, 2)
        avg_inr_rate = round(total_inr / total_qty, 2)
        usd_total_final = round(avg_usd_rate * total_qty, 2)
        inr_total_final = round(usd_total_final * conversion_rate, 2)

        invoice_entry = serializer.save(
            usd_rate=avg_usd_rate,
            usd_total=usd_total_final,
            inr_rate=avg_inr_rate,
            inr_total=inr_total_final,
        )

        # Now save the consumption entries with invoice_entry
        for data in consumption_data:
            InvoiceEntryConsumption.objects.create(invoice_entry=invoice_entry, **data)

        # Now update the previously created InvoiceEntryConsumption records with the entry FK
        InvoiceEntryConsumption.objects.filter(invoice_entry=None).update(
            invoice_entry=invoice_entry
        )

        # Final response
        response_data = serializer.data
        response_data["consumed_invoices"] = [
            {
                "invoice_id": invoice.id,
                "invoice_number": invoice.invoice_number,
                "consumed_qty": consumed_qty,
                "usd_rate": str(invoice.dollar_rate),
                "conversion_rate": str(invoice.conversion_rate),
                "inr_rate": str(invoice.inr_rate),
            }
            for invoice, consumed_qty in consumed_records
        ]

        return Response(response_data, status=status.HTTP_200_OK)


# class InvoiceEntryListView(generics.ListAPIView):
#     queryset = InvoiceEntry.objects.all()
#                 # .select_related('part_number'))
#     serializer_class = InvoiceEntrySerializer
#     filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
#     # filterset_fields = ['part_number', 'invoice_number']
#     # filterset_fields = ['part_number']
#     # ordering_fields = ['created_at', 'usd_total', 'inr_total']
#
#     def list(self, request, *args, **kwargs):
#         queryset = self.filter_queryset(self.get_queryset())
#
#         page = self.paginate_queryset(queryset)
#         serializer = self.get_serializer(page, many=True)
#         return self.get_paginated_response(serializer.data)

from django.db.models import Q
from rest_framework import generics
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from .models import InvoiceEntry
from .serializers import InvoiceEntrySerializer
import datetime


# class InvoiceEntryListView(generics.ListAPIView):
#     queryset = InvoiceEntry.objects.all()
#     serializer_class = InvoiceEntrySerializer
#
#     # Only use DjangoFilterBackend for filtering and OrderingFilter for ordering
#     filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
#
#     # Fields that can be filtered on (you can add more fields here)
#     filterset_fields = [
#         "part_number",
#         "usd_rate",
#         "inr_rate",
#         "qty",
#         "usd_total",
#         "inr_total",
#         "date",
#         "conversion_rate",
#     ]
#     ordering_fields = ["date", "usd_total", "inr_total", "qty"]
#
#     def get_queryset(self):
#         # Start with the default queryset
#         queryset = InvoiceEntry.objects.all()
#
#         # Dynamically apply filters if query params are passed
#         filter_params = self.request.query_params
#
#         # Build Q objects to dynamically filter based on provided query params
#         query = Q()
#
#         # Apply filters based on provided query params
#         for field in self.filterset_fields:
#             value = filter_params.get(field)
#             if value:
#                 query &= Q(
#                     **{f"{field}__icontains": value}
#                 )  # 'icontains' allows partial matching for string fields
#
#         # If any filter criteria were added, apply them
#         if query:
#             queryset = queryset.filter(query)
#
#         # Return the filtered queryset
#         return queryset
#
#     def list(self, request, *args, **kwargs):
#         # Get the filtered queryset
#         queryset = self.filter_queryset(self.get_queryset())
#
#         # Paginate the queryset (if pagination is enabled)
#         page = self.paginate_queryset(queryset)
#
#         # Serialize the data
#         serializer = self.get_serializer(page, many=True)
#
#         # Return paginated response
#         return self.get_paginated_response(serializer.data)


class InvoiceEntryListView(generics.ListAPIView):
    queryset = InvoiceEntry.objects.all()
    serializer_class = InvoiceEntrySerializer

    # Filter and ordering backends
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]

    # Fields that can be filtered on
    filterset_fields = [
        "part_number",
        "usd_rate",
        "inr_rate",
        "qty",
        "usd_total",
        "inr_total",
        "date",
        "conversion_rate",
    ]

    # Fields that can be used for ordering
    ordering_fields = ["date", "usd_total", "inr_total", "qty"]

    def get_queryset(self):
        # Start with the default queryset
        queryset = InvoiceEntry.objects.all()

        # Get the filter parameters from the request
        filter_params = self.request.query_params

        # Build Q objects to dynamically filter based on provided query params
        query = Q()

        # Apply filters based on provided query params
        for field in self.filterset_fields:
            value = filter_params.get(field)
            if value:
                query &= Q(
                    **{f"{field}__icontains": value}
                )  # 'icontains' allows partial matching for string fields

        from_date = filter_params.get("from_date")
        to_date = filter_params.get("to_date")

        if from_date:
            from_date = parse_datetime(from_date)
            if from_date:
                query &= Q(date__gte=from_date) | Q(created_at__gte=from_date)

        if to_date:
            to_date = parse_datetime(to_date)
            if to_date:
                query &= Q(date__lte=to_date) | Q(created_at__lte=to_date)
        # Apply the filters to the queryset
        if query:
            queryset = queryset.filter(query)

        # Return the filtered queryset
        return queryset

    def list(self, request, *args, **kwargs):
        # Get the filtered queryset
        queryset = self.filter_queryset(self.get_queryset())

        # Apply pagination
        paginator = PageNumberPagination()
        # find out how to pass the pagination from setting here
        # paginator.page_size = (
        #     10
        # )
        paginated_queryset = paginator.paginate_queryset(queryset, request)

        # Serialize the paginated queryset
        serializer = self.get_serializer(paginated_queryset, many=True)

        # Return paginated response
        return paginator.get_paginated_response(serializer.data)


class InvoiceEntryDetailView(generics.RetrieveAPIView):
    queryset = InvoiceEntry.objects.all()
    serializer_class = InvoiceEntrySerializer
    lookup_field = "id"

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


from sales.serializers import InvoiceEntryConsumptionSerializer


# class InvoiceEntryConsumptionListView(generics.ListAPIView):
#     queryset = InvoiceEntryConsumption.objects.all()
#     # .select_related('invoice_entry', 'invoice'))
#     serializer_class = InvoiceEntryConsumptionSerializer
#     filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
#
#     # filterset_fields = ['invoice_entry', 'invoice']
#     # ordering_fields = ['consumed_qty', 'profit_absolute']
#
#     def list(self, request, *args, **kwargs):
#         queryset = self.filter_queryset(self.get_queryset())
#
#         page = self.paginate_queryset(queryset)
#         serializer = self.get_serializer(page, many=True)
#         return self.get_paginated_response(serializer.data)


class InvoiceEntryConsumptionListView(generics.ListAPIView):
    queryset = InvoiceEntryConsumption.objects.all().order_by("-id")
    serializer_class = InvoiceEntryConsumptionSerializer

    # Filter and ordering backends
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]

    # Fields that can be filtered on (across relationships)
    filterset_fields = [
        "id",
        "invoice_entry",  # Fields in InvoiceEntry model
        "invoice__invoice_number",  # Fields in related Invoice model (use __ to access related model fields)
        "invoice__part_number",
        "invoice__date",
    ]

    ordering_fields = ["consumed_qty", "profit_absolute"]

    def get_queryset(self):
        # Start with the base queryset
        queryset = InvoiceEntryConsumption.objects.all()

        # Get the filter parameters from the request
        filter_params = self.request.query_params

        # Build Q objects to dynamically filter based on provided query params
        query = Q()

        # Apply filters based on provided query params
        for field in self.filterset_fields:
            value = filter_params.get(field)
            if value:
                query &= Q(
                    **{f"{field}__icontains": value}
                )  # 'icontains' allows partial matching for string fields

        # Apply the filters to the queryset
        if query:
            queryset = queryset.filter(query)

        # Return the filtered queryset
        return queryset

    def list(self, request, *args, **kwargs):
        # Get the filtered queryset
        queryset = self.filter_queryset(self.get_queryset())

        # Apply pagination
        paginator = PageNumberPagination()
        # paginator.page_size = (
        #     10  # Adjust this number to control the number of items per page
        # )
        paginated_queryset = paginator.paginate_queryset(queryset, request)

        # Serialize the paginated queryset
        serializer = self.get_serializer(paginated_queryset, many=True)

        # Return paginated response
        return paginator.get_paginated_response(serializer.data)


class InvoiceEntryConsumptionExcelExportView(APIView):
    def get(self, request, *args, **kwargs):
        # Start with the base queryset
        queryset = InvoiceEntryConsumption.objects.all()

        # Get filter parameters from the request
        filter_params = self.request.query_params
        query = Q()

        # Apply general filters (e.g., invoice_number, invoice_part_number, etc.)
        for field in [
            "invoice_entry",
            "invoice__invoice_number",
            "invoice__part_number",
            "invoice__date",
        ]:
            value = filter_params.get(field)
            if value:
                query &= Q(**{f"{field}__icontains": value})

        # Handle date range filtering (created_at or invoice__date)
        from_date = filter_params.get("from_date")
        to_date = filter_params.get("to_date")
        created_from_date = filter_params.get("created_from_date")
        created_to_date = filter_params.get("created_to_date")

        # filter from_date based on when the invoice was created
        if from_date and (not created_to_date or created_from_date):
            # from_date = parse_datetime(from_date)  # Parse the 'from_date' string to a datetime object
            from_date = datetime.datetime.strptime(from_date, "%y-%m-%d")
            if from_date:
                query &= Q(invoice__date__gte=from_date)
                # | Q(created_at__gte=from_date))

        if to_date and (not created_to_date or created_from_date):
            # to_date = parse_datetime(to_date)  # Parse the 'to_date' string to a datetime object
            to_date = datetime.datetime.strptime(to_date, "%y-%m-%d")
            if to_date:
                query &= Q(invoice__date__lte=to_date)
                # | Q(created_at__lte=to_date))

        if created_from_date:
            created_from_date = datetime.datetime.strptime(created_from_date, "%y-%m-d")
            if created_from_date:
                query = Q(created_at__gte=created_from_date)

        if created_to_date:
            created_to_date = datetime.datetime.strptime(
                created_to_date,
            )
        # Apply the filter to the queryset if any
        if query:
            queryset = queryset.filter(query)

        # Serialize the queryset using the InvoiceEntryConsumptionSerializer
        serializer = InvoiceEntryConsumptionSerializer(queryset, many=True)

        # Prepare data for Excel export
        rows = []
        for entry in serializer.data:
            rows.append(
                {
                    "Consumption ID": entry["id"],
                    "Invoice Number": entry["invoice"]["invoice_number"],
                    "Invoice Part Number": entry["invoice"]["part_number"],
                    "Invoice Date": entry["invoice"]["date"],
                    "Consumed Quantity": entry["consumed_qty"],
                    "Selling Price INR": entry["selling_price_inr"],
                    "Profit Absolute": entry["profit_absolute"],
                    "Profit Selling Rate": entry["profit_selling_rate"],
                    "Profit FX Rate": entry["profit_fx_rate"],
                    "Profit FX Only": entry["profit_fx_only"],
                    "Created At": entry["created_at"],
                    "Updated At": entry["updated_at"],
                    "Invoice Entry ID": entry["invoice_entry"],
                    "Base Value": entry.get("base_value"),
                    "D&D Charges": entry.get("dnd_charges"),
                    "Taxable Value": entry.get("taxable_value"),
                    "FC Value": entry.get("fc_value"),
                    "FC Rate with Discount": entry.get("fc_rate_with_discount"),
                }
            )

        # Convert data to a pandas DataFrame
        df = pd.DataFrame(rows)

        # Create an HTTP response with the Excel file content type
        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = (
            'attachment; filename="invoice_entry_consumptions.xlsx"'
        )

        # Write the DataFrame to the response object as an Excel file
        df.to_excel(response, index=False, engine="openpyxl")

        return response


@api_view(["GET"])
def part_number_summary(request):
    try:
        # Check if part_number is provided in query parameters
        part_number_param = request.query_params.get("part_number", None)

        # Apply filter if part_number is provided, else don't filter
        if part_number_param:
            # Filter based on provided part_number
            part_summaries = (
                InvoiceEntryConsumption.objects.filter(
                    invoice_entry__part_number=part_number_param
                )
                .values("invoice_entry__part_number")
                .annotate(
                    invoice_entry_count=Count("invoice_entry", distinct=True),
                    avg_usd_rate=Avg("invoice_entry__usd_rate"),
                    avg_inr_rate=Avg("invoice_entry__inr_rate"),
                    total_profit_absolute=Sum("profit_absolute"),
                    total_profit_fx_only=Sum("profit_fx_only"),
                    total_profit_selling_rate=Sum("profit_selling_rate"),
                    total_profit_fx_rate=Sum("profit_fx_rate"),
                )
            )
        else:
            # If no part_number is provided, summarize all entries
            part_summaries = InvoiceEntryConsumption.objects.values(
                "invoice_entry__part_number"
            ).annotate(
                invoice_entry_count=Count("invoice_entry", distinct=True),
                avg_usd_rate=Avg("invoice_entry__usd_rate"),
                avg_inr_rate=Avg("invoice_entry__inr_rate"),
                total_profit_absolute=Sum("profit_absolute"),
                total_profit_fx_only=Sum("profit_fx_only"),
                total_profit_selling_rate=Sum("profit_selling_rate"),
                total_profit_fx_rate=Sum("profit_fx_rate"),
            )

        # Get all entries, or filtered entries if part_number is provided
        if part_number_param:
            entries = InvoiceEntryConsumption.objects.filter(
                invoice_entry__part_number=part_number_param
            ).select_related("invoice_entry", "invoice")
        else:
            entries = InvoiceEntryConsumption.objects.select_related(
                "invoice_entry", "invoice"
            ).all()

        # Build a map of part summaries
        part_map = {
            summary["invoice_entry__part_number"]: summary for summary in part_summaries
        }

        # Add entries to the part map
        for part_number, data in part_map.items():
            data["part_number"] = part_number
            data["entries"] = []

        # Populate the entries for each part_number
        for entry in entries:
            part_number = entry.invoice_entry.part_number
            if part_number not in part_map:
                continue  # Skip if part_number is not in the summary map

            part_map[part_number]["entries"].append(
                {
                    "invoice_number": entry.invoice.invoice_number,
                    "consumed_qty": entry.consumed_qty,
                    "usd_rate": float(entry.invoice_entry.usd_rate),
                    "inr_rate": float(entry.invoice_entry.inr_rate),
                    "profit_absolute": float(entry.profit_absolute),
                    "profit_fx_only": float(entry.profit_fx_only),
                    "profit_selling_rate": float(entry.profit_selling_rate),
                    "profit_fx_rate": float(entry.profit_fx_rate),
                }
            )

        # Enable to include grand totals
        data = list(part_map.values())

        grand_total = {
            "part_number": "TOTAL",
            "invoice_entry_count": sum(d["invoice_entry_count"] for d in data),
            "avg_usd_rate": (
                sum(d["avg_usd_rate"] or 0 for d in data) / len(data) if data else 0
            ),
            "avg_inr_rate": (
                sum(d["avg_inr_rate"] or 0 for d in data) / len(data) if data else 0
            ),
            "total_profit_absolute": sum(d["total_profit_absolute"] or 0 for d in data),
            "total_profit_fx_only": sum(d["total_profit_fx_only"] or 0 for d in data),
            "total_profit_selling_rate": sum(
                d["total_profit_selling_rate"] or 0 for d in data
            ),
            "total_profit_fx_rate": sum(d["total_profit_fx_rate"] or 0 for d in data),
            "entries": [],  # Optional: or include all entries if needed
        }
        data.append(grand_total)

        return Response({"data": list(part_map.values())}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def invoice_entry_generate_excel(request):
    try:
        pass
    except Exception as e:
        pass


class InvoiceEntryExcelExportView(APIView):
    def get(self, request, *args, **kwargs):
        # Get the queryset (filtered if needed)
        queryset = InvoiceEntry.objects.all()

        # Get filter parameters from the request
        filter_params = self.request.query_params
        query = Q()

        # Apply general filters (e.g., part_number, usd_rate, etc.)
        for field in [
            "part_number",
            "usd_rate",
            "inr_rate",
            "qty",
            "usd_total",
            "inr_total",
            "date",
            "conversion_rate",
        ]:
            value = filter_params.get(field)
            if value:
                query &= Q(**{f"{field}__icontains": value})

        # Handle date range filtering
        from_date = filter_params.get("from_date")
        to_date = filter_params.get("to_date")
        created_from_date = filter_params.get("created_from_date")
        created_to_date = filter_params.get("created_to_date")

        if from_date and (not created_to_date or created_from_date):
            # from_date = parse_datetime(from_date)  # Parse the 'from_date' string to a datetime object
            from_date = datetime.datetime.strptime(from_date, "%Y-%m-%d")
            if from_date:
                print("inside from date", from_date)
                query &= Q(date__gte=from_date)
                # | Q(created_at__gte=from_date)

        if to_date and (not created_to_date or created_from_date):
            # to_date = parse_datetime(to_date)  # Parse the 'to_date' string to a datetime object
            to_date = datetime.datetime.strptime(to_date, "%Y-%m-%d")
            if to_date:
                print("inside to date", to_date)
                query &= Q(date__lte=to_date)
                # | Q(created_at__lte=to_date))

        if created_from_date:
            created_from_date = datetime.datetime.strptime(
                created_from_date, "%Y-%m-%d"
            )
            if created_from_date:
                query = Q(created_at__gte=created_from_date)

        if created_to_date:
            created_to_date = datetime.datetime.strptime(created_to_date, "%Y-%m-%d")
            if created_to_date:
                query = Q(created_at__lte=created_to_date)

        # Apply the filter to the queryset if any
        if query:
            print("generated query is ", query)
            queryset = queryset.filter(query)

        # Serialize the queryset using the InvoiceEntrySerializer
        serializer = InvoiceEntrySerializer(queryset, many=True)

        # Prepare data for Excel export
        rows = []
        for entry in serializer.data:
            for consumption in entry.get("consumptions", []):
                rows.append(
                    {
                        "Invoice Entry ID": entry["id"],
                        "Part Number": entry["part_number"],
                        "Date": entry["date"],
                        "Qty": entry["qty"],
                        "USD Rate": entry["usd_rate"],
                        "USD Total": entry["usd_total"],
                        "INR Rate": entry["inr_rate"],
                        "INR Total": entry["inr_total"],
                        "Conversion Rate": entry["conversion_rate"],
                        "Consumption Invoice ID": consumption["invoice"]["id"],
                        "Consumption Invoice Number": consumption["invoice"][
                            "invoice_number"
                        ],
                        "Consumption Part Number": consumption["invoice"][
                            "part_number"
                        ],
                        "Consumed Qty": consumption["consumed_qty"],
                        "Selling Price INR": consumption["selling_price_inr"],
                        "Profit Absolute": consumption["profit_absolute"],
                        "Profit Selling Rate": consumption["profit_selling_rate"],
                        "Profit FX Rate": consumption["profit_fx_rate"],
                        "Profit FX Only": consumption["profit_fx_only"],
                    }
                )

        # Convert data to a pandas DataFrame
        df = pd.DataFrame(rows)

        # Create an HTTP response with the Excel file content type
        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = 'attachment; filename="invoice_entries.xlsx"'

        # Write the DataFrame to the response object as an Excel file
        df.to_excel(response, index=False, engine="openpyxl")

        return response


class RetailInvoiceExportView(APIView):
    def get(self, request, *args, **kwargs):
        consumptions = InvoiceEntryConsumption.objects.select_related(
            "invoice", "invoice_entry"
        )
        print("consumptions are", consumptions)

        rows = []
        try:
            for c in consumptions:
                invoice = c.invoice
                entry = c.invoice_entry

                base_value = c.base_value or (c.consumed_qty * invoice.dollar_rate)
                dnd = c.dnd_charges or 0
                taxable_value = base_value - dnd
                fc_value = taxable_value
                fc_rate_discount = fc_value / c.consumed_qty if c.consumed_qty else 0

                rows.append(
                    {
                        "PLANT": "1002",  # or invoice.plant_code if available
                        "Customer No": invoice.customer_code,
                        "Customer Name": (
                            "INNIO"
                            if invoice.customer_code == "10446"
                            else "INNIO Waukesha Gas Engines (T)"
                        ),
                        # You can dynamically map later
                        "Invoice No.": invoice.invoice_number,
                        "Invoice Date": invoice.date.strftime("%d/%b/%y"),
                        "Part No.": invoice.part_number,
                        "Invoice Quantity": c.consumed_qty,
                        "Unit Rate": round(invoice.dollar_rate, 2),
                        "Base Value": round(base_value, 2),
                        "D&D Charges": round(dnd, 2),
                        "Discount": "",  # Extend if needed
                        "Freight": "",
                        "Packing Charges": "",
                        "Taxable Value": round(taxable_value, 2),
                        "Currency": "USD",
                        "Original Exchange Rate": round(invoice.conversion_rate, 2),
                        "FC Value": round(fc_value, 2),
                        "FC Rate with Discount": round(fc_rate_discount, 2),
                    }
                )
        except Exception as e:
            print("encountered exception", e)

        df = pd.DataFrame(rows)
        print("rows are ", df)

        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = (
            'attachment; filename="retail_invoice_report.xlsx"'
        )

        df.to_excel(response, index=False, engine="openpyxl")
        return response


# class CombinedInvoiceExportView(APIView):
#     def get(self, request, *args, **kwargs):
#         try:
#             consumptions = InvoiceEntryConsumption.objects.select_related(
#                 "invoice_entry", "invoice"
#             ).order_by("invoice__invoice_number", "invoice__date")
#
#             rows = []
#
#             for c in consumptions:
#                 invoice = c.invoice
#                 entry = c.invoice_entry
#
#                 # -- RV Details --
#                 # base_value = c.base_value or (c.consumed_qty * invoice.dollar_rate)
#                 base_value = c.base_value
#                 dnd = c.dnd_charges or 0
#                 taxable_value = base_value - dnd
#                 # taxable_value = invoice.inr_rate *
#                 fc_value = taxable_value
#                 fc_rate_discount = fc_value / c.consumed_qty if c.consumed_qty else 0
#
#                 # -- SA Details --
#                 revised_fc_rate = entry.usd_rate or 0
#                 revised_conversion_rate = entry.conversion_rate or 0
#                 revised_fc_value = revised_fc_rate * c.consumed_qty
#                 revised_inr_value = revised_fc_value * revised_conversion_rate
#
#                 # -- Difference Calculations --
#                 diff_fc_rate = round(fc_rate_discount - revised_fc_rate, 2)
#                 diff_conversion_rate = round(
#                     invoice.conversion_rate - revised_conversion_rate, 2
#                 )
#
#                 price_variation_inr = round(
#                     diff_fc_rate * c.consumed_qty * invoice.conversion_rate, 2
#                 )
#                 # exchange_variation_inr = round(diff_conversion_rate * revised_fc_value, 2)
#                 exchange_variation_inr = Decimal(diff_conversion_rate * revised_fc_value)
#                 # print("Exchange variation in inr is ", exchange_variation_inr)
#
#                 rate_sale_from_wh_per_unit = invoice.inr_rate / invoice.conversion_rate
#                 rate_sale_from_wh = entry.usd_rate
#                 diff = rate_sale_from_wh_per_unit - rate_sale_from_wh
#                 surcharge = diff * c.consumed_qty * c.invoice.conversion_rate
#                 # select conversion rate from sales.invoice entry
#                 # print("conversion_rate", c.invoice.conversion_rate)
#                 # diff * exchange_rate * invoice qty
#
#                 rows.append(
#                     {
#                         # RV Section
#                         # 'PLANT': '1002', # need where to select PLANT from
#                         "Customer No": invoice.customer_code,
#                         # 'Customer Name': 'INNIO' if invoice.customer_code == '10446' else 'INNIO Waukesha Gas Engines (T)', # need to know where to select
#                         # customer name from
#                         "Invoice No. (RV)": invoice.invoice_number,
#                         "Invoice Date (RV)": invoice.date.strftime("%d/%b/%y"),
#                         "Part No.": invoice.part_number,
#                         "Invoice Quantity": c.consumed_qty,
#                         "Unit Rate": round(invoice.dollar_rate, 2),
#                         "Base Value": round(base_value, 2),
#                         "D&D Charges": round(dnd, 2),
#                         "Discount": "",
#                         "Freight": "",
#                         "Packing Charges": "",
#                         "Taxable Value": round(taxable_value, 2),
#                         "Currency": "USD",
#                         "Original Exchange Rate": round(invoice.conversion_rate, 2),
#                         "FC Value": round(fc_value, 2),
#                         "FC Rate with Discount": round(fc_rate_discount, 2),
#                         # SA Section
#                         "Invoice No. (SA)": entry.id,
#                         "Invoice Date (SA)": entry.date.strftime("%d/%b/%y"),
#                         "Part No. (SA)": entry.part_number,
#                         "Qty (SA)": c.consumed_qty,
#                         "Revised Rate in FC": round(revised_fc_rate, 2),
#                         "Revised Exchange Rate": round(revised_conversion_rate, 2),
#                         "Revised Value in FC": round(revised_fc_value, 2),
#                         "Revised Value in INR": round(revised_inr_value, 2),
#                         # Difference
#                         "Difference in FC Rate": diff_fc_rate,
#                         "Difference in Exchange Rate": diff_conversion_rate,
#                         "Difference Value (Price Variation in INR)": price_variation_inr,
#                         "Difference in Exchange Rate in INR": exchange_variation_inr,
#
#                         # add plant later
#                         "Plant Code": invoice.plant_code,
#                         "Customer_name": invoice.customer_name,
#                         "Rate sale from WH per Unit with Discount": round(invoice.inr_rate/ invoice.conversion_rate, 2),
#                         "Rate sale from WH": round(entry.usd_rate, 2),
#                         "Diff": round((invoice.inr_rate / invoice.conversion_rate) - entry.usd_rate, 2),
#                         # "Surcharge": round(Decimal(((invoice.inr_rate/ invoice.conversion_rate)- entry.usd_rate) * c.consumed_qty * entry.conversion_rate),2),
#                         "Surcharge": round(surcharge,2)
#
#                     }
#                 )
#
#             df = pd.DataFrame(rows)
#
#             response = HttpResponse(
#                 content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
#             )
#             response["Content-Disposition"] = (
#                 'attachment; filename="combined_invoice_report.xlsx"'
#             )
#
#             df.to_excel(response, index=False, engine="openpyxl")
#             return response
#
#         except Exception as e:
#             trace = traceback.format_exc()
#             print("trace is ", trace)

class CombinedInvoiceExportView(APIView):
    def get(self, request, *args, **kwargs):
        try:
            consumptions = InvoiceEntryConsumption.objects.select_related(
                "invoice_entry", "invoice"
            ).order_by("invoice__invoice_number", "invoice__date")

            rows = []

            for c in consumptions:
                # c is invoice consumption from warehouse
                # invoice is concerned warehouse invoice
                # entry is retail entry
                invoice = c.invoice
                # print("f invoice is ", invoice)
                entry = c.invoice_entry

                # consumed_qty = to_decimal(c.consumed_qty, '0.01')
                consumed_qty = c.consumed_qty
                # base_value = to_decimal(c.base_value or (consumed_qty * invoice.dollar_rate), '0.01')
                # base_value = consumed_qty * entry.usd_rate
                base_value = consumed_qty * invoice.dollar_rate
                # print("base value is ", base_value);
                dnd = to_decimal(c.dnd_charges or 0, '0.01')
                taxable_value = base_value - dnd
                # fc_value = taxable_value
                fc_value = entry.usd_rate * consumed_qty
                fc_rate_discount = (fc_value / consumed_qty).quantize(Decimal('0.01')) if consumed_qty else Decimal('0.00')

                # Revised (SA) details
                revised_fc_rate = to_decimal(entry.usd_rate, '0.01')
                revised_conversion_rate = to_decimal(entry.conversion_rate, '0.0001')
                revised_fc_value = (revised_fc_rate * consumed_qty).quantize(Decimal('0.01'))
                # revised_inr_value = (revised_fc_value * revised_conversion_rate).quantize(Decimal('0.01'))
                # revised_inr_value = (entry.usd_rate * revised_conversion_rate * consumed_qty).quantize(Decimal('0.01'))
                # print("---------------------------")
                # print("revised inr value = consumed_qty * entry.usd_rate * entry.conversion_rate")
                # print(f"consumed qty is ", consumed_qty)
                # print(f"entry used rate is", entry.usd_rate)
                # print("entry_conversion_rate", entry.conversion_rate)
                # revised_inr_value = (consumed_qty * entry.usd_rate * entry.conversion_rate)
                intermediate_usd_value = round(consumed_qty * entry.usd_rate, 4)
                revised_inr_value = round(intermediate_usd_value * entry.conversion_rate,4)
                # print("revised_fc_rate", revised_fc_rate)
                # print("revised_conversion_rate", revised_conversion_rate)
                # print("revised_fc_value", revised_fc_value)
                print("revised_inr_rate", revised_inr_value)
                # print("unit rate", invoice.inr_rate)

                # Difference calculations
                diff_fc_rate = (fc_rate_discount - revised_fc_rate).quantize(Decimal('0.0001'))
                diff_conversion_rate = (to_decimal(invoice.conversion_rate, '0.0001') - revised_conversion_rate).quantize(Decimal('0.0001'))

                # change formula
                # price_variation_inr = revised_fc_value * revised_exchange_rate
                # w * x * y = AB from reconcilation sheet
                # price_variation_inr = (diff_fc_rate * consumed_qty * to_decimal(invoice.conversion_rate, '0.0001')).quantize(Decimal('0.0001'))
                price_variation_inr = revised_fc_value * revised_conversion_rate
                exchange_variation_inr = (diff_conversion_rate * revised_fc_value).quantize(Decimal('0.0001'))

                # Surcharge calculations
                rate_sale_from_wh_per_unit = (to_decimal(invoice.inr_rate, '0.01') / to_decimal(invoice.conversion_rate, '0.01'))
                # rate_sale_from_wh_per_unit = invoice.inr_rate / invoice.conversion_rate
                # rate_sale_from_wh = revised_fc_rate
                # rate_sale_from_wh = rate_sale_from_wh_per_unit * (invoice.dollar_rate * consumed_qty)
                rate_sale_from_wh = (invoice.inr_rate/invoice.conversion_rate) * entry.usd_rate
                        # .quantize(Decimal('0.01')))
                rate_sale_from_wh_per_unit_with_discount =invoice.conversion_rate - entry.conversion_rate
                rate_sale_from_wh_per_unit_with_discount = to_decimal(rate_sale_from_wh_per_unit_with_discount, '0.01')
                # print(f"rate sale from WH per unit with discount", rate_sale_from_wh_per_unit_with_discount)
                # rate_sale_from_wh = round(rate_sale_from_wh_per_unit_with_discount * (consumed_qty * entry.usd_rate),2)
                rate_sale_from_wh = (invoice.conversion_rate - revised_conversion_rate)*consumed_qty*revised_fc_rate
                diff = (invoice.dollar_rate - entry.usd_rate)
                # if diff < 0:
                #     pass
                # else:
                # diff = round(diff, 2)
                # diff = rate_sale_from_wh_per_unit_with_discount - rate_sale_from_wh
                # print("consumed_qty * unit_rate", consumed_qty * entry.usd_rate)
                # print("invoice.inr_rate", to_decimal(invoice.inr_rate, '0.01'))
                # print("invoice.conversion_rate", invoice.conversion_rate)
                # print("invoice.conversion_rate", to_decimal(invoice.conversion_rate, '0.0001'))
                # print("rate_sale_from_wh", revised_fc_rate)
                # print(f"diff is ", diff)
                # print(f"rate_sale_from_wh_per_unit",rate_sale_from_wh_per_unit)
                # print(f"invoice.conversion_rate", invoice.conversion_rate)
                # print(f"consumed qty", consumed_qty)
                # surcharge = round((diff * consumed_qty * to_decimal(invoice.conversion_rate, '0.01')),2)
                             # .quantize(Decimal('0.01')))
                # surcharge = diff * invoice.conversion_rate*consumed_qty
                # surcharge = diff * ((rate_sale_from_wh_per_unit_with_discount/entry.conversion_rate) - rate_sale_from_wh)*consumed_qty
                surcharge = (invoice.dollar_rate - fc_rate_discount) * consumed_qty * invoice.conversion_rate
                if surcharge < 0:
                    pass
                else:
                    surcharge = round(surcharge,4)
                # surcharge = round(surcharge,2)
                # print(f"rate_sale from warehouse is ", rate_sale_from_wh)
                # print(f"entry.usd_rate", entry.usd_rate)
                # print(f"invoice.dollar_rate", invoice.dollar_rate)
                # print(f"diff is ", diff)
                # print(f"rate sale from warehouse is ", rate_sale_from_wh)
                # print(f"rate sale from WH per unit with discount", rate_sale_from_wh_per_unit_with_discount)
                # print(f"surcharge is ", surcharge)

                rows.append({
                    "Customer No": invoice.customer_code,
                    "Invoice No. (RV)": invoice.invoice_number,
                    "Invoice Date (RV)": invoice.date.strftime("%d/%b/%y"),
                    "Part No.": invoice.part_number,
                    "Invoice Quantity": consumed_qty,
                    # "Unit Rate": float(to_decimal(invoice.dollar_rate)),
                    "Unit Rate": invoice.dollar_rate,
                    "Base Value": base_value,
                    "INR Rate":invoice.inr_rate,
                    "D&D Charges": dnd,
                    "Discount": "",
                    "Freight": "",
                    "Packing Charges": "",
                    "Taxable Value": taxable_value,
                    "Currency": "USD",
                    "Original Exchange Rate": float(to_decimal(invoice.conversion_rate, '0.0001')),
                    "FC Value": fc_value,
                    "FC Rate with Discount": fc_rate_discount,

                    # SA Section
                    "Invoice No. (SA)": entry.retail_invoice_number,
                    # "Invoice Date (SA)": entry.date.strftime("%d/%b/%y"),
                    "Invoice Date (SA)": entry.date.strftime("%d/%b/%y, %H:%M:%S"),
                    "Part No. (SA)": entry.part_number,
                    "Qty (SA)": consumed_qty,
                    "Revised Rate in FC": revised_fc_rate,
                    "Revised Exchange Rate": revised_conversion_rate,
                    "Revised Value in FC": revised_fc_value,
                    "Revised Value in INR": revised_inr_value,

                    # Difference
                    "Difference in FC Rate": diff_fc_rate,
                    "Difference in Exchange Rate": diff_conversion_rate,
                    "Difference Value (Price Variation in INR)": price_variation_inr,
                    # "Difference in Exchange Rate in INR": exchange_variation_inr,
                    # this column is copied twice as the client required it
                    "Difference in Exchange Rate in INR": rate_sale_from_wh,

                    # Warehouse
                    "Plant Code": invoice.plant_code,
                    "Customer_name": invoice.customer_name,
                    "Rate sale from WH per Unit with Discount": rate_sale_from_wh_per_unit_with_discount,
                    "Rate sale from WH": rate_sale_from_wh,
                    "Diff": round(diff,2),
                    "INR Total":  invoice.inr_rate * consumed_qty,
                    # "Surcharge": float(surcharge),
                    "Surcharge": surcharge
                })

            df = pd.DataFrame(rows)
            response = HttpResponse(
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            response["Content-Disposition"] = 'attachment; filename="combined_invoice_report.xlsx"'
            df.to_excel(response, index=False, engine="openpyxl")
            return response

        except Exception as e:
            # trace = traceback.format_exc()
            # print("trace is", trace)
            return Response({"error": str(e)}, status=500)
