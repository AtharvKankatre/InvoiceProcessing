"""
Run on the server:  python delete_wabtec_retail.py

Deletes ALL Wabtec data:
  1. Incoming invoices + their consumption records
  2. Outgoing retail entries (matched via BOTH retail-part mapping and SAP part mapping)
"""
import os, sys, django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sap_invoice.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.db.models import Q
from sales.models import Invoice, InvoiceEntryConsumption, InvoiceRetailPartMap
from retail.models import InvoiceEntry as RetailInvoiceEntry

print("--- Deleting ALL Wabtec Data ---")

# ── 1. Incoming Invoices ──
INVOICE_CUSTOMER_FILTER = Q(customer_name__icontains='Wabtec')

wabtec_invoices = Invoice.objects.filter(INVOICE_CUSTOMER_FILTER)
inv_count = wabtec_invoices.count()

if inv_count > 0:
    print(f"\nFound {inv_count} Incoming Invoices for Wabtec.")
    cons_deleted, _ = InvoiceEntryConsumption.objects.filter(invoice__in=wabtec_invoices).delete()
    print(f"  -> Deleted {cons_deleted} linked consumption records.")
    inv_deleted, details = wabtec_invoices.delete()
    print(f"  -> Deleted {inv_deleted} Incoming Invoice records (cascaded entries included).")
else:
    print("\nNo Incoming Invoices found for Wabtec.")

# ── 2. Outgoing Retail Entries ──
MAPPING_COMPANY_FILTER = Q(company_name__icontains='Wabtec')

wabtec_maps = InvoiceRetailPartMap.objects.filter(MAPPING_COMPANY_FILTER)

wabtec_retail_parts = list(wabtec_maps.values_list('retail_part_number', flat=True))
wabtec_sap_parts = list(wabtec_maps.values_list('sale_part_number', flat=True))

all_wabtec_parts = list(set(wabtec_retail_parts + wabtec_sap_parts))

if all_wabtec_parts:
    print(f"\nFound {len(all_wabtec_parts)} total part numbers (Retail + SAP) mapped to Wabtec:")
    for p in all_wabtec_parts:
        print(f"  - {p}")

    # Delete consumption records linked to outgoing entries
    outgoing_entries = RetailInvoiceEntry.objects.filter(part_number__in=all_wabtec_parts)
    cons_from_outgoing, _ = InvoiceEntryConsumption.objects.filter(invoice_entry__in=outgoing_entries).delete()
    if cons_from_outgoing:
        print(f"  -> Deleted {cons_from_outgoing} consumption records from outgoing entries.")

    ret_count = outgoing_entries.count()
    if ret_count > 0:
        ret_deleted, _ = outgoing_entries.delete()
        print(f"  -> Deleted {ret_deleted} Outgoing (Retail) entries.")
    else:
        print("  -> No Outgoing (Retail) entries found for these part numbers.")
else:
    print("\nNo part mappings found for Wabtec.")

print("\n✅ Wabtec deep-deletion complete. You can now re-upload Wabtec data cleanly.")
