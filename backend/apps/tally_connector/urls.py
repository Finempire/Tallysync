from django.urls import path
from django.http import FileResponse, Http404
from django.conf import settings
import os
from .models import (ConnectorListCreateView, ConnectorDetailView, ConnectorHeartbeatView,
                     PendingOperationsView, OperationResultView)
from .views_direct import (TallyStatusView, TallyCompaniesView, TallyLedgersView,
                           TallySyncLedgersView, TallyVoucherTypesView)


def download_connector(request):
    """Serve the tally-connector.zip file for download."""
    file_path = os.path.join(settings.MEDIA_ROOT, 'tally-connector.zip')
    if os.path.exists(file_path):
        return FileResponse(
            open(file_path, 'rb'),
            as_attachment=True,
            filename='tally-connector.zip',
            content_type='application/zip'
        )
    raise Http404("Connector file not found")


urlpatterns = [
    # Desktop Connector endpoints (legacy)
    path('connectors/', ConnectorListCreateView.as_view(), name='connectors'),
    path('connectors/<uuid:pk>/', ConnectorDetailView.as_view(), name='connector-detail'),
    path('heartbeat/', ConnectorHeartbeatView.as_view(), name='heartbeat'),
    path('pending-operations/', PendingOperationsView.as_view(), name='pending-operations'),
    path('operation-result/', OperationResultView.as_view(), name='operation-result'),
    path('download-connector/', download_connector, name='download-connector'),
    
    # Direct Tally Connection endpoints (no desktop connector needed)
    path('direct/status/', TallyStatusView.as_view(), name='tally-direct-status'),
    path('direct/companies/', TallyCompaniesView.as_view(), name='tally-direct-companies'),
    path('direct/ledgers/', TallyLedgersView.as_view(), name='tally-direct-ledgers'),
    path('direct/sync-ledgers/', TallySyncLedgersView.as_view(), name='tally-direct-sync-ledgers'),
    path('direct/voucher-types/', TallyVoucherTypesView.as_view(), name='tally-direct-voucher-types'),
]

