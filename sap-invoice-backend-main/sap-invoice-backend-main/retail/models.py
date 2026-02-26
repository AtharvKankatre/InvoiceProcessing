from django.db import models
from user.models import User


class InvoiceEntry(models.Model):
    # invoice_number = models.CharField(max_length=50)
    part_number = models.CharField(max_length=100)
    date = models.DateField()
    qty = models.PositiveIntegerField()
    usd_rate = models.DecimalField(max_digits=20, decimal_places=4)
    usd_total = models.DecimalField(max_digits=20, decimal_places=4)
    inr_rate = models.DecimalField(max_digits=20, decimal_places=4)
    inr_total = models.DecimalField(max_digits=20, decimal_places=4)
    conversion_rate = models.DecimalField(max_digits=20, decimal_places=4)
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        related_name="retail_invoice_entries_created_by",
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        related_name="retail_invoice_entries_updated_by",
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)
    # dnd_charges = models.DecimalField(max_digits=12, decimal_places=2)
    retail_invoice_number = models.CharField(max_length=100, null=True, blank=True)
    rate_sale_from_wh_per_unit = models.DecimalField(max_digits=20, decimal_places=4, null=True)
    rate_sale_from_wh = models.DecimalField(max_digits = 20, decimal_places = 4, null=True)
    difference = models.DecimalField(max_digits=20, decimal_places = 4, null=True)
    surcharge = models.DecimalField(max_digits=20, decimal_places = 4, null=True)
    def __str__(self):
        return f"Invoice {self.invoice_number} - {self.part_number}"

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
