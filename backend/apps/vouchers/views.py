
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import transaction
from django.utils import timezone
from .models import Voucher, VoucherSettings
from .serializers import (
    VoucherSerializer, VoucherCreateSerializer, VoucherSettingsSerializer
)

class VoucherListCreateView(generics.ListCreateAPIView):
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return VoucherCreateSerializer
        return VoucherSerializer
    
    def get_queryset(self):
        queryset = Voucher.objects.all()
        company_id = self.request.query_params.get('company')
        if company_id:
            queryset = queryset.filter(company_id=company_id)
        
        voucher_status = self.request.query_params.get('status')
        if voucher_status:
            if voucher_status == 'unverified':
                 queryset = queryset.filter(status='draft') # Or specific unverified logic
            else:
                 queryset = queryset.filter(status=voucher_status)
                 
        type_filter = self.request.query_params.get('type')
        if type_filter:
             if type_filter == 'sales':
                  queryset = queryset.filter(voucher_type__in=['sales', 'credit_note'])
             elif type_filter == 'purchase':
                  queryset = queryset.filter(voucher_type__in=['purchase', 'debit_note'])
             elif type_filter == 'journal':
                  queryset = queryset.filter(voucher_type__in=['journal', 'payment', 'receipt', 'contra'])

        return queryset.select_related('company', 'party_ledger').order_by('-date', '-created_at')
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, source='manual')


class VoucherDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = VoucherSerializer
    queryset = Voucher.objects.all()


class VoucherApproveView(APIView):
    def post(self, request, pk):
        voucher = Voucher.objects.get(pk=pk)
        if voucher.status not in ['draft', 'pending_approval']:
            return Response({'error': 'Voucher not pending approval'}, status=400)
        
        voucher.status = 'approved'
        voucher.approved_by = request.user
        voucher.approved_at = timezone.now()
        voucher.save()
        return Response({'message': 'Voucher approved', 'voucher': VoucherSerializer(voucher).data})


class VoucherBulkApproveView(APIView):
    @transaction.atomic
    def post(self, request):
        voucher_ids = request.data.get('voucher_ids', [])
        updated = Voucher.objects.filter(
            id__in=voucher_ids, status__in=['draft', 'pending_approval']
        ).update(status='approved', approved_by=request.user, approved_at=timezone.now())
        return Response({'message': f'{updated} vouchers approved'})


class VoucherPushToTallyView(APIView):
    def post(self, request, pk):
        voucher = Voucher.objects.get(pk=pk)
        if voucher.status != 'approved':
            return Response({'error': 'Voucher must be approved'}, status=400)
        
        from apps.tally_connector.models import DesktopConnector, SyncOperation
        
        connector = DesktopConnector.objects.filter(company=voucher.company, status='active').first()
        if not connector:
            return Response({'error': 'No active Tally connector'}, status=400)
        
        operation = SyncOperation.objects.create(
            connector=connector,
            operation_type='create_voucher',
            voucher=voucher,
            request_xml=voucher.generate_tally_xml(),
            priority=2
        )
        
        voucher.status = 'queued'
        voucher.save()
        return Response({'message': 'Voucher queued for sync', 'operation_id': str(operation.id)})


class VoucherBulkPushToTallyView(APIView):
    @transaction.atomic
    def post(self, request):
        voucher_ids = request.data.get('voucher_ids', [])
        vouchers = Voucher.objects.filter(id__in=voucher_ids, status='approved').select_related('company')
        
        from apps.tally_connector.models import DesktopConnector, SyncOperation
        
        created = 0
        for voucher in vouchers:
            connector = DesktopConnector.objects.filter(company=voucher.company, status='active').first()
            if connector:
                SyncOperation.objects.create(
                    connector=connector, operation_type='create_voucher',
                    voucher=voucher, request_xml=voucher.generate_tally_xml(), priority=2
                )
                voucher.status = 'queued'
                voucher.save()
                created += 1
        
        return Response({'message': f'{created} vouchers queued'})


class VoucherXMLPreviewView(APIView):
    def get(self, request, pk):
        voucher = Voucher.objects.get(pk=pk)
        return Response({'xml': voucher.generate_tally_xml()})


class VoucherSettingsView(generics.RetrieveUpdateAPIView):
    serializer_class = VoucherSettingsSerializer
    lookup_field = 'company_id' if 'company_id' in 'company_id' else 'pk' # Tricky lookup logic
    
    def get_object(self):
        company_id = self.request.query_params.get('company_id')
        txn_type = self.request.query_params.get('type')
        if not company_id or not txn_type:
            return None
        
        obj, created = VoucherSettings.objects.get_or_create(
            company_id=company_id, transaction_type=txn_type
        )
        return obj

    def get(self, request, *args, **kwargs):
        obj = self.get_object()
        if not obj:
            return Response({'error': 'company_id and type required'}, status=400)
        return Response(self.get_serializer(obj).data)
        
    def put(self, request, *args, **kwargs):
        obj = self.get_object()
        if not obj:
             return Response({'error': 'company_id and type required'}, status=400)
        serializer = self.get_serializer(obj, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
