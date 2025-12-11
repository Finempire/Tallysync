from django.urls import path
from django.http import FileResponse, Http404
from django.conf import settings
import os
from .models import (BankAccountListCreateView, BankStatementUploadView, BankStatementListView,
                     TransactionListView, TransactionMapView, TransactionApproveView, GenerateVouchersView, BankStatementDetailView,
                     TransactionAutoMapView, PushStatementVouchersView)


def download_template(request):
    """Serve the bank statement template CSV file."""
    file_path = os.path.join(settings.MEDIA_ROOT, 'bank_statement_template.csv')
    if os.path.exists(file_path):
        return FileResponse(
            open(file_path, 'rb'),
            as_attachment=True,
            filename='bank_statement_template.csv',
            content_type='text/csv'
        )
    raise Http404("Template file not found")


urlpatterns = [
    path('accounts/', BankAccountListCreateView.as_view(), name='bank-accounts'),
    path('upload/', BankStatementUploadView.as_view(), name='upload'),
    path('', BankStatementListView.as_view(), name='statements'),
    path('<int:pk>/', BankStatementDetailView.as_view(), name='statement-detail'),
    path('<int:statement_id>/transactions/', TransactionListView.as_view(), name='transactions'),
    path('transactions/map/', TransactionMapView.as_view(), name='map-transactions'),
    path('transactions/auto-map/', TransactionAutoMapView.as_view(), name='auto-map-transactions'),
    path('transactions/approve/', TransactionApproveView.as_view(), name='approve-transactions'),
    path('generate-vouchers/', GenerateVouchersView.as_view(), name='generate-vouchers'),
    path('push-vouchers/', PushStatementVouchersView.as_view(), name='push-statement-vouchers'),
    path('template/', download_template, name='download-template'),
]

