"""Celery Tasks for Invoice OCR Processing"""
from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def process_invoice_ocr(self, invoice_id: int):
    """Process invoice with OCR"""
    from apps.invoices.models import Invoice, OCRService, InvoiceDataExtractor, InvoiceLineItem
    
    try:
        invoice = Invoice.objects.get(pk=invoice_id)
        invoice.status = 'processing'
        invoice.save()
        
        logger.info(f"Processing invoice {invoice_id} with OCR")
        
        # Extract text using OCR
        ocr_service = OCRService()
        ocr_result = ocr_service.extract_text(invoice.file.path)
        
        invoice.ocr_raw_text = ocr_result['text']
        invoice.ocr_confidence = ocr_result['confidence']
        invoice.ocr_provider = ocr_result['provider']
        
        # Extract structured data
        extractor = InvoiceDataExtractor()
        extracted_data = extractor.extract(ocr_result['text'])
        
        invoice.vendor_name = extracted_data.get('vendor_name')
        invoice.vendor_gstin = extracted_data.get('gstin')
        invoice.invoice_number = extracted_data.get('invoice_number')
        invoice.invoice_date = extracted_data.get('invoice_date')
        invoice.subtotal = extracted_data.get('subtotal', 0)
        invoice.cgst_amount = extracted_data.get('cgst', 0)
        invoice.sgst_amount = extracted_data.get('sgst', 0)
        invoice.igst_amount = extracted_data.get('igst', 0)
        invoice.total_amount = extracted_data.get('total', 0)
        invoice.ocr_extracted_data = extracted_data
        
        # Extract line items if available
        for item in extracted_data.get('line_items', []):
            InvoiceLineItem.objects.create(
                invoice=invoice,
                description=item.get('description'),
                hsn_code=item.get('hsn'),
                quantity=item.get('quantity', 1),
                unit_price=item.get('unit_price', 0),
                taxable_value=item.get('taxable_value', 0),
                gst_rate=item.get('gst_rate', 18),
                confidence_score=item.get('confidence', 0.5)
            )
        
        # Check for duplicates
        duplicate = Invoice.objects.filter(
            company=invoice.company,
            vendor_gstin=invoice.vendor_gstin,
            invoice_number=invoice.invoice_number
        ).exclude(pk=invoice_id).first()
        
        if duplicate:
            invoice.is_duplicate = True
            invoice.duplicate_of = duplicate
        
        invoice.status = 'extracted'
        invoice.save()
        
        logger.info(f"Invoice {invoice_id} OCR completed successfully")
        return {'status': 'success', 'invoice_id': invoice_id}
        
    except Exception as e:
        logger.error(f"Invoice OCR failed for {invoice_id}: {e}")
        invoice.status = 'failed'
        invoice.error_message = str(e)
        invoice.save()
        raise self.retry(exc=e)


@shared_task
def bulk_process_invoices(invoice_ids: list):
    """Process multiple invoices"""
    for invoice_id in invoice_ids:
        process_invoice_ocr.delay(invoice_id)
    return {'queued': len(invoice_ids)}


@shared_task
def create_voucher_from_invoice(invoice_id: int, user_id: int):
    """Create voucher from approved invoice"""
    from apps.invoices.models import Invoice
    from apps.vouchers.models import Voucher, VoucherEntry
    from django.db import transaction
    
    invoice = Invoice.objects.select_related('company', 'mapped_ledger').get(pk=invoice_id)
    
    if invoice.status != 'approved':
        return {'error': 'Invoice not approved'}
    
    voucher_type = 'purchase' if invoice.invoice_type == 'purchase' else 'journal'
    
    with transaction.atomic():
        voucher = Voucher.objects.create(
            company=invoice.company,
            voucher_type=voucher_type,
            date=invoice.invoice_date,
            amount=invoice.total_amount,
            narration=f"Invoice {invoice.invoice_number} from {invoice.vendor_name}",
            source='invoice_ocr',
            created_by_id=user_id
        )
        
        # Purchase/Expense entry (Debit)
        VoucherEntry.objects.create(
            voucher=voucher,
            ledger=invoice.mapped_ledger,
            amount=invoice.subtotal,
            is_debit=True
        )
        
        # Tax entries if applicable
        if invoice.cgst_amount:
            VoucherEntry.objects.create(
                voucher=voucher,
                ledger_id=invoice.company.cgst_input_ledger_id,
                amount=invoice.cgst_amount,
                is_debit=True
            )
        
        if invoice.sgst_amount:
            VoucherEntry.objects.create(
                voucher=voucher,
                ledger_id=invoice.company.sgst_input_ledger_id,
                amount=invoice.sgst_amount,
                is_debit=True
            )
        
        if invoice.igst_amount:
            VoucherEntry.objects.create(
                voucher=voucher,
                ledger_id=invoice.company.igst_input_ledger_id,
                amount=invoice.igst_amount,
                is_debit=True
            )
        
        # Creditor/Vendor entry (Credit)
        VoucherEntry.objects.create(
            voucher=voucher,
            ledger_id=invoice.vendor_ledger_id or invoice.mapped_ledger_id,
            amount=invoice.total_amount,
            is_debit=False
        )
        
        invoice.voucher = voucher
        invoice.status = 'voucher_created'
        invoice.save()
    
    logger.info(f"Created voucher {voucher.id} from invoice {invoice_id}")
    return {'voucher_id': voucher.id}
