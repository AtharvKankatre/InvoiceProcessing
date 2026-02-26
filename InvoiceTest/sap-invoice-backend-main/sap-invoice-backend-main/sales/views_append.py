

@api_view(["GET"])
def invoice_balance_history(request):
    """
    Get combined history of invoice creation (credit) and consumption (debit).
    """
    try:
        # 1. Get all Invoices (Credits)
        invoices = Invoice.objects.all().order_by("date")
        invoice_data = InvoiceSerializer(invoices, many=True).data

        # 2. Get all Consumption entries (Debits)
        consumptions = InvoiceEntryConsumption.objects.all().order_by("invoice_entry__date")
        # specific serializer might be needed or manual construction
        
        history = []

        # Process Invoices (Add to stock)
        for inv in invoice_data:
            history.append({
                "id": f"inv_{inv['id']}",
                "date": inv["date"],
                "type": "Invoice Created",
                "reference": inv["invoice_number"],
                "part_number": inv["part_number"],
                "qty": float(inv["invoice_qty"]),  # Total qty created
                "price": float(inv["dollar_rate"]),
                "currency": "USD",
                "action": "Created",
            })

        # Process Consumptions (Remove from stock)
        for cons in consumptions:
            history.append({
                "id": f"cons_{cons.id}",
                "date": cons.invoice_entry.date.isoformat(),
                "type": "Retail Consumption",
                "reference": cons.invoice_entry.retail_invoice_number, # Retail Invoice #
                "part_number": cons.invoice.part_number, # The part being consumed
                "qty": -float(cons.consumed_qty), # Negative for consumption
                "price": float(cons.selling_price_dollar),
                "currency": "USD",
                "action": "Retail Sales",
            })

        # Sort combined history by date
        # Helper to parse date string to ensure correct sorting
        def parse_date(item):
            d = item["date"]
            if isinstance(d, str):
                try:
                    return datetime.strptime(d, "%Y-%m-%d").date()
                except ValueError:
                    return datetime.strptime(d, "%Y-%m-%dT%H:%M:%S").date()
            return d

        history.sort(key=lambda x: parse_date(x), reverse=True) # Newest first

        return Response(history)

    except Exception as e:
        traceback.print_exc()
        return Response(
            {"error": str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
