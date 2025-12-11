"""
Tally Connector App - Complete Implementation
Desktop Connector, Sync Operations, XML Builder
"""
import uuid
from datetime import date
from lxml import etree
from django.db import models
from django.utils import timezone
from rest_framework import serializers, generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny


# ============================================
# MODELS
# ============================================
class DesktopConnector(models.Model):
    STATUS_CHOICES = [('active', 'Active'), ('inactive', 'Inactive'), ('disconnected', 'Disconnected')]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='connectors')
    name = models.CharField(max_length=100)
    machine_name = models.CharField(max_length=100, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    tally_host = models.CharField(max_length=100, default='localhost')
    tally_port = models.IntegerField(default=9000)
    tally_company_name = models.CharField(max_length=200, blank=True)
    api_key = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='inactive')
    last_heartbeat = models.DateTimeField(null=True, blank=True)
    last_sync = models.DateTimeField(null=True, blank=True)
    connector_version = models.CharField(max_length=20, blank=True)
    tally_version = models.CharField(max_length=20, blank=True)
    total_operations = models.IntegerField(default=0)
    successful_operations = models.IntegerField(default=0)
    failed_operations = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.company.name})"

    def generate_api_key(self):
        import secrets
        self.api_key = secrets.token_urlsafe(32)
        return self.api_key


class SyncOperation(models.Model):
    OPERATION_TYPES = [
        ('create_voucher', 'Create Voucher'), ('update_voucher', 'Update Voucher'),
        ('delete_voucher', 'Delete Voucher'), ('sync_ledgers', 'Sync Ledgers'),
        ('sync_masters', 'Sync Masters'), ('export_report', 'Export Report'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'), ('in_progress', 'In Progress'),
        ('completed', 'Completed'), ('failed', 'Failed'), ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    connector = models.ForeignKey(DesktopConnector, on_delete=models.CASCADE, related_name='operations')
    operation_type = models.CharField(max_length=30, choices=OPERATION_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    priority = models.IntegerField(default=2)
    request_data = models.JSONField(default=dict)
    request_xml = models.TextField(blank=True)
    response_data = models.JSONField(default=dict, blank=True)
    response_xml = models.TextField(blank=True)
    error_message = models.TextField(blank=True)
    voucher = models.ForeignKey('vouchers.Voucher', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    retry_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=3)


class TallyMaster(models.Model):
    MASTER_TYPES = [
        ('ledger', 'Ledger'), ('group', 'Group'), ('cost_center', 'Cost Center'),
        ('voucher_type', 'Voucher Type'), ('stock_item', 'Stock Item'),
    ]
    
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='tally_masters')
    master_type = models.CharField(max_length=30, choices=MASTER_TYPES)
    name = models.CharField(max_length=200)
    tally_guid = models.CharField(max_length=100, blank=True)
    data = models.JSONField(default=dict)
    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['company', 'master_type', 'name']


# ============================================
# XML BUILDER
# ============================================
class TallyXMLBuilder:
    def __init__(self):
        self.envelope = None
    
    def _create_envelope(self, request_type='Import', request_id='All'):
        self.envelope = etree.Element('ENVELOPE')
        header = etree.SubElement(self.envelope, 'HEADER')
        etree.SubElement(header, 'TALLYREQUEST').text = request_type
        etree.SubElement(header, 'TYPE').text = 'Data'
        etree.SubElement(header, 'ID').text = request_id
        body = etree.SubElement(self.envelope, 'BODY')
        data = etree.SubElement(body, 'DATA')
        return data
    
    def _format_date(self, d: date) -> str:
        return d.strftime('%Y%m%d')
    
    def to_string(self) -> str:
        return etree.tostring(self.envelope, pretty_print=True, xml_declaration=True, encoding='UTF-8').decode('utf-8')


class VoucherXMLBuilder(TallyXMLBuilder):
    VOUCHER_TYPE_MAP = {
        'payment': 'Payment', 'receipt': 'Receipt', 'journal': 'Journal',
        'contra': 'Contra', 'sales': 'Sales', 'purchase': 'Purchase',
        'credit_note': 'Credit Note', 'debit_note': 'Debit Note', 'payroll': 'Payroll',
    }
    
    def __init__(self, voucher):
        super().__init__()
        self.voucher = voucher
    
    def build(self) -> str:
        data = self._create_envelope('Import', 'Vouchers')
        tally_msg = etree.SubElement(data, 'TALLYMESSAGE')
        
        voucher_elem = etree.SubElement(tally_msg, 'VOUCHER')
        voucher_elem.set('VCHTYPE', self.VOUCHER_TYPE_MAP.get(self.voucher.voucher_type, 'Journal'))
        voucher_elem.set('ACTION', 'Create')
        
        etree.SubElement(voucher_elem, 'DATE').text = self._format_date(self.voucher.date)
        etree.SubElement(voucher_elem, 'VOUCHERTYPENAME').text = self.VOUCHER_TYPE_MAP.get(self.voucher.voucher_type, 'Journal')
        
        if self.voucher.voucher_number:
            etree.SubElement(voucher_elem, 'VOUCHERNUMBER').text = self.voucher.voucher_number
        if self.voucher.reference:
            etree.SubElement(voucher_elem, 'REFERENCE').text = self.voucher.reference
        if self.voucher.narration:
            etree.SubElement(voucher_elem, 'NARRATION').text = self.voucher.narration
        
        etree.SubElement(voucher_elem, 'PERSISTEDVIEW').text = 'Accounting Voucher View'
        
        for entry in self.voucher.entries.all():
            ledger_entry = etree.SubElement(voucher_elem, 'ALLLEDGERENTRIES.LIST')
            etree.SubElement(ledger_entry, 'LEDGERNAME').text = entry.ledger.name
            etree.SubElement(ledger_entry, 'ISDEEMEDPOSITIVE').text = 'Yes' if entry.is_debit else 'No'
            amount = float(entry.amount)
            if entry.is_debit:
                amount = -amount
            etree.SubElement(ledger_entry, 'AMOUNT').text = str(amount)
        
        return self.to_string()


class LedgerSyncXMLBuilder(TallyXMLBuilder):
    def build_export_request(self, company_name: str) -> str:
        self.envelope = etree.Element('ENVELOPE')
        header = etree.SubElement(self.envelope, 'HEADER')
        etree.SubElement(header, 'TALLYREQUEST').text = 'Export'
        etree.SubElement(header, 'TYPE').text = 'Collection'
        etree.SubElement(header, 'ID').text = 'Ledger Collection'
        
        body = etree.SubElement(self.envelope, 'BODY')
        desc = etree.SubElement(body, 'DESC')
        static_vars = etree.SubElement(desc, 'STATICVARIABLES')
        etree.SubElement(static_vars, 'SVCURRENTCOMPANY').text = company_name
        
        tdl = etree.SubElement(desc, 'TDL')
        tdl_msg = etree.SubElement(tdl, 'TDLMESSAGE')
        collection = etree.SubElement(tdl_msg, 'COLLECTION')
        collection.set('NAME', 'Ledger Collection')
        etree.SubElement(collection, 'TYPE').text = 'Ledger'
        etree.SubElement(collection, 'FETCH').text = 'NAME, PARENT, OPENINGBALANCE, GUID'
        
        return self.to_string()


def parse_tally_response(xml_string: str) -> dict:
    result = {'success': False, 'errors': [], 'data': {}, 'imported_count': 0}
    try:
        root = etree.fromstring(xml_string.encode('utf-8'))
        for error in root.findall('.//LINEERROR'):
            result['errors'].append(error.text)
        import_result = root.find('.//IMPORTRESULT')
        if import_result is not None:
            created = import_result.find('CREATED')
            if created is not None:
                result['imported_count'] = int(created.text or 0)
                result['success'] = result['imported_count'] > 0
        if not result['errors']:
            result['success'] = True
    except Exception as e:
        result['errors'].append(str(e))
    return result


# ============================================
# SERIALIZERS
# ============================================
class DesktopConnectorSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company.name', read_only=True)
    
    class Meta:
        model = DesktopConnector
        fields = '__all__'
        read_only_fields = ['id', 'api_key', 'status', 'last_heartbeat', 'created_at']


class SyncOperationSerializer(serializers.ModelSerializer):
    class Meta:
        model = SyncOperation
        fields = '__all__'


# ============================================
# VIEWS
# ============================================
class ConnectorListCreateView(generics.ListCreateAPIView):
    serializer_class = DesktopConnectorSerializer
    
    def get_queryset(self):
        return DesktopConnector.objects.all()
    
    def perform_create(self, serializer):
        connector = serializer.save()
        connector.generate_api_key()
        connector.save()


class ConnectorDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = DesktopConnectorSerializer
    queryset = DesktopConnector.objects.all()


class ConnectorHeartbeatView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        api_key = request.data.get('api_key')
        try:
            connector = DesktopConnector.objects.get(api_key=api_key)
            connector.status = 'active'
            connector.last_heartbeat = timezone.now()
            connector.machine_name = request.data.get('machine_name', connector.machine_name)
            connector.connector_version = request.data.get('connector_version', connector.connector_version)
            connector.tally_version = request.data.get('tally_version', connector.tally_version)
            connector.save()
            return Response({'status': 'ok', 'connector_id': str(connector.id)})
        except DesktopConnector.DoesNotExist:
            return Response({'error': 'Invalid API key'}, status=401)


class PendingOperationsView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        api_key = request.data.get('api_key')
        limit = request.data.get('limit', 10)
        
        try:
            connector = DesktopConnector.objects.get(api_key=api_key)
        except DesktopConnector.DoesNotExist:
            return Response({'error': 'Invalid API key'}, status=401)
        
        operations = SyncOperation.objects.filter(
            connector=connector, status='pending'
        ).order_by('-priority', 'created_at')[:limit]
        
        operations.update(status='in_progress', started_at=timezone.now())
        
        return Response({
            'operations': [{
                'id': str(op.id),
                'operation_type': op.operation_type,
                'request_xml': op.request_xml,
                'request_data': op.request_data
            } for op in operations]
        })


class OperationResultView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        api_key = request.data.get('api_key')
        operation_id = request.data.get('operation_id')
        op_status = request.data.get('status')
        response_xml = request.data.get('response_xml', '')
        error_message = request.data.get('error_message', '')
        
        try:
            connector = DesktopConnector.objects.get(api_key=api_key)
        except DesktopConnector.DoesNotExist:
            return Response({'error': 'Invalid API key'}, status=401)
        
        try:
            operation = SyncOperation.objects.get(id=operation_id, connector=connector)
        except SyncOperation.DoesNotExist:
            return Response({'error': 'Operation not found'}, status=404)
        
        operation.status = op_status
        operation.response_xml = response_xml
        operation.error_message = error_message
        operation.completed_at = timezone.now()
        operation.save()
        
        connector.total_operations += 1
        if op_status == 'completed':
            connector.successful_operations += 1
            if operation.voucher:
                operation.voucher.status = 'synced'
                operation.voucher.sync_completed_at = timezone.now()
                result = parse_tally_response(response_xml)
                if result.get('created_guids'):
                    operation.voucher.tally_guid = result['created_guids'][0]
                operation.voucher.save()
        else:
            connector.failed_operations += 1
            if operation.voucher:
                operation.voucher.status = 'failed'
                operation.voucher.sync_error = error_message
                operation.voucher.save()
        
        connector.last_sync = timezone.now()
        connector.save()
        
        return Response({'status': 'ok'})
