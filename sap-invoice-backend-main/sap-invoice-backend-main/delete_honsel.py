"""
Run on the server:  python delete_honsel.py

Deletes ALL Martinrea Honsel Maxico data:
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

print("--- Deleting ALL Martinrea Honsel Maxico Data ---")

INVOICE_CUSTOMER_FILTER = Q(customer_name='Martinrea Honsel Maxico S.A. de C.V')

honsel_invoices = Invoice.objects.filter(INVOICE_CUSTOMER_FILTER)
inv_count = honsel_invoices.count()

if inv_count > 0:
    print(f"\nFound {inv_count} Incoming Invoices for Honsel Maxico.")
    cons_deleted, _ = InvoiceEntryConsumption.objects.filter(invoice__in=honsel_invoices).delete()
    print(f"  -> Deleted {cons_deleted} linked consumption records.")
    inv_deleted, details = honsel_invoices.delete()
    print(f"  -> Deleted {inv_deleted} Incoming Invoice records (cascaded entries included).")
else:
    print("\nNo Incoming Invoices found for Honsel.")

# ── 2. Outgoing Retail Entries ──
MAPPING_COMPANY_FILTER = Q(company_name='Martinrea Honsel Maxico S.A. de C.V')

honsel_maps = InvoiceRetailPartMap.objects.filter(MAPPING_COMPANY_FILTER)

honsel_retail_parts = list(honsel_maps.values_list('retail_part_number', flat=True))
honsel_sap_parts = list(honsel_maps.values_list('sale_part_number', flat=True))

all_honsel_parts_to_delete = list(set(honsel_retail_parts + honsel_sap_parts))

if all_honsel_parts_to_delete:
    print(f"\nFound {len(all_honsel_parts_to_delete)} total part numbers (Retail + SAP) mapped to Honsel:")
    for p in all_honsel_parts_to_delete:
        print(f"  - {p}")

    # Also delete consumption records linked to these outgoing entries
    outgoing_entries = RetailInvoiceEntry.objects.filter(part_number__in=all_honsel_parts_to_delete)
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
    print("\nNo part mappings found for Honsel.")

print("\n✅ Honsel Maxico deep-deletion complete. You can now re-upload Honsel Maxico data cleanly.")
