"""
Invoices App - Complete Implementation (Phase 3)
Invoice OCR, Digitization, Auto-Voucher Creation
"""
import re
from decimal import Decimal
from django.db import models
from django.core.validators import FileExtensionValidator
from django.utils import timezone
from rest_framework import serializers, generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.db import transaction


# ============================================
# MODELS
# ============================================
class Invoice(models.Model):
    """Uploaded and processed invoices"""
    TYPE_CHOICES = [
        ('purchase', 'Purchase Invoice'),
        ('sales', 'Sales Invoice'),
        ('expense', 'Expense Invoice'),
    ]
    
    STATUS_CHOICES = [
        ('uploaded', 'Uploaded'),
        ('processing', 'Processing OCR'),
        ('extracted', 'Data Extracted'),
        ('validated', 'Validated'),
        ('approved', 'Approved'),
        ('voucher_created', 'Voucher Created'),
        ('failed', 'Failed'),
    ]
    
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='invoices')
    
    # File info
    file = models.FileField(
        upload_to='invoices/%Y/%m/',
        validators=[FileExtensionValidator(['pdf', 'jpg', 'jpeg', 'png'])]
    )
    original_filename = models.CharField(max_length=255)
    file_type = models.CharField(max_length=10)
    file_size = models.IntegerField()
    
    # Invoice type
    invoice_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='purchase')
    
    # Extracted data
    vendor_name = models.CharField(max_length=200, blank=True)
    vendor_gstin = models.CharField(max_length=15, blank=True)
    vendor_address = models.TextField(blank=True)
    
    invoice_number = models.CharField(max_length=100, blank=True)
    invoice_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    
    # Amounts
    subtotal = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    cgst_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    sgst_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    igst_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_tax = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    
    # Ledger mapping
    suggested_ledger = models.ForeignKey(
        'companies.Ledger', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='suggested_invoices'
    )
    mapped_ledger = models.ForeignKey(
        'companies.Ledger', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='mapped_invoices'
    )
    
    # OCR details
    ocr_provider = models.CharField(max_length=20, blank=True)
    ocr_confidence = models.FloatField(default=0)
    ocr_raw_text = models.TextField(blank=True)
    ocr_extracted_data = models.JSONField(default=dict)
    
    # Linked voucher
    voucher = models.ForeignKey(
        'vouchers.Voucher', on_delete=models.SET_NULL, null=True, blank=True
    )
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='uploaded')
    error_message = models.TextField(blank=True)
    
    # Duplicate detection
    is_duplicate = models.BooleanField(default=False)
    duplicate_of = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True
    )
    
    # Audit
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, related_name='uploaded_invoices')
    processed_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_invoices')
    approved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.vendor_name} - {self.invoice_number}"

    def check_duplicate(self):
        """Check if this invoice is a duplicate"""
        if not self.vendor_gstin or not self.invoice_number:
            return False
        
        existing = Invoice.objects.filter(
            company=self.company,
            vendor_gstin=self.vendor_gstin,
            invoice_number=self.invoice_number
        ).exclude(pk=self.pk).first()
        
        if existing:
            self.is_duplicate = True
            self.duplicate_of = existing
            return True
        return False


class InvoiceLineItem(models.Model):
    """Line items extracted from invoice"""
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='line_items')
    sl_no = models.IntegerField(default=1)
    description = models.TextField()
    hsn_code = models.CharField(max_length=8, blank=True)
    quantity = models.DecimalField(max_digits=18, decimal_places=3, default=1)
    unit = models.CharField(max_length=20, blank=True)
    unit_price = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    discount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    taxable_value = models.DecimalField(max_digits=18, decimal_places=2)
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    cgst = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    sgst = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    igst = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=18, decimal_places=2)
    
    # Confidence scores
    confidence_score = models.FloatField(default=0)


class InvoiceCorrection(models.Model):
    """Track manual corrections for learning"""
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='corrections')
    field_name = models.CharField(max_length=50)
    ocr_value = models.TextField()
    corrected_value = models.TextField()
    corrected_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True)
    corrected_at = models.DateTimeField(auto_now_add=True)


# ============================================
# OCR SERVICE
# ============================================
class OCRService:
    """Invoice OCR using Google Vision or AWS Textract"""
    
    def __init__(self, provider='google'):
        self.provider = provider
    
    def extract_text(self, file_content: bytes, file_type: str) -> dict:
        """Extract text from invoice image/PDF"""
        if self.provider == 'google':
            return self._google_vision_extract(file_content, file_type)
        elif self.provider == 'aws':
            return self._aws_textract_extract(file_content, file_type)
        else:
            return self._fallback_extract(file_content, file_type)
    
    def _google_vision_extract(self, file_content: bytes, file_type: str) -> dict:
        """Extract using Google Cloud Vision API"""
        try:
            from google.cloud import vision
            client = vision.ImageAnnotatorClient()
            
            image = vision.Image(content=file_content)
            response = client.document_text_detection(image=image)
            
            if response.error.message:
                raise Exception(response.error.message)
            
            return {
                'raw_text': response.full_text_annotation.text,
                'confidence': response.full_text_annotation.pages[0].confidence if response.full_text_annotation.pages else 0,
                'provider': 'google'
            }
        except Exception as e:
            return {'raw_text': '', 'confidence': 0, 'provider': 'google', 'error': str(e)}
    
    def _aws_textract_extract(self, file_content: bytes, file_type: str) -> dict:
        """Extract using AWS Textract"""
        try:
            import boto3
            client = boto3.client('textract')
            
            response = client.detect_document_text(
                Document={'Bytes': file_content}
            )
            
            text = '\n'.join([
                block['Text'] for block in response['Blocks']
                if block['BlockType'] == 'LINE'
            ])
            
            return {
                'raw_text': text,
                'confidence': 0.9,
                'provider': 'aws'
            }
        except Exception as e:
            return {'raw_text': '', 'confidence': 0, 'provider': 'aws', 'error': str(e)}
    
    def _fallback_extract(self, file_content: bytes, file_type: str) -> dict:
        """Fallback OCR using pytesseract"""
        try:
            import pytesseract
            from PIL import Image
            from io import BytesIO
            
            if file_type == 'pdf':
                from pdf2image import convert_from_bytes
                images = convert_from_bytes(file_content)
                text = '\n'.join([pytesseract.image_to_string(img) for img in images])
            else:
                image = Image.open(BytesIO(file_content))
                text = pytesseract.image_to_string(image)
            
            return {
                'raw_text': text,
                'confidence': 0.7,
                'provider': 'tesseract'
            }
        except Exception as e:
            return {'raw_text': '', 'confidence': 0, 'provider': 'tesseract', 'error': str(e)}


class InvoiceDataExtractor:
    """Extract structured data from OCR text"""
    
    GSTIN_PATTERN = r'[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}'
    DATE_PATTERNS = [
        r'(\d{2}[-/]\d{2}[-/]\d{4})',
        r'(\d{2}[-/]\d{2}[-/]\d{2})',
        r'(\d{4}[-/]\d{2}[-/]\d{2})',
    ]
    AMOUNT_PATTERN = r'[₹]?\s*([\d,]+\.?\d*)'
    
    def extract(self, raw_text: str) -> dict:
        """Extract invoice fields from raw OCR text"""
        data = {
            'vendor_gstin': self._extract_gstin(raw_text),
            'invoice_number': self._extract_invoice_number(raw_text),
            'invoice_date': self._extract_date(raw_text),
            'total_amount': self._extract_total(raw_text),
            'tax_details': self._extract_tax(raw_text),
        }
        return data
    
    def _extract_gstin(self, text: str) -> str:
        match = re.search(self.GSTIN_PATTERN, text)
        return match.group() if match else ''
    
    def _extract_invoice_number(self, text: str) -> str:
        patterns = [
            r'Invoice\s*(?:No\.?|Number|#)\s*[:\-]?\s*([A-Z0-9\-/]+)',
            r'Bill\s*(?:No\.?|Number)\s*[:\-]?\s*([A-Z0-9\-/]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        return ''
    
    def _extract_date(self, text: str) -> str:
        for pattern in self.DATE_PATTERNS:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return ''
    
    def _extract_total(self, text: str) -> Decimal:
        patterns = [
            r'Total\s*[:\-]?\s*[₹]?\s*([\d,]+\.?\d*)',
            r'Grand\s*Total\s*[:\-]?\s*[₹]?\s*([\d,]+\.?\d*)',
            r'Net\s*Amount\s*[:\-]?\s*[₹]?\s*([\d,]+\.?\d*)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return Decimal(match.group(1).replace(',', ''))
                except:
                    pass
        return Decimal('0')
    
    def _extract_tax(self, text: str) -> dict:
        tax = {'cgst': Decimal('0'), 'sgst': Decimal('0'), 'igst': Decimal('0')}
        
        cgst_match = re.search(r'CGST\s*[:\-@]?\s*\d*\.?\d*%?\s*[₹]?\s*([\d,]+\.?\d*)', text, re.IGNORECASE)
        if cgst_match:
            try:
                tax['cgst'] = Decimal(cgst_match.group(1).replace(',', ''))
            except:
                pass
        
        sgst_match = re.search(r'SGST\s*[:\-@]?\s*\d*\.?\d*%?\s*[₹]?\s*([\d,]+\.?\d*)', text, re.IGNORECASE)
        if sgst_match:
            try:
                tax['sgst'] = Decimal(sgst_match.group(1).replace(',', ''))
            except:
                pass
        
        igst_match = re.search(r'IGST\s*[:\-@]?\s*\d*\.?\d*%?\s*[₹]?\s*([\d,]+\.?\d*)', text, re.IGNORECASE)
        if igst_match:
            try:
                tax['igst'] = Decimal(igst_match.group(1).replace(',', ''))
            except:
                pass
        
        return tax


# ============================================
# SERIALIZERS
# ============================================
class InvoiceLineItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceLineItem
        fields = '__all__'


class InvoiceSerializer(serializers.ModelSerializer):
    line_items = InvoiceLineItemSerializer(many=True, read_only=True)
    suggested_ledger_name = serializers.CharField(source='suggested_ledger.name', read_only=True)
    mapped_ledger_name = serializers.CharField(source='mapped_ledger.name', read_only=True)
    
    class Meta:
        model = Invoice
        fields = '__all__'


class InvoiceCorrectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceCorrection
        fields = '__all__'


# ============================================
# VIEWS
# ============================================
class InvoiceUploadView(APIView):
    """Upload and process invoice"""
    parser_classes = [MultiPartParser, FormParser]
    
    @transaction.atomic
    def post(self, request):
        company_id = request.data.get('company')
        uploaded_file = request.FILES.get('file')
        invoice_type = request.data.get('invoice_type', 'purchase')
        
        if not uploaded_file:
            return Response({'error': 'File is required'}, status=400)
        
        # Create invoice record
        invoice = Invoice.objects.create(
            company_id=company_id,
            file=uploaded_file,
            original_filename=uploaded_file.name,
            file_type=uploaded_file.name.split('.')[-1].lower(),
            file_size=uploaded_file.size,
            invoice_type=invoice_type,
            status='processing',
            uploaded_by=request.user
        )
        
        try:
            # OCR extraction
            ocr_service = OCRService(provider='google')
            file_content = uploaded_file.read()
            ocr_result = ocr_service.extract_text(file_content, invoice.file_type)
            
            invoice.ocr_provider = ocr_result.get('provider', '')
            invoice.ocr_confidence = ocr_result.get('confidence', 0)
            invoice.ocr_raw_text = ocr_result.get('raw_text', '')
            
            # Extract structured data
            extractor = InvoiceDataExtractor()
            extracted_data = extractor.extract(invoice.ocr_raw_text)
            invoice.ocr_extracted_data = extracted_data
            
            # Populate fields
            invoice.vendor_gstin = extracted_data.get('vendor_gstin', '')
            invoice.invoice_number = extracted_data.get('invoice_number', '')
            
            if extracted_data.get('invoice_date'):
                try:
                    from datetime import datetime
                    date_str = extracted_data['invoice_date']
                    for fmt in ['%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d']:
                        try:
                            invoice.invoice_date = datetime.strptime(date_str, fmt).date()
                            break
                        except:
                            continue
                except:
                    pass
            
            invoice.total_amount = extracted_data.get('total_amount', Decimal('0'))
            
            tax_details = extracted_data.get('tax_details', {})
            invoice.cgst_amount = tax_details.get('cgst', Decimal('0'))
            invoice.sgst_amount = tax_details.get('sgst', Decimal('0'))
            invoice.igst_amount = tax_details.get('igst', Decimal('0'))
            invoice.total_tax = invoice.cgst_amount + invoice.sgst_amount + invoice.igst_amount
            
            # Check for duplicates
            invoice.check_duplicate()
            
            # Suggest ledger based on vendor history
            if invoice.vendor_gstin:
                from apps.companies.models import Ledger
                vendor_ledger = Ledger.objects.filter(
                    company_id=company_id,
                    gstin=invoice.vendor_gstin
                ).first()
                if vendor_ledger:
                    invoice.suggested_ledger = vendor_ledger
            
            invoice.status = 'extracted'
            invoice.processed_at = timezone.now()
            invoice.save()
            
            return Response({
                'message': 'Invoice processed successfully',
                'invoice': InvoiceSerializer(invoice).data
            }, status=201)
            
        except Exception as e:
            invoice.status = 'failed'
            invoice.error_message = str(e)
            invoice.save()
            return Response({'error': str(e)}, status=400)


class InvoiceListView(generics.ListAPIView):
    serializer_class = InvoiceSerializer
    
    def get_queryset(self):
        queryset = Invoice.objects.all()
        company_id = self.request.query_params.get('company')
        if company_id:
            queryset = queryset.filter(company_id=company_id)
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset


class InvoiceDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = InvoiceSerializer
    queryset = Invoice.objects.all()


class InvoiceApproveView(APIView):
    """Approve extracted invoice data"""
    def post(self, request, pk):
        invoice = Invoice.objects.get(pk=pk)
        
        if invoice.status not in ['extracted', 'validated']:
            return Response({'error': 'Invoice not ready for approval'}, status=400)
        
        # Update with any corrections
        for field in ['vendor_name', 'vendor_gstin', 'invoice_number', 'total_amount']:
            if field in request.data:
                old_value = getattr(invoice, field)
                new_value = request.data[field]
                if str(old_value) != str(new_value):
                    InvoiceCorrection.objects.create(
                        invoice=invoice,
                        field_name=field,
                        ocr_value=str(old_value),
                        corrected_value=str(new_value),
                        corrected_by=request.user
                    )
                setattr(invoice, field, new_value)
        
        # Set mapped ledger
        if 'mapped_ledger_id' in request.data:
            invoice.mapped_ledger_id = request.data['mapped_ledger_id']
        
        invoice.status = 'approved'
        invoice.approved_by = request.user
        invoice.approved_at = timezone.now()
        invoice.save()
        
        return Response({'message': 'Invoice approved', 'invoice': InvoiceSerializer(invoice).data})


class InvoiceCreateVoucherView(APIView):
    """Create voucher from approved invoice"""
    @transaction.atomic
    def post(self, request, pk):
        invoice = Invoice.objects.get(pk=pk)
        
        if invoice.status != 'approved':
            return Response({'error': 'Invoice must be approved first'}, status=400)
        
        if not invoice.mapped_ledger:
            return Response({'error': 'Ledger not mapped'}, status=400)
        
        from apps.vouchers.models import Voucher, VoucherEntry
        
        # Create voucher
        voucher = Voucher.objects.create(
            company=invoice.company,
            voucher_type='purchase' if invoice.invoice_type == 'purchase' else 'sales',
            date=invoice.invoice_date or timezone.now().date(),
            reference=invoice.invoice_number,
            narration=f"Invoice from {invoice.vendor_name}",
            amount=invoice.total_amount,
            party_ledger=invoice.mapped_ledger,
            source='invoice_ocr',
            status='pending_approval',
            created_by=request.user
        )
        
        # Create entries
        # Purchase/Expense Dr
        VoucherEntry.objects.create(
            voucher=voucher,
            ledger=invoice.mapped_ledger,
            amount=invoice.subtotal or invoice.total_amount,
            is_debit=True,
            order=1
        )
        
        # TODO: Add tax ledger entries if GST amounts present
        
        # Party Cr
        # (need to find or create party ledger based on GSTIN)
        
        invoice.voucher = voucher
        invoice.status = 'voucher_created'
        invoice.save()
        
        return Response({
            'message': 'Voucher created',
            'voucher_id': voucher.id
        })


class BulkInvoiceUploadView(APIView):
    """Upload multiple invoices"""
    parser_classes = [MultiPartParser, FormParser]
    
    def post(self, request):
        company_id = request.data.get('company')
        files = request.FILES.getlist('files')
        
        results = []
        for uploaded_file in files:
            invoice = Invoice.objects.create(
                company_id=company_id,
                file=uploaded_file,
                original_filename=uploaded_file.name,
                file_type=uploaded_file.name.split('.')[-1].lower(),
                file_size=uploaded_file.size,
                status='uploaded',
                uploaded_by=request.user
            )
            results.append({'id': invoice.id, 'filename': invoice.original_filename})
        
        # Queue for background processing
        # TODO: Trigger Celery task
        
        return Response({
            'message': f'{len(results)} invoices uploaded',
            'invoices': results
        })
