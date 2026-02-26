import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sap_invoice.settings')
django.setup()

from sales.models import Invoice

def check_names():
    names = Invoice.objects.values_list('customer_name', flat=True).distinct()
    print("Existing Customer Names:")
    for name in names:
        print(f" - '{name}'")

if __name__ == "__main__":
    check_names()
