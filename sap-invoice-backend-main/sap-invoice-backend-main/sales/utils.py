
from datetime import datetime, date
from sales.models import Invoice, InvoiceRetailPartMap
from retail.models import InvoiceEntry
from django.db.models import Sum

class TransactionMerger:
    """
    Helper class to fetch and merge incoming (Invoice) and outgoing (InvoiceEntry) transactions.
    """

    def get_incoming_transactions(self, part_number=None, from_date=None, to_date=None):
        """
        Fetch incoming transactions from Invoices table.
        """
        print(f"DEBUG_UTILS: get_incoming_transactions called with part_number={repr(part_number)}, from={from_date}, to={to_date}")
        if part_number:
            print(f"DEBUG_UTILS: Filtering by part_number: {part_number}")
            invoices = Invoice.objects.filter(part_number=part_number).order_by("date", "id")
        else:
            print("DEBUG_UTILS: Fetching ALL invoices")
            invoices = Invoice.objects.all().order_by("date", "id")
        
        print(f"DEBUG_UTILS: Found {invoices.count()} invoices (before date filter)")
        
        # We fetch all to calculate correct opening balance later, 
        # but if filtering is strict DB side, we would need separate opening balance query.
        # Here we follow the logic of fetching all and filtering later if needed, 
        # or relying on Python filtering.
        
        # The ViewSet logic implies filtering passed to this method.
        # If from_date is passed, we should ideally still fetch previous to get opening balance?
        # But the User's code passes from_date/to_date to these methods.
        # So we should filter DB side?
        
        if from_date:
            invoices = invoices.filter(date__gte=from_date)
        if to_date:
            invoices = invoices.filter(date__lte=to_date)
            
        transactions = []
        for inv in invoices:
            transactions.append({
                "date": inv.date,
                "date": inv.date,
                "part_number": inv.part_number,
                "invoice_number": inv.invoice_number,
                "qty": inv.qty, # Positive
                "name": inv.customer_name or "COOPER",
                "type": "INCOMING",
                "created_at": inv.created_at,
                "id": inv.id,
                "customer_code": inv.customer_code or "",
            })
        return transactions

    def get_outgoing_transactions(self, part_number=None, from_date=None, to_date=None):
        """
        Fetch outgoing transactions from InvoiceEntry table via mapping.
        """
        if part_number:
            # manual mapping lookup (since the relationship isn't direct FK on part_number string)
            mappings = InvoiceRetailPartMap.objects.filter(sale_part_number=part_number)
            retail_part_numbers = [m.retail_part_number for m in mappings]
            
            search_parts = set(retail_part_numbers)
            search_parts.add(part_number)
            
            entries = InvoiceEntry.objects.filter(part_number__in=search_parts).order_by("date", "id")
            
            # Cache map for name lookup
            part_to_company = {m.retail_part_number: m.company_name for m in mappings}
        else:
            # Fetch ALL outgoing transactions
            entries = InvoiceEntry.objects.all().order_by("date", "id")
            
            # For all parts, we need a map of ALL retail parts to company names
            all_mappings = InvoiceRetailPartMap.objects.all()
            part_to_company = {m.retail_part_number: m.company_name for m in all_mappings}
        
        if from_date:
            entries = entries.filter(date__gte=from_date)
        if to_date:
            entries = entries.filter(date__lte=to_date)
            
        transactions = []
        for entry in entries:
            company = part_to_company.get(entry.part_number, "Retail Customer")
            
            transactions.append({
                "date": entry.date,
                "date": entry.date,
                "part_number": entry.part_number,
                "invoice_number": entry.retail_invoice_number or "N/A",
                "qty": -1 * entry.qty, # Negative
                "name": company,
                "type": "OUTGOING",
                "created_at": entry.created_at,
                "id": entry.id,
                "customer_code": "", # Outgoing doesn't usually have a customer code in the entry itself
            })
        return transactions

    def merge_and_sort(self, incoming, outgoing):
        """
        Combine two lists and sort by date.
        """
        all_txns = incoming + outgoing
        # Sort by Date, then by Created At
        all_txns.sort(key=lambda x: (x['date'], x['created_at'] or datetime.min))
        return all_txns

class BalanceCalculator:
    """
    Helper class to calculate running balance.
    """
    
    def calculate_running_balance(self, transactions):
        """
        Iterate through sorted transactions and add 'on_hand' field.
        """
        balance = 0
        result = []
        for txn in transactions:
            balance += txn['qty']
            txn_with_balance = txn.copy()
            txn_with_balance['on_hand'] = balance
            result.append(txn_with_balance)
        return result
