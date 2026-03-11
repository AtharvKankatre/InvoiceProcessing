"""Transaction merger service for part-wise transaction history."""

from sales.models import Invoice, InvoiceRetailPartMap, InvoiceEntryConsumption
from retail.models import InvoiceEntry
from datetime import datetime
from collections import defaultdict

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
            'invoice_qty',
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
            
            actual_qty = invoice['invoice_qty'] if invoice.get('invoice_qty') is not None else invoice['qty']
            
            transactions.append({
                'date': invoice['date'],
                'invoice_number': invoice['invoice_number'],
                'qty': actual_qty,
                'type': 'INCOMING',
                'created_at': invoice['created_at'],
                'name': customer_name, # Standardized key 'name' for view
                'customer_code': invoice['customer_code'] or "",
                'part_number': invoice['part_number'],
                'fc_value': invoice['dollar_total'] or 0,
                'rate_fc': float(invoice['dollar_rate'] or 0),
                'inr_value': invoice['inr_total'] or 0,
                'exchange_rate': conv_rate,
                'invoice_id': invoice['id'],  # Track DB id for consumption grouping
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
            'usd_rate',
            'inr_total',
            'conversion_rate',
            'plating_charges',
        )

        transactions = []
        for entry in invoice_entries:
            retail_pn = entry['part_number']
            company = part_to_company.get(retail_pn, "Retail Customer")
            code = part_to_code.get(retail_pn, "")
            # Normalize to SAP part number so grouping/filtering by SAP part works correctly
            sap_part = retail_to_sale.get(retail_pn, retail_pn)

            usd_rate = float(entry['usd_rate'] or 0)
            usd_total = float(entry['usd_total'] or 0)
            inr_total = float(entry['inr_total'] or 0)
            conv_rate = float(entry['conversion_rate'] or 0)
            plating = float(entry['plating_charges'] or 0)
            qty = entry['qty'] or 0

            # Adjust for plating: subtract plating portion from FC/INR
            adjusted_rate = usd_rate - plating
            adjusted_fc = usd_total - (plating * qty) if plating else usd_total
            adjusted_inr = inr_total - (plating * conv_rate * qty) if plating else inr_total

            transactions.append({
                'date': entry['date'],
                'invoice_number': entry['retail_invoice_number'] or f"OUT-{entry['date']}",
                'qty': -qty,  # Negative for outgoing
                'type': 'OUTGOING',
                'created_at': entry['created_at'],
                'name': company,
                'customer_code': code,
                'part_number': sap_part,
                'fc_value': adjusted_fc,
                'rate_fc': adjusted_rate,
                'inr_value': adjusted_inr,
                'exchange_rate': entry['conversion_rate'] or 0,
                'invoice_entry_id': entry['id'],
                'plating_charges': plating,
            })

        return transactions

    def merge_and_sort(self, incoming, outgoing):
        """
        Merge incoming and outgoing transactions using invoice-wise grouping.
        
        Uses a two-layer matching strategy:
        1. Bill-to-bill: Match outgoing invoices with '/A' suffix to their
           incoming invoice by base number (e.g., 2242500426/A → 2242500426)
        2. Split-consumption fallback: For remaining outgoing rows, use
           InvoiceEntryConsumption to split across incoming invoices by consumed_qty
        
        Args:
            incoming: List of incoming transaction dictionaries
            outgoing: List of outgoing transaction dictionaries
            
        Returns:
            Single merged list with outgoing rows grouped under their
            parent incoming invoices
        """
        if not incoming and not outgoing:
            return []

        # Sort incoming by date (FIFO: oldest first)
        incoming.sort(key=lambda x: (x['date'], x['created_at'] or datetime.min))

        # ── LAYER 1: Bill-to-bill matching by invoice number ──
        # Build lookup: incoming invoice_number -> incoming transaction
        incoming_by_invoice_num = {}
        for txn in incoming:
            inv_num = txn.get('invoice_number', '')
            if inv_num:
                incoming_by_invoice_num[inv_num] = txn

        # Try to match outgoing invoices with '/A' suffix to incoming by base number
        # e.g., outgoing "2242500426/A" → incoming "2242500426"
        bill_to_bill_map = defaultdict(list)  # incoming_invoice_number -> [outgoing txns]
        bill_to_bill_matched = set()  # track matched outgoing invoice_entry_ids

        for txn in outgoing:
            out_inv_num = txn.get('invoice_number', '')
            # Check if outgoing invoice has /A suffix (bill-to-bill pattern)
            if '/' in out_inv_num:
                base_num = out_inv_num.split('/')[0]
                if base_num in incoming_by_invoice_num:
                    bill_to_bill_map[base_num].append(txn)
                    entry_id = txn.get('invoice_entry_id')
                    if entry_id:
                        bill_to_bill_matched.add(entry_id)

        # ── LAYER 2: Split-consumption for non-bill-to-bill outgoing ──
        # Build lookup of remaining outgoing (not matched by bill-to-bill)
        outgoing_by_entry_id = {}
        for txn in outgoing:
            entry_id = txn.get('invoice_entry_id')
            if entry_id and entry_id not in bill_to_bill_matched:
                outgoing_by_entry_id[entry_id] = txn

        # Query InvoiceEntryConsumption for remaining outgoing
        incoming_ids = [txn['invoice_id'] for txn in incoming if txn.get('invoice_id')]
        outgoing_entry_ids = list(outgoing_by_entry_id.keys())

        invoice_to_consumptions = defaultdict(list)
        if incoming_ids and outgoing_entry_ids:
            consumptions = InvoiceEntryConsumption.objects.filter(
                invoice_id__in=incoming_ids,
                invoice_entry_id__in=outgoing_entry_ids,
            ).values(
                'invoice_id', 'invoice_entry_id', 'consumed_qty', 'fc_value'
            ).order_by('invoice_entry__date', 'invoice_entry_id')

            for c in consumptions:
                invoice_to_consumptions[c['invoice_id']].append({
                    'entry_id': c['invoice_entry_id'],
                    'consumed_qty': c['consumed_qty'] or 0,
                    'fc_value': float(c['fc_value'] or 0),
                })

        # ── BUILD FINAL RESULT ──
        result = []
        placed_entry_ids = set(bill_to_bill_matched)  # Already placed by bill-to-bill

        for inc_txn in incoming:
            # Add incoming row
            result.append(inc_txn)

            inv_num = inc_txn.get('invoice_number', '')
            inv_id = inc_txn.get('invoice_id')

            # LAYER 1: Add bill-to-bill matched outgoing rows (full qty, no split)
            if inv_num in bill_to_bill_map:
                for out_txn in bill_to_bill_map[inv_num]:
                    result.append(out_txn)

            # LAYER 2: Add split-consumption outgoing rows (for non-bill-to-bill)
            if inv_id and inv_id in invoice_to_consumptions:
                for cons in invoice_to_consumptions[inv_id]:
                    entry_id = cons['entry_id']
                    consumed_qty = cons['consumed_qty']

                    if entry_id not in outgoing_by_entry_id:
                        continue

                    original_txn = outgoing_by_entry_id[entry_id]
                    original_qty = abs(original_txn['qty'])

                    # Calculate proportional INR value
                    ratio = consumed_qty / original_qty if original_qty > 0 else 0
                    proportional_inr = float(original_txn.get('inr_value', 0)) * ratio

                    # Adjust fc_value for plating
                    raw_fc = cons['fc_value']
                    plating = original_txn.get('plating_charges', 0)
                    adjusted_fc = raw_fc - (plating * consumed_qty) if plating else raw_fc

                    # Create split outgoing row
                    split_txn = {
                        'date': original_txn['date'],
                        'invoice_number': original_txn['invoice_number'],
                        'qty': -consumed_qty,
                        'type': 'OUTGOING',
                        'created_at': original_txn['created_at'],
                        'name': original_txn.get('name', ''),
                        'customer_code': original_txn.get('customer_code', ''),
                        'part_number': original_txn.get('part_number', ''),
                        'fc_value': adjusted_fc,
                        'rate_fc': original_txn.get('rate_fc', 0),
                        'inr_value': proportional_inr,
                        'exchange_rate': original_txn.get('exchange_rate', 0),
                        'invoice_entry_id': entry_id,
                        'consumption_invoice_id': inv_id,
                        'plating_charges': plating,
                    }
                    result.append(split_txn)
                    placed_entry_ids.add(entry_id)  # Track for orphans check

        # Add any remaining orphan outgoing transactions
        orphans = [txn for txn in outgoing if txn.get('invoice_entry_id') not in placed_entry_ids]
        orphans.sort(key=lambda x: (x['date'], x['created_at'] or datetime.min))
        result.extend(orphans)

        return result
