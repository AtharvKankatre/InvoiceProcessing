import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sap_invoice.settings')
django.setup()

from sales.models import Invoice

def update_names():
    # Update "Alpha Tech Solutions" -> "Global Electronics"
    count1 = Invoice.objects.filter(customer_name="Alpha Tech Solutions").update(customer_name="Global Electronics")
    print(f"Updated {count1} records from 'Alpha Tech Solutions' to 'Global Electronics'")

    # Update "Beta Innovations Inc" -> "City Infrastructure Ltd"
    count2 = Invoice.objects.filter(customer_name="Beta Innovations Inc").update(customer_name="City Infrastructure Ltd")
    print(f"Updated {count2} records from 'Beta Innovations Inc' to 'City Infrastructure Ltd'")

    # Also check for "Inpinite" just in case it exists in name or code
    count3 = Invoice.objects.filter(customer_name__icontains="Inpinite").update(customer_name="Global Electronics")
    if count3 > 0:
        print(f"Updated {count3} records containing 'Inpinite' to 'Global Electronics'")

if __name__ == "__main__":
    update_names()
