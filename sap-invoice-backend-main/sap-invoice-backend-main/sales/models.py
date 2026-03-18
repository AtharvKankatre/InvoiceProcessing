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
    consumed_qty = models.IntegerField()
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


class PartWiseTracking(models.Model):
    """
    Mirrors the Part-Wise Tracking sheet from the Stock Ledger Excel export.
    Auto-refreshed whenever the Stock Ledger is exported.
    Power BI reads directly from this table.
    """
    ROW_TYPE_CHOICES = [
        ('customer_subtotal', 'Customer Subtotal'),
        ('invoice_detail', 'Invoice Detail'),
        ('part_grand_total', 'Part Grand Total'),
    ]

    row_type = models.CharField(max_length=20, choices=ROW_TYPE_CHOICES)
    customer_code = models.CharField(max_length=100, blank=True, default='')
    customer_name = models.CharField(max_length=200, blank=True, default='')
    part_number = models.CharField(max_length=100, blank=True, default='')
    invoice_number = models.CharField(max_length=100, blank=True, default='')
    invoice_date = models.CharField(max_length=20, blank=True, default='')

    # Opening
    opening_qty = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    opening_fc = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    opening_inr = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)

    # CCPL to WH (Incoming)
    ccpl_to_wh_qty = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    ccpl_to_wh_fc = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    ccpl_to_wh_inr = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    
    # Original Invoice Quantity (for Power BI)
    invoice_qty = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)

    # WH to Customer (Outgoing)
    wh_to_customer_qty = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    wh_to_customer_fc = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    wh_to_customer_inr = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)

    # Closing
    closing_qty = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    closing_fc = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    closing_inr = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)

    # Metadata
    generated_at = models.DateTimeField(auto_now=True)
    from_date = models.DateField(null=True, blank=True)
    to_date = models.DateField(null=True, blank=True)

    class Meta:
        db_table = 'sales_partwise_tracking'
        indexes = [
            models.Index(fields=['part_number']),
            models.Index(fields=['customer_name']),
            models.Index(fields=['row_type']),
        ]

    def __str__(self):
        return f"{self.row_type}: {self.part_number} - {self.customer_name}"

