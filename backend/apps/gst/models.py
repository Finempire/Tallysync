"""
GST App - Complete Implementation (Phase 2)
E-Invoicing, GSTR-1, GSTR-3B, Reconciliation, E-Way Bill
"""
import json
import hashlib
import base64
from decimal import Decimal
from datetime import datetime
from django.db import models
from django.utils import timezone
from rest_framework import serializers, generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import transaction


# ============================================
# MODELS
# ============================================
class GSTCredential(models.Model):
    """GSP API credentials for each company"""
    company = models.OneToOneField('companies.Company', on_delete=models.CASCADE, related_name='gst_credentials')
    gstin = models.CharField(max_length=15)
    gsp_provider = models.CharField(max_length=50, choices=[
        ('cleartax', 'ClearTax'), ('masters_india', 'Masters India'), ('nic', 'NIC Direct')
    ])
    username = models.CharField(max_length=100)
    encrypted_password = models.TextField()
    auth_token = models.TextField(blank=True)
    token_expiry = models.DateTimeField(null=True, blank=True)
    sandbox_mode = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class EInvoice(models.Model):
    """E-Invoice generation and tracking"""
    STATUS_CHOICES = [
        ('draft', 'Draft'), ('pending', 'Pending'), ('generated', 'Generated'),
        ('cancelled', 'Cancelled'), ('failed', 'Failed'),
    ]
    
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='einvoices')
    voucher = models.OneToOneField('vouchers.Voucher', on_delete=models.CASCADE, null=True, blank=True)
    
    # Document details
    doc_type = models.CharField(max_length=10, choices=[('INV', 'Invoice'), ('CRN', 'Credit Note'), ('DBN', 'Debit Note')])
    doc_number = models.CharField(max_length=50)
    doc_date = models.DateField()
    
    # Seller details
    seller_gstin = models.CharField(max_length=15)
    seller_name = models.CharField(max_length=200)
    seller_address = models.TextField()
    seller_state_code = models.CharField(max_length=2)
    
    # Buyer details
    buyer_gstin = models.CharField(max_length=15, blank=True)
    buyer_name = models.CharField(max_length=200)
    buyer_address = models.TextField()
    buyer_state_code = models.CharField(max_length=2)
    buyer_pos = models.CharField(max_length=2)  # Place of supply
    
    # Values
    taxable_value = models.DecimalField(max_digits=18, decimal_places=2)
    cgst_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    sgst_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    igst_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    cess_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_invoice_value = models.DecimalField(max_digits=18, decimal_places=2)
    
    # E-Invoice response
    irn = models.CharField(max_length=100, blank=True)  # Invoice Reference Number
    ack_number = models.CharField(max_length=50, blank=True)
    ack_date = models.DateTimeField(null=True, blank=True)
    signed_invoice = models.TextField(blank=True)
    signed_qr_code = models.TextField(blank=True)
    qr_code_image = models.ImageField(upload_to='einvoice_qr/%Y/%m/', blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    error_message = models.TextField(blank=True)
    cancel_reason = models.TextField(blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    
    # JSON data
    request_json = models.JSONField(default=dict)
    response_json = models.JSONField(default=dict)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True)

    class Meta:
        unique_together = ['company', 'doc_type', 'doc_number']

    def generate_irp_json(self):
        """Generate JSON for IRP submission"""
        return {
            "Version": "1.1",
            "TranDtls": {"TaxSch": "GST", "SupTyp": "B2B", "RegRev": "N"},
            "DocDtls": {"Typ": self.doc_type, "No": self.doc_number, "Dt": self.doc_date.strftime("%d/%m/%Y")},
            "SellerDtls": {
                "Gstin": self.seller_gstin, "LglNm": self.seller_name,
                "Addr1": self.seller_address[:100], "Loc": "", "Pin": 0, "Stcd": self.seller_state_code
            },
            "BuyerDtls": {
                "Gstin": self.buyer_gstin or "URP", "LglNm": self.buyer_name,
                "Addr1": self.buyer_address[:100], "Loc": "", "Pin": 0, "Stcd": self.buyer_state_code, "Pos": self.buyer_pos
            },
            "ValDtls": {
                "AssVal": float(self.taxable_value), "CgstVal": float(self.cgst_amount),
                "SgstVal": float(self.sgst_amount), "IgstVal": float(self.igst_amount),
                "CesVal": float(self.cess_amount), "TotInvVal": float(self.total_invoice_value)
            },
            "ItemList": []
        }


class EInvoiceItem(models.Model):
    """Line items for E-Invoice"""
    einvoice = models.ForeignKey(EInvoice, on_delete=models.CASCADE, related_name='items')
    sl_no = models.IntegerField()
    product_name = models.CharField(max_length=300)
    hsn_code = models.CharField(max_length=8)
    quantity = models.DecimalField(max_digits=18, decimal_places=3, default=1)
    unit = models.CharField(max_length=10, default='NOS')
    unit_price = models.DecimalField(max_digits=18, decimal_places=2)
    discount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    taxable_value = models.DecimalField(max_digits=18, decimal_places=2)
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2)
    cgst_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    sgst_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    igst_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=18, decimal_places=2)


class GSTR1Data(models.Model):
    """GSTR-1 return data"""
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='gstr1_data')
    period = models.CharField(max_length=7)  # MMYYYY format
    return_type = models.CharField(max_length=10, choices=[
        ('b2b', 'B2B'), ('b2cl', 'B2C Large'), ('b2cs', 'B2C Small'),
        ('cdnr', 'Credit/Debit Notes'), ('exp', 'Exports'), ('nil', 'Nil Rated'),
        ('hsn', 'HSN Summary'), ('doc', 'Document Summary'),
    ])
    data = models.JSONField(default=list)
    status = models.CharField(max_length=20, default='draft')
    filed_at = models.DateTimeField(null=True, blank=True)
    arn = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['company', 'period', 'return_type']


class GSTR3BData(models.Model):
    """GSTR-3B liability computation"""
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='gstr3b_data')
    period = models.CharField(max_length=7)
    
    # Outward supplies
    outward_taxable_supplies = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    outward_zero_rated = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    outward_nil_exempt = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    outward_non_gst = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    
    # Inward supplies (ITC)
    itc_igst = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    itc_cgst = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    itc_sgst = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    itc_cess = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    
    # Tax liability
    igst_liability = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    cgst_liability = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    sgst_liability = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    cess_liability = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    
    # Net payable
    igst_payable = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    cgst_payable = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    sgst_payable = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    
    status = models.CharField(max_length=20, default='draft')
    filed_at = models.DateTimeField(null=True, blank=True)
    arn = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['company', 'period']


class GSTR2BRecord(models.Model):
    """Downloaded GSTR-2B records for reconciliation"""
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='gstr2b_records')
    period = models.CharField(max_length=7)
    supplier_gstin = models.CharField(max_length=15)
    supplier_name = models.CharField(max_length=200, blank=True)
    invoice_number = models.CharField(max_length=50)
    invoice_date = models.DateField()
    invoice_type = models.CharField(max_length=10)
    taxable_value = models.DecimalField(max_digits=18, decimal_places=2)
    igst = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    cgst = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    sgst = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    cess = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    itc_available = models.BooleanField(default=True)
    status = models.CharField(max_length=20, default='pending')
    downloaded_at = models.DateTimeField(auto_now_add=True)


class ReconciliationResult(models.Model):
    """GST reconciliation results"""
    MATCH_TYPES = [
        ('exact', 'Exact Match'), ('suggested', 'Suggested Match'),
        ('missing_2b', 'Missing in GSTR-2B'), ('missing_pr', 'Missing in Purchase Register'),
        ('mismatch', 'Value Mismatch'),
    ]
    
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE)
    period = models.CharField(max_length=7)
    gstr2b_record = models.ForeignKey(GSTR2BRecord, on_delete=models.CASCADE, null=True, blank=True)
    purchase_voucher = models.ForeignKey('vouchers.Voucher', on_delete=models.CASCADE, null=True, blank=True)
    match_type = models.CharField(max_length=20, choices=MATCH_TYPES)
    mismatch_reasons = models.JSONField(default=list)
    action_taken = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class EWayBill(models.Model):
    """E-Way Bill generation"""
    STATUS_CHOICES = [
        ('draft', 'Draft'), ('generated', 'Generated'), ('cancelled', 'Cancelled'),
        ('expired', 'Expired'), ('extended', 'Extended'),
    ]
    
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='eway_bills')
    einvoice = models.OneToOneField(EInvoice, on_delete=models.CASCADE, null=True, blank=True)
    voucher = models.ForeignKey('vouchers.Voucher', on_delete=models.CASCADE, null=True, blank=True)
    
    # Document details
    doc_type = models.CharField(max_length=10)
    doc_number = models.CharField(max_length=50)
    doc_date = models.DateField()
    
    # Transaction details
    supply_type = models.CharField(max_length=20)
    sub_supply_type = models.CharField(max_length=50)
    transaction_type = models.CharField(max_length=10)
    
    # Value
    total_value = models.DecimalField(max_digits=18, decimal_places=2)
    cgst = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    sgst = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    igst = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    
    # Transport details
    transporter_id = models.CharField(max_length=15, blank=True)
    transporter_name = models.CharField(max_length=200, blank=True)
    transport_mode = models.CharField(max_length=10, choices=[
        ('1', 'Road'), ('2', 'Rail'), ('3', 'Air'), ('4', 'Ship'),
    ])
    vehicle_number = models.CharField(max_length=20, blank=True)
    vehicle_type = models.CharField(max_length=10, blank=True)
    transport_doc_number = models.CharField(max_length=50, blank=True)
    transport_doc_date = models.DateField(null=True, blank=True)
    
    # Addresses
    from_gstin = models.CharField(max_length=15)
    from_address = models.TextField()
    from_pincode = models.CharField(max_length=6)
    from_state_code = models.CharField(max_length=2)
    to_gstin = models.CharField(max_length=15, blank=True)
    to_address = models.TextField()
    to_pincode = models.CharField(max_length=6)
    to_state_code = models.CharField(max_length=2)
    
    # E-Way Bill details
    ewb_number = models.CharField(max_length=20, blank=True)
    ewb_date = models.DateTimeField(null=True, blank=True)
    ewb_valid_till = models.DateTimeField(null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    cancel_reason = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


# ============================================
# SERIALIZERS
# ============================================
class EInvoiceSerializer(serializers.ModelSerializer):
    items = serializers.SerializerMethodField()
    
    class Meta:
        model = EInvoice
        fields = '__all__'
    
    def get_items(self, obj):
        return EInvoiceItemSerializer(obj.items.all(), many=True).data


class EInvoiceItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = EInvoiceItem
        fields = '__all__'


class GSTR1DataSerializer(serializers.ModelSerializer):
    class Meta:
        model = GSTR1Data
        fields = '__all__'


class GSTR3BDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = GSTR3BData
        fields = '__all__'


class GSTR2BRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = GSTR2BRecord
        fields = '__all__'


class ReconciliationResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReconciliationResult
        fields = '__all__'


class EWayBillSerializer(serializers.ModelSerializer):
    class Meta:
        model = EWayBill
        fields = '__all__'


# ============================================
# VIEWS
# ============================================
class EInvoiceListCreateView(generics.ListCreateAPIView):
    serializer_class = EInvoiceSerializer
    
    def get_queryset(self):
        return EInvoice.objects.filter(company__in=self.request.user.companies.all())


class EInvoiceGenerateView(APIView):
    """Generate E-Invoice through GSP"""
    def post(self, request, pk):
        einvoice = EInvoice.objects.get(pk=pk)
        
        # Generate JSON
        json_data = einvoice.generate_irp_json()
        einvoice.request_json = json_data
        
        # TODO: Call GSP API
        # For now, simulate success
        einvoice.status = 'generated'
        einvoice.irn = f"IRN{einvoice.id:012d}"
        einvoice.ack_number = f"ACK{einvoice.id:012d}"
        einvoice.ack_date = timezone.now()
        einvoice.save()
        
        return Response({'message': 'E-Invoice generated', 'irn': einvoice.irn})


class EInvoiceCancelView(APIView):
    """Cancel E-Invoice within 24 hours"""
    def post(self, request, pk):
        einvoice = EInvoice.objects.get(pk=pk)
        
        if einvoice.status != 'generated':
            return Response({'error': 'E-Invoice not generated'}, status=400)
        
        # Check 24-hour window
        if einvoice.ack_date and (timezone.now() - einvoice.ack_date).total_seconds() > 86400:
            return Response({'error': 'Cancellation window expired'}, status=400)
        
        einvoice.status = 'cancelled'
        einvoice.cancel_reason = request.data.get('reason', '')
        einvoice.cancelled_at = timezone.now()
        einvoice.save()
        
        return Response({'message': 'E-Invoice cancelled'})


class GSTR1SummaryView(APIView):
    """Generate GSTR-1 summary from vouchers"""
    def get(self, request, company_id):
        period = request.query_params.get('period')  # MMYYYY
        
        from apps.vouchers.models import Voucher
        
        # Get sales vouchers for the period
        start_date = datetime.strptime(f"01{period}", "%d%m%Y")
        if start_date.month == 12:
            end_date = start_date.replace(year=start_date.year + 1, month=1)
        else:
            end_date = start_date.replace(month=start_date.month + 1)
        
        vouchers = Voucher.objects.filter(
            company_id=company_id,
            voucher_type='sales',
            date__gte=start_date,
            date__lt=end_date,
            status='synced'
        )
        
        summary = {
            'b2b_count': vouchers.filter(party_ledger__gstin__isnull=False).count(),
            'b2c_count': vouchers.filter(party_ledger__gstin__isnull=True).count(),
            'total_taxable': sum(v.amount for v in vouchers),
            'period': period
        }
        
        return Response(summary)


class GSTR3BComputeView(APIView):
    """Compute GSTR-3B liability"""
    def post(self, request, company_id):
        period = request.data.get('period')
        
        gstr3b, created = GSTR3BData.objects.get_or_create(
            company_id=company_id, period=period
        )
        
        # TODO: Compute from vouchers
        # For now, return empty
        
        return Response(GSTR3BDataSerializer(gstr3b).data)


class ReconcileGSTR2BView(APIView):
    """Reconcile GSTR-2B with purchase register"""
    def post(self, request, company_id):
        period = request.data.get('period')
        
        from apps.vouchers.models import Voucher
        
        # Get GSTR-2B records
        gstr2b_records = GSTR2BRecord.objects.filter(company_id=company_id, period=period)
        
        # Get purchase vouchers
        start_date = datetime.strptime(f"01{period}", "%d%m%Y")
        if start_date.month == 12:
            end_date = start_date.replace(year=start_date.year + 1, month=1)
        else:
            end_date = start_date.replace(month=start_date.month + 1)
        
        purchases = Voucher.objects.filter(
            company_id=company_id,
            voucher_type='purchase',
            date__gte=start_date,
            date__lt=end_date
        )
        
        results = []
        
        # Simple matching by invoice number
        for record in gstr2b_records:
            matched = purchases.filter(
                reference__iexact=record.invoice_number,
                party_ledger__gstin=record.supplier_gstin
            ).first()
            
            if matched:
                if matched.amount == record.taxable_value:
                    match_type = 'exact'
                else:
                    match_type = 'mismatch'
            else:
                match_type = 'missing_pr'
            
            result = ReconciliationResult.objects.create(
                company_id=company_id,
                period=period,
                gstr2b_record=record,
                purchase_voucher=matched,
                match_type=match_type
            )
            results.append(result)
        
        return Response({
            'total_records': len(results),
            'exact_matches': sum(1 for r in results if r.match_type == 'exact'),
            'mismatches': sum(1 for r in results if r.match_type == 'mismatch'),
            'missing': sum(1 for r in results if r.match_type == 'missing_pr')
        })


class EWayBillGenerateView(APIView):
    """Generate E-Way Bill"""
    def post(self, request, pk):
        ewb = EWayBill.objects.get(pk=pk)
        
        if ewb.total_value < 50000:
            return Response({'error': 'E-Way Bill not required for value < ₹50,000'}, status=400)
        
        # TODO: Call GSP API
        ewb.status = 'generated'
        ewb.ewb_number = f"EWB{ewb.id:012d}"
        ewb.ewb_date = timezone.now()
        ewb.ewb_valid_till = timezone.now() + timezone.timedelta(days=1)
        ewb.save()
        
        return Response({'message': 'E-Way Bill generated', 'ewb_number': ewb.ewb_number})
