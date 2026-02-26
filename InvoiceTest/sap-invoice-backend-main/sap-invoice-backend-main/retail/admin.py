from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import InvoiceEntry

# , PurchaseCost)

admin.site.register(InvoiceEntry)
# admin.site.register(PurchaseCost)
