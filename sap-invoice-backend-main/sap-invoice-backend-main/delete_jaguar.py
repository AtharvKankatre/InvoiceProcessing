"""
Run on the server:  python delete_jaguar.py

Deletes all Jaguar Land Rover incoming invoices (and their consumption records)
so the data can be re-uploaded with the corrected INR mapping.
"""
import os, sys, django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sap_invoice.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from sales.models import Invoice, InvoiceEntryConsumption

jag_invoices = Invoice.objects.filter(customer_name__icontains='jaguar')
count = jag_invoices.count()

print(f"Found {count} Jaguar Land Rover invoices to delete.")

if count:
    # Delete linked consumption records first
    cons_deleted, _ = InvoiceEntryConsumption.objects.filter(invoice__in=jag_invoices).delete()
    print(f"Deleted {cons_deleted} linked consumption records.")

    # Delete the invoices
    inv_deleted, _ = jag_invoices.delete()
    print(f"✅ Deleted {inv_deleted} Jaguar invoices. You can now re-upload.")
else:
    print("No Jaguar invoices found.")
