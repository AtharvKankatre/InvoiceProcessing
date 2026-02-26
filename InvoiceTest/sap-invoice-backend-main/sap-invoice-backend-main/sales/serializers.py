from rest_framework import serializers
from .models import Invoice, InvoiceEntryConsumption, InvoiceRetailPartMap


class InvoiceSerializer(serializers.ModelSerializer):
    # dollar_total = serializers.SerializerMethodField()
    # inr_rate = serializers.SerializerMethodField()
    # inr_total = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = [
            "id",
            "invoice_number",
            "part_number",
            "date",
            "qty",
            "dollar_rate",
            "conversion_rate",
            "dollar_total",
            "inr_rate",
            "inr_total",
            "inr_rate",
            "inr_total",
            "invoice_qty",
            "customer_code",
            "customer_name",
        ]

    # def get_dollar_total(self, obj):
    #     return obj.dollar_total

    # def get_inr_rate(self, obj):
    #     return obj.inr_rate

    # def get_inr_total(self, obj):
    #     return obj.inr_total


class InvoiceEntryConsumptionSerializer(serializers.ModelSerializer):
    # invoice = serializers.StringRelatedField()
    invoice = InvoiceSerializer()

    # invoice_entry = serializers.StringRelatedField()

    class Meta:
        model = InvoiceEntryConsumption
        fields = "__all__"


class InvoiceRetailPartMapSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceRetailPartMap
        fields = "__all__"
