from rest_framework import serializers

from sales.serializers import InvoiceEntryConsumptionSerializer
from .models import InvoiceEntry


# class InvoiceEntrySerializer(serializers.ModelSerializer):
#     class Meta:
#         model = InvoiceEntry
#         fields = '__all__'


# class InvoiceEntrySerializer(serializers.ModelSerializer):
#     class Meta:
#         model = InvoiceEntry
#         fields = '__all__'
#         read_only_fields = ['usd_total', 'inr_rate', 'inr_total']  # prevent client from sending them
#
#     def validate(self, data):
#         qty = data.get('qty')
#         usd_rate = data.get('usd_rate')
#         conversion_rate = data.get('conversion_rate')
#
#         if qty is None or usd_rate is None or conversion_rate is None:
#             raise serializers.ValidationError("qty, usd_rate, and conversion_rate are required.")
#
#         # Auto-calculate
#         usd_total = round(qty * usd_rate, 2)
#         inr_rate = round(usd_rate * conversion_rate, 2)
#         inr_total = round(usd_total * conversion_rate, 2)
#
#         data['usd_total'] = usd_total
#         data['inr_rate'] = inr_rate
#         data['inr_total'] = inr_total
#
#         return data

from rest_framework import serializers
from .models import InvoiceEntry
from sales.models import InvoiceRetailPartMap


class InvoiceEntrySerializer(serializers.ModelSerializer):
    # include which invoices were consumed to complete this sale
    class Meta:
        model = InvoiceEntry
        fields = "__all__"
        read_only_fields = [
            "usd_rate",
            "usd_total",
            "inr_total",
            "customer_name",
            "customer_code",
        ]

    customer_name = serializers.SerializerMethodField()
    customer_code = serializers.SerializerMethodField()

    def get_customer_name(self, obj):
        # Try to find map where obj.part_number is sale_part_number
        map_obj = InvoiceRetailPartMap.objects.filter(sale_part_number=obj.part_number).first()
        if not map_obj:
             # Try where obj.part_number is retail_part_number
             map_obj = InvoiceRetailPartMap.objects.filter(retail_part_number=obj.part_number).first()
        return map_obj.company_name if map_obj else None

    def get_customer_code(self, obj):
        # Retail transactions might not have a code, return None or empty
        return None

    consumptions = InvoiceEntryConsumptionSerializer(many=True, required=False)

    def validate(self, data):
        qty = data.get("qty")
        if qty is None:
            raise serializers.ValidationError("Field 'qty' is required.")
        return data

    def create(self, validated_data):
        # Don't compute any pricing here — it's handled in the view based on actual invoice(s)
        return super().create(validated_data)
