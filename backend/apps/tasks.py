"""
Celery Tasks for All Apps
Background processing for bank statements, OCR, payroll, notifications
"""
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


# ============================================
# BANK STATEMENT TASKS
# ============================================
@shared_task(bind=True, max_retries=3)
def process_bank_statement(self, statement_id: int):
    """Process uploaded bank statement"""
    from apps.bank_statements.models import BankStatement, BankStatementParser, LedgerSuggestionEngine
    
    try:
        statement = BankStatement.objects.get(pk=statement_id)
        statement.status = 'processing'
        statement.save()
        
        # Parse the file
        parser = BankStatementParser(statement.bank_account.bank_format)
        transactions = parser.parse_file(statement.file.path)
        
        # Create parsed transactions with suggestions
        suggestion_engine = LedgerSuggestionEngine(statement.bank_account.company_id)
        
        for txn_data in transactions:
            from apps.bank_statements.models import ParsedTransaction
            txn = ParsedTransaction.objects.create(
                statement=statement,
                date=txn_data['date'],
                description=txn_data['description'],
                debit=txn_data.get('debit', 0),
                credit=txn_data.get('credit', 0),
                balance=txn_data.get('balance', 0),
                reference_number=txn_data.get('reference'),
            )
            
            # Get ledger suggestion
            suggestion = suggestion_engine.suggest_ledger(txn.description)
            if suggestion:
                txn.suggested_ledger_id = suggestion['ledger_id']
                txn.confidence_score = suggestion['confidence']
                txn.save()
        
        statement.status = 'parsed'
        statement.total_transactions = len(transactions)
        statement.save()
        
        logger.info(f"Processed bank statement {statement_id}: {len(transactions)} transactions")
        return {'status': 'success', 'transactions': len(transactions)}
        
    except Exception as e:
        logger.error(f"Error processing bank statement {statement_id}: {e}")
        statement.status = 'failed'
        statement.error_message = str(e)
        statement.save()
        raise self.retry(exc=e, countdown=60)


@shared_task
def generate_vouchers_from_transactions(transaction_ids: list, company_id: int):
    """Generate vouchers from mapped transactions"""
    from apps.bank_statements.models import ParsedTransaction
    from apps.vouchers.models import Voucher, VoucherEntry
    from apps.companies.models import Company
    
    company = Company.objects.get(pk=company_id)
    vouchers_created = 0
    
    for txn_id in transaction_ids:
        txn = ParsedTransaction.objects.get(pk=txn_id)
        if txn.status != 'mapped' or not txn.mapped_ledger:
            continue
        
        # Determine voucher type
        voucher_type = 'payment' if txn.debit > 0 else 'receipt'
        amount = txn.debit if txn.debit > 0 else txn.credit
        
        # Create voucher
        voucher = Voucher.objects.create(
            company=company,
            voucher_type=voucher_type,
            date=txn.date,
            amount=amount,
            narration=txn.description,
            source='bank_statement',
            status='draft'
        )
        
        # Create entries (double-entry)
        bank_ledger = txn.statement.bank_account.ledger
        
        if voucher_type == 'payment':
            VoucherEntry.objects.create(voucher=voucher, ledger=txn.mapped_ledger, amount=amount, is_debit=True)
            VoucherEntry.objects.create(voucher=voucher, ledger=bank_ledger, amount=amount, is_debit=False)
        else:
            VoucherEntry.objects.create(voucher=voucher, ledger=bank_ledger, amount=amount, is_debit=True)
            VoucherEntry.objects.create(voucher=voucher, ledger=txn.mapped_ledger, amount=amount, is_debit=False)
        
        txn.voucher = voucher
        txn.status = 'voucher_created'
        txn.save()
        vouchers_created += 1
    
    return {'vouchers_created': vouchers_created}


# ============================================
# TALLY SYNC TASKS
# ============================================
@shared_task(bind=True, max_retries=3)
def sync_voucher_to_tally(self, voucher_id: int):
    """Sync single voucher to Tally via desktop connector"""
    from apps.vouchers.models import Voucher
    from apps.tally_connector.models import SyncOperation
    
    try:
        voucher = Voucher.objects.get(pk=voucher_id)
        
        # Create sync operation
        operation = SyncOperation.objects.create(
            connector=voucher.company.desktop_connectors.filter(status='active').first(),
            operation_type='create_voucher',
            voucher=voucher,
            status='pending'
        )
        
        voucher.status = 'queued'
        voucher.save()
        
        return {'operation_id': str(operation.id), 'status': 'queued'}
        
    except Exception as e:
        logger.error(f"Error queuing voucher {voucher_id}: {e}")
        raise self.retry(exc=e, countdown=30)


@shared_task
def sync_ledgers_from_tally(company_id: int):
    """Sync ledger master from Tally"""
    from apps.tally_connector.models import SyncOperation, DesktopConnector
    
    connector = DesktopConnector.objects.filter(
        company_id=company_id, status='active'
    ).first()
    
    if not connector:
        return {'error': 'No active connector'}
    
    operation = SyncOperation.objects.create(
        connector=connector,
        operation_type='sync_ledgers',
        status='pending',
        priority=2
    )
    
    return {'operation_id': str(operation.id)}


# ============================================
# INVOICE OCR TASKS
# ============================================
@shared_task(bind=True, max_retries=2)
def process_invoice_ocr(self, invoice_id: int):
    """Process invoice with OCR"""
    from apps.invoices.models import Invoice, OCRService, InvoiceDataExtractor
    
    try:
        invoice = Invoice.objects.get(pk=invoice_id)
        invoice.status = 'processing'
        invoice.save()
        
        # Extract text using OCR
        ocr_service = OCRService()
        ocr_result = ocr_service.extract_text(invoice.file.path)
        
        invoice.ocr_raw_text = ocr_result['text']
        invoice.ocr_provider = ocr_result['provider']
        invoice.ocr_confidence = ocr_result['confidence']
        
        # Extract structured data
        extractor = InvoiceDataExtractor()
        extracted_data = extractor.extract(ocr_result['text'])
        
        invoice.vendor_name = extracted_data.get('vendor_name')
        invoice.vendor_gstin = extracted_data.get('gstin')
        invoice.invoice_number = extracted_data.get('invoice_number')
        invoice.invoice_date = extracted_data.get('invoice_date')
        invoice.subtotal = extracted_data.get('subtotal', 0)
        invoice.total_amount = extracted_data.get('total', 0)
        invoice.cgst_amount = extracted_data.get('cgst', 0)
        invoice.sgst_amount = extracted_data.get('sgst', 0)
        invoice.igst_amount = extracted_data.get('igst', 0)
        invoice.ocr_extracted_data = extracted_data
        invoice.status = 'extracted'
        invoice.save()
        
        # Check for duplicates
        check_duplicate_invoice.delay(invoice_id)
        
        logger.info(f"OCR processed invoice {invoice_id}")
        return {'status': 'success', 'invoice_id': invoice_id}
        
    except Exception as e:
        logger.error(f"OCR error for invoice {invoice_id}: {e}")
        invoice.status = 'failed'
        invoice.error_message = str(e)
        invoice.save()
        raise self.retry(exc=e, countdown=120)


@shared_task
def check_duplicate_invoice(invoice_id: int):
    """Check for duplicate invoices"""
    from apps.invoices.models import Invoice
    
    invoice = Invoice.objects.get(pk=invoice_id)
    
    if not invoice.vendor_gstin or not invoice.invoice_number:
        return {'duplicate': False}
    
    duplicate = Invoice.objects.filter(
        company=invoice.company,
        vendor_gstin=invoice.vendor_gstin,
        invoice_number=invoice.invoice_number,
        status__in=['extracted', 'validated', 'approved', 'voucher_created']
    ).exclude(pk=invoice_id).first()
    
    if duplicate:
        invoice.is_duplicate = True
        invoice.duplicate_of = duplicate
        invoice.save()
        return {'duplicate': True, 'duplicate_of': duplicate.id}
    
    return {'duplicate': False}


# ============================================
# PAYROLL TASKS
# ============================================
@shared_task
def process_monthly_payroll(company_id: int, month: int, year: int):
    """Process monthly payroll for all employees"""
    from apps.payroll.models import PayrollRun, Employee, Payslip, StatutoryCalculator
    from apps.companies.models import Company
    from decimal import Decimal
    from datetime import date
    import calendar
    
    company = Company.objects.get(pk=company_id)
    
    # Create payroll run
    days_in_month = calendar.monthrange(year, month)[1]
    payroll = PayrollRun.objects.create(
        company=company,
        month=month,
        year=year,
        period_start=date(year, month, 1),
        period_end=date(year, month, days_in_month),
        status='processing'
    )
    
    employees = Employee.objects.filter(company=company, is_active=True)
    calculator = StatutoryCalculator()
    
    total_gross = Decimal('0')
    total_deductions = Decimal('0')
    total_net = Decimal('0')
    total_employer_pf = Decimal('0')
    total_employer_esi = Decimal('0')
    
    for emp in employees:
        # Calculate salary components
        monthly_ctc = emp.ctc / 12
        structure = emp.salary_structure
        
        basic = monthly_ctc * Decimal(str(structure.basic_percent / 100))
        hra = basic * Decimal(str(structure.hra_percent / 100))
        da = structure.da_amount
        conveyance = structure.conveyance_amount
        medical = structure.medical_amount
        
        gross = basic + hra + da + conveyance + medical
        special = monthly_ctc - gross - (monthly_ctc * Decimal('0.13'))  # Employer contributions
        gross += max(special, 0)
        
        # Calculate deductions
        pf_calc = calculator.calculate_pf(float(basic), float(da))
        esi_calc = calculator.calculate_esi(float(gross))
        pt_calc = calculator.calculate_pt(float(gross), emp.state or 'MH', month)
        
        annual_income = emp.ctc - Decimal(str(pf_calc['employee_pf'] * 12))
        tds_calc = calculator.calculate_tds(float(annual_income), emp.tax_regime)
        monthly_tds = Decimal(str(tds_calc['monthly_tds']))
        
        total_deductions_emp = (Decimal(str(pf_calc['employee_pf'])) + 
                               Decimal(str(esi_calc['employee_esi'])) + 
                               Decimal(str(pt_calc)) + monthly_tds)
        
        net_pay = gross - total_deductions_emp
        
        # Create payslip
        Payslip.objects.create(
            payroll_run=payroll,
            employee=emp,
            worked_days=days_in_month,
            basic=basic,
            hra=hra,
            da=da,
            conveyance=conveyance,
            medical=medical,
            special_allowance=max(special, 0),
            gross_earnings=gross,
            pf_deduction=Decimal(str(pf_calc['employee_pf'])),
            esi_deduction=Decimal(str(esi_calc['employee_esi'])),
            pt_deduction=Decimal(str(pt_calc)),
            tds_deduction=monthly_tds,
            total_deductions=total_deductions_emp,
            employer_pf=Decimal(str(pf_calc['employer_epf'])),
            employer_eps=Decimal(str(pf_calc['employer_eps'])),
            employer_edli=Decimal(str(pf_calc['edli'])),
            employer_esi=Decimal(str(esi_calc['employer_esi'])),
            net_pay=net_pay,
            ctc_monthly=monthly_ctc
        )
        
        total_gross += gross
        total_deductions += total_deductions_emp
        total_net += net_pay
        total_employer_pf += Decimal(str(pf_calc['employer_epf'] + pf_calc['employer_eps']))
        total_employer_esi += Decimal(str(esi_calc['employer_esi']))
    
    # Update payroll run
    payroll.total_employees = employees.count()
    payroll.total_gross = total_gross
    payroll.total_deductions = total_deductions
    payroll.total_net_pay = total_net
    payroll.total_employer_pf = total_employer_pf
    payroll.total_employer_esi = total_employer_esi
    payroll.status = 'processed'
    payroll.save()
    
    return {'payroll_id': payroll.id, 'employees': employees.count()}


@shared_task
def generate_pf_ecr(payroll_id: int):
    """Generate PF ECR file for EPFO portal"""
    from apps.payroll.models import PayrollRun, Payslip
    import csv
    import io
    
    payroll = PayrollRun.objects.get(pk=payroll_id)
    payslips = Payslip.objects.filter(payroll_run=payroll)
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # ECR format headers
    writer.writerow(['UAN', 'Member Name', 'Gross Wages', 'EPF Wages', 'EPS Wages', 
                     'EDLI Wages', 'EPF Contribution (EE)', 'EPS Contribution (ER)', 
                     'EPF Contribution (ER)', 'NCP Days', 'Refund of Advances'])
    
    for slip in payslips:
        emp = slip.employee
        writer.writerow([
            emp.uan or '',
            f"{emp.first_name} {emp.last_name}",
            int(slip.gross_earnings),
            int(min(slip.basic + slip.da, 15000)),
            int(min(slip.basic + slip.da, 15000)),
            int(min(slip.basic + slip.da, 15000)),
            int(slip.pf_deduction),
            int(slip.employer_eps),
            int(slip.employer_pf),
            slip.lop_days or 0,
            0
        ])
    
    return output.getvalue()


# ============================================
# GST TASKS
# ============================================
@shared_task
def generate_einvoice(invoice_id: int):
    """Generate e-invoice via GSP"""
    from apps.gst.models import EInvoice
    
    invoice = EInvoice.objects.get(pk=invoice_id)
    
    # Generate IRP JSON
    irp_json = invoice.generate_irp_json()
    
    # TODO: Call actual GSP API
    # For now, simulate success
    invoice.status = 'generated'
    invoice.irn = f"INV{invoice.id:012d}"
    invoice.ack_number = f"ACK{invoice.id:010d}"
    invoice.ack_date = timezone.now()
    invoice.save()
    
    return {'irn': invoice.irn}


@shared_task
def reconcile_gstr2b(company_id: int, period: str):
    """Reconcile GSTR-2B with purchase register"""
    from apps.gst.models import GSTR2BRecord, ReconciliationResult
    from apps.vouchers.models import Voucher
    
    gstr2b_records = GSTR2BRecord.objects.filter(company_id=company_id, period=period)
    
    for record in gstr2b_records:
        # Find matching purchase voucher
        match = Voucher.objects.filter(
            company_id=company_id,
            voucher_type='purchase',
            party_gstin=record.supplier_gstin,
        ).first()
        
        if match:
            # Check for exact match
            if (match.party_invoice_number == record.invoice_no and 
                abs(match.amount - record.taxable_value) < 1):
                match_type = 'exact'
            else:
                match_type = 'mismatch'
        else:
            match_type = 'missing_pr'
        
        ReconciliationResult.objects.update_or_create(
            gstr2b_record=record,
            defaults={
                'purchase_voucher': match,
                'match_type': match_type
            }
        )
    
    return {'records_processed': gstr2b_records.count()}


# ============================================
# NOTIFICATION TASKS
# ============================================
@shared_task
def send_notification(user_id: int, event: str, data: dict = None):
    """Send notification to user"""
    from apps.notifications.models import NotificationService
    from apps.users.models import User
    
    user = User.objects.get(pk=user_id)
    notification = NotificationService.notify_user(user, event, data)
    
    return {'notification_id': notification.id if notification else None}


@shared_task
def send_compliance_reminders():
    """Send daily compliance reminders"""
    from apps.notifications.models import ComplianceReminderService
    
    ComplianceReminderService.send_due_reminders(days_before=3)
    ComplianceReminderService.send_due_reminders(days_before=1)
    
    return {'status': 'sent'}


@shared_task
def generate_weekly_summary(tenant_id: int):
    """Generate and send weekly summary to admins"""
    from apps.users.models import User
    from apps.vouchers.models import Voucher
    from apps.bank_statements.models import BankStatement
    
    # Gather stats
    week_ago = timezone.now() - timedelta(days=7)
    
    vouchers_created = Voucher.objects.filter(created_at__gte=week_ago).count()
    vouchers_synced = Voucher.objects.filter(sync_completed_at__gte=week_ago).count()
    statements_processed = BankStatement.objects.filter(upload_date__gte=week_ago).count()
    
    summary_data = {
        'vouchers_created': vouchers_created,
        'vouchers_synced': vouchers_synced,
        'statements_processed': statements_processed,
        'period': f"{week_ago.date()} to {timezone.now().date()}"
    }
    
    # Send to admins
    admins = User.objects.filter(role='admin', is_active=True)
    for admin in admins:
        send_notification.delay(admin.id, 'weekly_summary', summary_data)
    
    return summary_data


# ============================================
# SCHEDULED TASKS (Celery Beat)
# ============================================
@shared_task
def daily_maintenance():
    """Daily maintenance tasks"""
    # Clean up old sync operations
    from apps.tally_connector.models import SyncOperation
    
    old_ops = SyncOperation.objects.filter(
        created_at__lt=timezone.now() - timedelta(days=30),
        status__in=['completed', 'failed']
    )
    count = old_ops.count()
    old_ops.delete()
    
    return {'cleaned_operations': count}


@shared_task
def check_connector_health():
    """Check health of all desktop connectors"""
    from apps.tally_connector.models import DesktopConnector
    
    threshold = timezone.now() - timedelta(minutes=5)
    
    disconnected = DesktopConnector.objects.filter(
        status='active',
        last_heartbeat__lt=threshold
    ).update(status='disconnected')
    
    if disconnected > 0:
        # TODO: Send alert notifications
        pass
    
    return {'disconnected_connectors': disconnected}
