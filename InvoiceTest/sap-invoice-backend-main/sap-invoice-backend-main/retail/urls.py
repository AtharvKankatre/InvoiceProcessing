from django.urls import path

from . import views
from .bulk_upload import BulkTemplateView, BulkUploadView, BulkPreviewView, BulkCommitView

urlpatterns = [
    # Bulk FX Upload
    path("bulk-template/", BulkTemplateView.as_view(), name="bulk-template"),
    path("bulk-upload/", BulkUploadView.as_view(), name="bulk-upload"),
    path("bulk-preview/", BulkPreviewView.as_view(), name="bulk-preview"),
    path("bulk-upload-commit/", BulkCommitView.as_view(), name="bulk-upload-commit"),

    # path('', views.index, name='index'),
    # from .views import export_invoice_summary
    # urlpatterns += [
    # path(
    #     "export-invoice-summary/",
    #     views.export_invoice_summary,
    #     name="export-invoice-summary",
    # ),
    path(
        "invoice/create/",
        views.InvoiceEntryCreateView.as_view(),
        name="invoice-create",
    ),
    path(
        "invoice-entries/",
        views.InvoiceEntryListView.as_view(),
        name="invoice-entry-list",
    ),
    path(
        "invoice-entries/<int:id>/",
        views.InvoiceEntryDetailView.as_view(),
        name="invoice-entry-detail",
    ),
    path(
        "invoice-entry-consumptions/",
        views.InvoiceEntryConsumptionListView.as_view(),
        name="invoice-entry-consumption-list",
    ),
    path(
        "invoice-part-consumption/",
        views.part_number_summary,
        name="invoice-part-consumption",
    ),
    path(
        "invoice-entries-generate-excel/",
        views.InvoiceEntryExcelExportView.as_view(),
        name="invoice_entry_generate_excel",
    ),
    path(
        "invoice-entry-consumptions-excel/",
        views.InvoiceEntryConsumptionExcelExportView.as_view(),
        name="invoice-entry-consumptions-excel",
    ),
    path(
        "retail-invoice/export/",
        views.RetailInvoiceExportView.as_view(),
        name="retail_invoice_export",
    ),

    # retail invoice combined excel export
    path(
        "retail-invoice-combined/export/",
        views.CombinedInvoiceExportView.as_view(),
        name="retail_invoice_combined_export",
    ),
    # ]
]
