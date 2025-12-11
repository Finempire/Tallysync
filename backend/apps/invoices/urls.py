from django.urls import path
from .models import (InvoiceUploadView, InvoiceListView, InvoiceDetailView,
                     InvoiceApproveView, InvoiceCreateVoucherView, BulkInvoiceUploadView)

urlpatterns = [
    path('upload/', InvoiceUploadView.as_view(), name='upload'),
    path('bulk-upload/', BulkInvoiceUploadView.as_view(), name='bulk-upload'),
    path('', InvoiceListView.as_view(), name='invoice-list'),
    path('<int:pk>/', InvoiceDetailView.as_view(), name='invoice-detail'),
    path('<int:pk>/approve/', InvoiceApproveView.as_view(), name='invoice-approve'),
    path('<int:pk>/create-voucher/', InvoiceCreateVoucherView.as_view(), name='create-voucher'),
]
