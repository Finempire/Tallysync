"""Celery Tasks for Payroll Processing"""
from celery import shared_task
from celery.utils.log import get_task_logger
from decimal import Decimal

logger = get_task_logger(__name__)


@shared_task(bind=True, max_retries=2)
def process_monthly_payroll(self, company_id: int, month: int, year: int, user_id: int):
    """Process monthly payroll for all employees"""
    from apps.payroll.models import Employee, PayrollRun, Payslip, StatutoryCalculator
    from apps.companies.models import Company
    from django.db import transaction
    from datetime import date
    import calendar
    
    try:
        company = Company.objects.get(pk=company_id)
        
        # Get or create payroll run
        payroll_run, created = PayrollRun.objects.get_or_create(
            company=company,
            month=month,
            year=year,
            defaults={
                'period_start': date(year, month, 1),
                'period_end': date(year, month, calendar.monthrange(year, month)[1]),
                'processed_by_id': user_id
            }
        )
        
        if not created and payroll_run.status in ['processed', 'approved', 'paid']:
            return {'error': 'Payroll already processed for this period'}
        
        payroll_run.status = 'processing'
        payroll_run.save()
        
        logger.info(f"Processing payroll for {company.name} - {month}/{year}")
        
        employees = Employee.objects.filter(
            company=company,
            is_active=True,
            date_of_joining__lte=payroll_run.period_end
        ).select_related('salary_structure')
        
        calculator = StatutoryCalculator()
        
        total_gross = Decimal('0')
        total_deductions = Decimal('0')
        total_net = Decimal('0')
        total_employer_pf = Decimal('0')
        total_employer_esi = Decimal('0')
        
        with transaction.atomic():
            for employee in employees:
                payslip = _process_employee_payroll(
                    employee, payroll_run, calculator, month
                )
                
                total_gross += payslip.gross_salary
                total_deductions += payslip.total_deductions
                total_net += payslip.net_pay
                total_employer_pf += payslip.employer_pf + payslip.employer_eps + payslip.employer_edli
                total_employer_esi += payslip.employer_esi
            
            payroll_run.total_employees = employees.count()
            payroll_run.total_gross = total_gross
            payroll_run.total_deductions = total_deductions
            payroll_run.total_net_pay = total_net
            payroll_run.total_employer_pf = total_employer_pf
            payroll_run.total_employer_esi = total_employer_esi
            payroll_run.status = 'processed'
            payroll_run.save()
        
        logger.info(f"Payroll processed: {employees.count()} employees, Net: {total_net}")
        return {
            'payroll_run_id': payroll_run.id,
            'employees': employees.count(),
            'total_net': float(total_net)
        }
        
    except Exception as e:
        logger.error(f"Payroll processing failed: {e}")
        if payroll_run:
            payroll_run.status = 'failed'
            payroll_run.save()
        raise self.retry(exc=e)


def _process_employee_payroll(employee, payroll_run, calculator, month):
    """Process payroll for single employee"""
    from apps.payroll.models import Payslip, Attendance
    
    structure = employee.salary_structure
    monthly_ctc = employee.ctc / 12
    
    # Calculate earnings
    basic = monthly_ctc * Decimal(str(structure.basic_percent / 100))
    hra = basic * Decimal(str(structure.hra_percent / 100))
    da = monthly_ctc * Decimal(str(structure.da_percent / 100)) if structure.da_percent else Decimal('0')
    conveyance = Decimal(str(structure.conveyance_allowance or 1600))
    medical = Decimal(str(structure.medical_allowance or 1250))
    special = monthly_ctc - basic - hra - da - conveyance - medical
    
    gross = basic + hra + da + conveyance + medical + special
    
    # Calculate attendance
    attendance_records = Attendance.objects.filter(
        employee=employee,
        date__month=month,
        date__year=payroll_run.year
    )
    worked_days = attendance_records.filter(status__in=['present', 'half_day']).count()
    lop_days = attendance_records.filter(status='absent').count()
    
    # Apply LOP deduction
    if lop_days > 0:
        daily_rate = gross / 30
        lop_deduction = daily_rate * lop_days
        gross -= lop_deduction
    
    # Statutory calculations
    pf_result = calculator.calculate_pf(float(basic + da))
    esi_result = calculator.calculate_esi(float(gross)) if employee.esi_applicable else {'employee': 0, 'employer': 0}
    pt = calculator.calculate_pt(float(gross), employee.company.state, month) if employee.pt_applicable else 0
    
    # TDS calculation (annual projected)
    annual_taxable = float(gross * 12)
    tds_result = calculator.calculate_tds(annual_taxable, employee.tax_regime)
    monthly_tds = Decimal(str(tds_result['monthly_tds']))
    
    # Total deductions
    total_deductions = (
        Decimal(str(pf_result['employee_pf'])) +
        Decimal(str(esi_result['employee'])) +
        Decimal(str(pt)) +
        monthly_tds
    )
    
    net_pay = gross - total_deductions
    
    # Create/update payslip
    payslip, _ = Payslip.objects.update_or_create(
        payroll_run=payroll_run,
        employee=employee,
        defaults={
            'worked_days': worked_days,
            'lop_days': lop_days,
            'basic_salary': basic,
            'hra': hra,
            'da': da,
            'conveyance': conveyance,
            'medical': medical,
            'special_allowance': special,
            'gross_salary': gross,
            'pf_deduction': Decimal(str(pf_result['employee_pf'])),
            'esi_deduction': Decimal(str(esi_result['employee'])),
            'pt_deduction': Decimal(str(pt)),
            'tds_deduction': monthly_tds,
            'total_deductions': total_deductions,
            'employer_pf': Decimal(str(pf_result['employer_epf'])),
            'employer_eps': Decimal(str(pf_result['employer_eps'])),
            'employer_edli': Decimal(str(pf_result['edli'])),
            'employer_esi': Decimal(str(esi_result['employer'])),
            'net_pay': net_pay,
            'ctc_monthly': monthly_ctc
        }
    )
    
    return payslip


@shared_task
def generate_payslip_pdf(payslip_id: int):
    """Generate PDF payslip"""
    from apps.payroll.models import Payslip
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from io import BytesIO
    from django.core.files.base import ContentFile
    
    payslip = Payslip.objects.select_related('employee', 'payroll_run__company').get(pk=payslip_id)
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()
    
    # Header
    elements.append(Paragraph(f"<b>{payslip.payroll_run.company.name}</b>", styles['Heading1']))
    elements.append(Paragraph(f"Salary Slip - {payslip.payroll_run.month}/{payslip.payroll_run.year}", styles['Heading2']))
    elements.append(Spacer(1, 20))
    
    # Employee details
    emp_data = [
        ['Employee Code', payslip.employee.employee_code, 'Department', payslip.employee.department or '-'],
        ['Name', f"{payslip.employee.first_name} {payslip.employee.last_name}", 'Designation', payslip.employee.designation or '-'],
        ['PAN', payslip.employee.pan or '-', 'UAN', payslip.employee.uan or '-'],
    ]
    emp_table = Table(emp_data, colWidths=[100, 150, 100, 150])
    emp_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('BACKGROUND', (2, 0), (2, -1), colors.lightgrey),
    ]))
    elements.append(emp_table)
    elements.append(Spacer(1, 20))
    
    # Earnings and Deductions
    earnings = [
        ['Earnings', 'Amount (₹)', 'Deductions', 'Amount (₹)'],
        ['Basic', f"{payslip.basic_salary:,.2f}", 'PF', f"{payslip.pf_deduction:,.2f}"],
        ['HRA', f"{payslip.hra:,.2f}", 'ESI', f"{payslip.esi_deduction:,.2f}"],
        ['DA', f"{payslip.da:,.2f}", 'PT', f"{payslip.pt_deduction:,.2f}"],
        ['Conveyance', f"{payslip.conveyance:,.2f}", 'TDS', f"{payslip.tds_deduction:,.2f}"],
        ['Medical', f"{payslip.medical:,.2f}", '', ''],
        ['Special Allowance', f"{payslip.special_allowance:,.2f}", '', ''],
        ['', '', '', ''],
        ['Gross Salary', f"{payslip.gross_salary:,.2f}", 'Total Deductions', f"{payslip.total_deductions:,.2f}"],
    ]
    earn_table = Table(earnings, colWidths=[130, 120, 130, 120])
    earn_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
    ]))
    elements.append(earn_table)
    elements.append(Spacer(1, 20))
    
    # Net Pay
    elements.append(Paragraph(f"<b>Net Pay: ₹{payslip.net_pay:,.2f}</b>", styles['Heading2']))
    
    doc.build(elements)
    
    pdf_content = buffer.getvalue()
    buffer.close()
    
    filename = f"payslip_{payslip.employee.employee_code}_{payslip.payroll_run.month}_{payslip.payroll_run.year}.pdf"
    payslip.pdf_file.save(filename, ContentFile(pdf_content))
    
    logger.info(f"Generated payslip PDF for {payslip.employee.employee_code}")
    return {'filename': filename}


@shared_task
def export_payroll_to_tally(payroll_run_id: int):
    """Export payroll to Tally as salary voucher"""
    from apps.payroll.models import PayrollRun, Payslip
    from apps.vouchers.models import Voucher, VoucherEntry
    from django.db import transaction
    
    payroll_run = PayrollRun.objects.select_related('company').get(pk=payroll_run_id)
    payslips = Payslip.objects.filter(payroll_run=payroll_run).select_related('employee')
    
    with transaction.atomic():
        voucher = Voucher.objects.create(
            company=payroll_run.company,
            voucher_type='payroll',
            date=payroll_run.period_end,
            amount=payroll_run.total_net_pay,
            narration=f"Salary for {payroll_run.month}/{payroll_run.year}",
            source='payroll'
        )
        
        # Salary expense entries (Debit)
        for payslip in payslips:
            VoucherEntry.objects.create(
                voucher=voucher,
                ledger_id=payroll_run.company.salary_expense_ledger_id,
                amount=payslip.gross_salary,
                is_debit=True,
                narration=f"{payslip.employee.first_name} {payslip.employee.last_name}"
            )
        
        # Bank/Cash entry (Credit)
        VoucherEntry.objects.create(
            voucher=voucher,
            ledger_id=payroll_run.company.salary_bank_ledger_id,
            amount=payroll_run.total_net_pay,
            is_debit=False
        )
        
        # PF Payable entry
        if payroll_run.total_employer_pf > 0:
            total_pf = sum(p.pf_deduction + p.employer_pf + p.employer_eps for p in payslips)
            VoucherEntry.objects.create(
                voucher=voucher,
                ledger_id=payroll_run.company.pf_payable_ledger_id,
                amount=total_pf,
                is_debit=False
            )
        
        payroll_run.voucher = voucher
        payroll_run.status = 'exported'
        payroll_run.save()
    
    logger.info(f"Exported payroll {payroll_run_id} to Tally voucher {voucher.id}")
    return {'voucher_id': voucher.id}
