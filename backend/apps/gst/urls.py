from django.urls import path
from .models import (EInvoiceListCreateView, EInvoiceGenerateView, EInvoiceCancelView,
                     GSTR1SummaryView, GSTR3BComputeView, ReconcileGSTR2BView, EWayBillGenerateView)

urlpatterns = [
    path('einvoices/', EInvoiceListCreateView.as_view(), name='einvoice-list'),
    path('einvoices/<int:pk>/generate/', EInvoiceGenerateView.as_view(), name='einvoice-generate'),
    path('einvoices/<int:pk>/cancel/', EInvoiceCancelView.as_view(), name='einvoice-cancel'),
    path('<int:company_id>/gstr1-summary/', GSTR1SummaryView.as_view(), name='gstr1-summary'),
    path('<int:company_id>/gstr3b-compute/', GSTR3BComputeView.as_view(), name='gstr3b-compute'),
    path('<int:company_id>/reconcile/', ReconcileGSTR2BView.as_view(), name='reconcile'),
    path('eway-bill/<int:pk>/generate/', EWayBillGenerateView.as_view(), name='eway-bill-generate'),
]
