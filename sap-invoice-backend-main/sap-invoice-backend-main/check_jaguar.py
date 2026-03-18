"""
Quick diagnostic: check what Jaguar invoice data looks like in the DB.
Run: python check_jaguar.py
"""
import os, sys, django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sap_invoice.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from sales.models import Invoice

jag = Invoice.objects.filter(customer_name__icontains='jaguar').order_by('date')[:5]

print(f"Found {Invoice.objects.filter(customer_name__icontains='jaguar').count()} total Jaguar invoices\n")

for inv in jag:
    print(f"Invoice: {inv.invoice_number} | Date: {inv.date}")
    print(f"  Qty: {inv.qty} | Invoice Qty: {inv.invoice_qty}")
    print(f"  dollar_rate: {inv.dollar_rate} | dollar_total: {inv.dollar_total}")
    print(f"  inr_rate: {inv.inr_rate} | inr_total: {inv.inr_total}")
    print(f"  conversion_rate: {inv.conversion_rate}")
    print()
