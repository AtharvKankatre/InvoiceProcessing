from django.urls import path

from . import views

from .views import (
    upload_invoice_excel,
    view_invoice_file,
    view_invoices,
    dashboard,
    upload_part_map_excel,
    available_invoices,
    invoice_balance_history,
    PartHistoryViewSet,
    StockLedgerViewSet,
)

urlpatterns = [
    path("upload-invoice-excel/", upload_invoice_excel, name="upload-invoice-excel"),
    path("invoices/", view_invoice_file, name="view_invoice_file"),
    path("all-invoices/", view_invoices, name="view_all_invoices"),
    path("dashboard/", dashboard, name="dashboard"),
    path("upload-part-map-excel/", upload_part_map_excel, name="upload_part_map_excel"),
    path("available-invoices/", available_invoices, name="available_invoices"),
    path(
        "retail-part-map-list/",
        views.RetailPartMapListView.as_view(),
        name="retail-part-map_list",
    ),
    path("invoice-balance-history/", invoice_balance_history, name="invoice_balance_history"),
    path(
        "parts/<str:part_number>/history/",
        PartHistoryViewSet.as_view({'get': 'list'}),
        name="part-history"
    ),
    path(
        "parts/<str:part_number>/export/",
        PartHistoryViewSet.as_view({'get': 'export_history'}),
        name="part-history-export"
    ),
    path(
        "export-stock-ledger/",
        StockLedgerViewSet.as_view({'get': 'export_ledger'}),
        name="export-stock-ledger"
    ),
    # path('invoices/', view_invoices, name="view_invoices")
]
