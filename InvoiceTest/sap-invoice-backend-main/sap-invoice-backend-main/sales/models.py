from django.db import models
from user.models import User


class Invoice(models.Model):
    invoice_number = models.CharField(max_length=50)
    part_number = models.CharField(max_length=100)
    date = models.DateField()
    qty = models.PositiveIntegerField()
    invoice_qty = models.PositiveIntegerField(null = True)
    dollar_rate = models.DecimalField(max_digits=30, decimal_places=15, default=0)
    conversion_rate = models.DecimalField(max_digits=30, decimal_places=15, default=0)
    dollar_total = models.DecimalField(max_digits=30, decimal_places=15, default=0)
    inr_rate = models.DecimalField(max_digits=30, decimal_places=15, default=0)
    inr_total = models.DecimalField(max_digits=30, decimal_places=15, default=0)
    customer_code = models.CharField(max_length=100, null=True, blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        related_name="sales_invoice_created_by",
    )
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)
    dnd_charges = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    customer_name = models.CharField(max_length=100, blank=True, null=True)
    plant_code = models.CharField(max_length=10, default="1002")

    # @property
    # def dollar_total(self):
    #     return round(self.qty * self.dollar_rate, 2)

    # @property
    # def inr_rate(self):
    #     return round(self.dollar_rate * self.conversion_rate, 2)

    # @property
    # def inr_total(self):
    #     return round(self.dollar_total * self.conversion_rate, 2)

    # def __str__(self):
    #     return f"Invoice {self.invoice_number} - {self.part_number}"


class InvoiceEntryConsumption(models.Model):
    invoice_entry = models.ForeignKey(
        "retail.InvoiceEntry", on_delete=models.CASCADE, related_name="consumptions"
    )
    invoice = models.ForeignKey("Invoice", on_delete=models.CASCADE)
    consumed_qty = models.PositiveIntegerField()
    selling_price_inr = models.DecimalField(max_digits=30, decimal_places=15, default=0)

    profit_absolute = models.DecimalField(max_digits=30, decimal_places=15, default=0)
    profit_selling_rate = models.DecimalField(
        max_digits=20, decimal_places=4, default=0
    )
    profit_fx_rate = models.DecimalField(max_digits=30, decimal_places=15, default=0)
    profit_fx_only = models.DecimalField(max_digits=30, decimal_places=15, default=0)
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        related_name="sales_invoice_consumption_created_by",
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        related_name="sales_invoice_consumption_updated_by",
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)
    base_value = models.DecimalField(
        max_digits=30, decimal_places=15, null=True, blank=True
    )
    dnd_charges = models.DecimalField(
        max_digits=30, decimal_places=15, null=True, blank=True
    )
    taxable_value = models.DecimalField(
        max_digits=30, decimal_places=15, null=True, blank=True
    )
    fc_value = models.DecimalField(
        max_digits=30, decimal_places=15, null=True, blank=True
    )
    fc_rate_with_discount = models.DecimalField(
        max_digits=30, decimal_places=15, null=True, blank=True
    )
    rate_sale_from_wh_per_unit = models.DecimalField(max_digits=30, decimal_places=15, null = True, blank = True)
    rate_sale_from_wh = models.DecimalField(max_digits=30, decimal_places=15, null=True, blank=True)
    diff = models.DecimalField(max_digits=30, decimal_places=15, null=True, blank=True)
    surcharge = models.DecimalField(max_digits=30, decimal_places=15, null=True, blank=True)

    def __str__(self):
        # return f"{self.consumed_qty} from {self.invoice.invoice_number} to Entry {self.invoice_entry.id}"

        return f"{self.consumed_qty}  to Entry {self.invoice_entry.id}"


class InvoiceRetailPartMap(models.Model):
    sale_part_number = models.CharField(max_length=50)
    retail_part_number = models.CharField(max_length=50)
    company_name = models.CharField(max_length=50)
    customer_code = models.CharField(max_length=50, null=True, blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        related_name="invoice_retail_part_map_created_by",
    )
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)
