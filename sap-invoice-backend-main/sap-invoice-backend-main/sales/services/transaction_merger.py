"""Transaction merger service for part-wise transaction history."""

from sales.models import Invoice, InvoiceRetailPartMap
from retail.models import InvoiceEntry
from datetime import datetime

class TransactionMerger:
    """Service class for retrieving and merging incoming and outgoing transactions."""

    def get_incoming_transactions(self, part_number=None, from_date=None, to_date=None):
        """
        Retrieve incoming transactions from Invoice model.
        
        Args:
            part_number: The part number to filter by (None for ALL)
            from_date: Optional start date filter (inclusive)
            to_date: Optional end date filter (inclusive)
            
        Returns:
            List of transaction dictionaries with type='INCOMING' and positive qty
        """
        if part_number:
            queryset = Invoice.objects.filter(part_number=part_number)
        else:
            # Fetch ALL if part_number is None
            queryset = Invoice.objects.all()
        
        # Apply optional date filters
        if from_date:
            queryset = queryset.filter(date__gte=from_date)
        if to_date:
            queryset = queryset.filter(date__lte=to_date)
        
        queryset = queryset.order_by("date", "id")

        # Extract required fields
        # Note: ensuring we get part_number for 'ALL' case
        invoices = queryset.values(
            'id',
            'invoice_number',
            'date',
            'qty',
            'customer_name',
            'customer_code',
            'created_at',
            'part_number',
            'dollar_total',
            'inr_total',
            'conversion_rate',
            'dollar_rate',
            'inr_rate',
        )
        
        # Convert to list of dictionaries with proper format
        transactions = []
        for invoice in invoices:
            # Handle customer_name: use value if present, else "COOPER"
            customer_name = invoice['customer_name'] if invoice['customer_name'] else "COOPER"
            
            # Auto-calculate exchange_rate when conversion_rate is 0/None
            # SAP imports often don't populate conversion_rate, but we can derive it:
            # exchange_rate = inr_rate / dollar_rate
            conv_rate = invoice['conversion_rate']
            if not conv_rate or float(conv_rate) == 0:
                dollar_rate = float(invoice['dollar_rate'] or 0)
                inr_rate = float(invoice['inr_rate'] or 0)
                conv_rate = round(inr_rate / dollar_rate, 4) if dollar_rate > 0 else 0
            
            transactions.append({
                'date': invoice['date'],
                'invoice_number': invoice['invoice_number'],
                'qty': invoice['qty'],
                'type': 'INCOMING',
                'created_at': invoice['created_at'],
                'name': customer_name, # Standardized key 'name' for view
                'customer_code': invoice['customer_code'] or "",
                'part_number': invoice['part_number'],
                'fc_value': invoice['dollar_total'] or 0,
                'inr_value': invoice['inr_total'] or 0,
                'exchange_rate': conv_rate,
            })
        
        return transactions

    def get_outgoing_transactions(self, part_number=None, from_date=None, to_date=None):
        """
        Retrieve outgoing transactions from InvoiceEntry model.
        
        Args:
            part_number: The part number to filter by (None for ALL)
            from_date: Optional start date filter (inclusive)
            to_date: Optional end date filter (inclusive)
            
        Returns:
            List of transaction dictionaries with type='OUTGOING' and negative qty
        """
        
        if part_number:
            # Look up retail part numbers mapped to this SAP part number
            mappings = InvoiceRetailPartMap.objects.filter(sale_part_number=part_number)
            retail_part_numbers = [m.retail_part_number for m in mappings]

            # Search by retail part numbers AND the SAP part number itself (in case it's used directly)
            search_parts = set(retail_part_numbers)
            search_parts.add(part_number)

            queryset = InvoiceEntry.objects.filter(part_number__in=search_parts)

            # Maps: retail_part → company name, retail_part → customer_code
            part_to_company = {m.retail_part_number: m.company_name for m in mappings}
            part_to_code = {m.retail_part_number: (m.customer_code or "") for m in mappings}
            # Reverse map: retail_part → SAP part (so we can normalize part_number in output)
            retail_to_sale = {m.retail_part_number: m.sale_part_number for m in mappings}
        else:
            # Fetch ALL outgoing transactions
            queryset = InvoiceEntry.objects.all()

            all_mappings = InvoiceRetailPartMap.objects.all()
            part_to_company = {m.retail_part_number: m.company_name for m in all_mappings}
            part_to_code = {m.retail_part_number: (m.customer_code or "") for m in all_mappings}
            retail_to_sale = {m.retail_part_number: m.sale_part_number for m in all_mappings}

        # Apply optional date filters
        if from_date:
            queryset = queryset.filter(date__gte=from_date)
        if to_date:
            queryset = queryset.filter(date__lte=to_date)

        queryset = queryset.order_by("date", "id")

        invoice_entries = queryset.values(
            'id',
            'retail_invoice_number',
            'date',
            'qty',
            'created_at',
            'part_number',
            'usd_total',
            'inr_total',
            'conversion_rate',
        )

        transactions = []
        for entry in invoice_entries:
            retail_pn = entry['part_number']
            company = part_to_company.get(retail_pn, "Retail Customer")
            code = part_to_code.get(retail_pn, "")
            # Normalize to SAP part number so grouping/filtering by SAP part works correctly
            sap_part = retail_to_sale.get(retail_pn, retail_pn)

            transactions.append({
                'date': entry['date'],
                'invoice_number': entry['retail_invoice_number'] or f"OUT-{entry['date']}",
                'qty': -entry['qty'],  # Negative for outgoing
                'type': 'OUTGOING',
                'created_at': entry['created_at'],
                'name': company,
                'customer_code': code,
                'part_number': sap_part,  # Use SAP part number, not retail part number
                'fc_value': entry['usd_total'] or 0,
                'inr_value': entry['inr_total'] or 0,
                'exchange_rate': entry['conversion_rate'] or 0,
            })

        return transactions

    def merge_and_sort(self, incoming, outgoing):
        """
        Merge and sort transactions chronologically.
        
        Args:
            incoming: List of incoming transaction dictionaries
            outgoing: List of outgoing transaction dictionaries
            
        Returns:
            Single merged and sorted list of transactions
        """
        # Combine both lists
        merged = incoming + outgoing
        
        # Sort by date (ascending), then by created_at (ascending)
        merged.sort(key=lambda x: (x['date'], x['created_at'] or datetime.min))
        
        return merged
