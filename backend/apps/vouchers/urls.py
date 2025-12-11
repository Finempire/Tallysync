from django.urls import path
from .views import (
    VoucherListCreateView, VoucherDetailView, VoucherApproveView,
    VoucherBulkApproveView, VoucherPushToTallyView, VoucherBulkPushToTallyView, 
    VoucherXMLPreviewView, VoucherSettingsView
)
from .import_view import VoucherImportView, VoucherTemplateView
from .sales_import_views import (
    SalesImportUploadView, SalesImportDetailView, SalesImportFieldMappingView,
    SalesImportPreviewView, SalesImportGSTConfigView, SalesImportLedgerMappingView,
    SalesImportRowsView, SalesImportRowDetailView, SalesImportBulkUpdateView,
    SalesImportCreatePartyView, SalesImportCreateItemView,
    SalesImportProcessView, SalesImportPushTallyView
)

urlpatterns = [
    # Standard Voucher endpoints
    path('', VoucherListCreateView.as_view(), name='voucher-list'),
    path('template/', VoucherTemplateView.as_view(), name='voucher-template'),
    path('<int:pk>/', VoucherDetailView.as_view(), name='voucher-detail'),
    path('import/', VoucherImportView.as_view(), name='voucher-import'),
    path('settings/', VoucherSettingsView.as_view(), name='voucher-settings'),
    path('<int:pk>/approve/', VoucherApproveView.as_view(), name='voucher-approve'),
    path('bulk-approve/', VoucherBulkApproveView.as_view(), name='voucher-bulk-approve'),
    path('<int:pk>/push-tally/', VoucherPushToTallyView.as_view(), name='push-tally'),
    path('bulk-push-tally/', VoucherBulkPushToTallyView.as_view(), name='bulk-push-tally'),
    path('<int:pk>/xml-preview/', VoucherXMLPreviewView.as_view(), name='xml-preview'),
    
    # Sales Import Workflow (Suvit-style)
    path('sales-import/upload/', SalesImportUploadView.as_view(), name='sales-import-upload'),
    path('sales-import/<int:pk>/', SalesImportDetailView.as_view(), name='sales-import-detail'),
    path('sales-import/<int:pk>/field-mapping/', SalesImportFieldMappingView.as_view(), name='sales-import-field-mapping'),
    path('sales-import/<int:pk>/preview/', SalesImportPreviewView.as_view(), name='sales-import-preview'),
    path('sales-import/<int:pk>/gst-config/', SalesImportGSTConfigView.as_view(), name='sales-import-gst-config'),
    path('sales-import/<int:pk>/ledger-mapping/', SalesImportLedgerMappingView.as_view(), name='sales-import-ledger-mapping'),
    path('sales-import/<int:pk>/rows/', SalesImportRowsView.as_view(), name='sales-import-rows'),
    path('sales-import/<int:pk>/rows/<int:row_id>/', SalesImportRowDetailView.as_view(), name='sales-import-row-detail'),
    path('sales-import/<int:pk>/bulk-update/', SalesImportBulkUpdateView.as_view(), name='sales-import-bulk-update'),
    path('sales-import/<int:pk>/create-party/', SalesImportCreatePartyView.as_view(), name='sales-import-create-party'),
    path('sales-import/<int:pk>/create-item/', SalesImportCreateItemView.as_view(), name='sales-import-create-item'),
    path('sales-import/<int:pk>/process/', SalesImportProcessView.as_view(), name='sales-import-process'),
    path('sales-import/<int:pk>/push-tally/', SalesImportPushTallyView.as_view(), name='sales-import-push-tally'),
]

