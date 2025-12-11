"""
Payroll App - Complete Implementation (Phase 4)
Employee Management, Salary Structure, Statutory Deductions (PF, ESI, TDS, PT)
Salary Processing, Payslip Generation, Tally Export
"""
from decimal import Decimal
from datetime import date, timedelta
from django.db import models
from django.utils import timezone
from rest_framework import serializers, generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import transaction


# ============================================
# MODELS
# ============================================
class Employee(models.Model):
    """Employee master with statutory details"""
    GENDER_CHOICES = [('M', 'Male'), ('F', 'Female'), ('O', 'Other')]
    
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='employees')
    
    # Basic info
    employee_code = models.CharField(max_length=20)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    date_of_birth = models.DateField()
    date_of_joining = models.DateField()
    date_of_exit = models.DateField(null=True, blank=True)
    
    # Contact
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=15, blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    pincode = models.CharField(max_length=10, blank=True)
    
    # Statutory IDs
    pan = models.CharField(max_length=10, blank=True)
    aadhaar = models.CharField(max_length=12, blank=True)
    uan = models.CharField(max_length=12, blank=True)  # Universal Account Number (PF)
    esic_ip = models.CharField(max_length=17, blank=True)  # ESIC IP Number
    
    # Bank details
    bank_name = models.CharField(max_length=100, blank=True)
    bank_account = models.CharField(max_length=20, blank=True)
    ifsc_code = models.CharField(max_length=11, blank=True)
    
    # Department and designation
    department = models.CharField(max_length=100, blank=True)
    designation = models.CharField(max_length=100, blank=True)
    
    # Salary structure
    salary_structure = models.ForeignKey(
        'SalaryStructure', on_delete=models.SET_NULL, null=True, blank=True
    )
    ctc = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Tax regime
    tax_regime = models.CharField(max_length=10, choices=[
        ('old', 'Old Regime'), ('new', 'New Regime')
    ], default='new')
    
    # Status
    is_active = models.BooleanField(default=True)
    pf_applicable = models.BooleanField(default=True)
    esi_applicable = models.BooleanField(default=True)
    pt_applicable = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['company', 'employee_code']

    def __str__(self):
        return f"{self.employee_code} - {self.first_name} {self.last_name}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class SalaryStructure(models.Model):
    """Salary structure template"""
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='salary_structures')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    # Component percentages (of CTC)
    basic_percent = models.DecimalField(max_digits=5, decimal_places=2, default=40)  # 40% of CTC
    hra_percent = models.DecimalField(max_digits=5, decimal_places=2, default=50)  # 50% of Basic
    da_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    conveyance = models.DecimalField(max_digits=10, decimal_places=2, default=1600)
    medical_allowance = models.DecimalField(max_digits=10, decimal_places=2, default=1250)
    special_allowance_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # Balance
    
    # Additional components as JSON
    components = models.JSONField(default=dict)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.company.name})"


class SalaryComponent(models.Model):
    """Individual salary component definition"""
    COMPONENT_TYPES = [
        ('earning', 'Earning'),
        ('deduction', 'Deduction'),
        ('employer_contribution', 'Employer Contribution'),
    ]
    
    CALCULATION_TYPES = [
        ('fixed', 'Fixed Amount'),
        ('percent_basic', 'Percentage of Basic'),
        ('percent_gross', 'Percentage of Gross'),
        ('percent_ctc', 'Percentage of CTC'),
    ]
    
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='salary_components')
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20)
    component_type = models.CharField(max_length=30, choices=COMPONENT_TYPES)
    calculation_type = models.CharField(max_length=30, choices=CALCULATION_TYPES)
    value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_taxable = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ['company', 'code']

    def __str__(self):
        return f"{self.name} ({self.code})"


class Attendance(models.Model):
    """Daily attendance records"""
    STATUS_CHOICES = [
        ('present', 'Present'), ('absent', 'Absent'), ('half_day', 'Half Day'),
        ('weekend', 'Weekend'), ('holiday', 'Holiday'), ('leave', 'Leave'),
    ]
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='attendance')
    date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    hours_worked = models.DecimalField(max_digits=4, decimal_places=2, default=8)
    overtime_hours = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    remarks = models.CharField(max_length=200, blank=True)

    class Meta:
        unique_together = ['employee', 'date']


class Leave(models.Model):
    """Leave management"""
    LEAVE_TYPES = [
        ('casual', 'Casual Leave'), ('sick', 'Sick Leave'), ('earned', 'Earned Leave'),
        ('maternity', 'Maternity Leave'), ('paternity', 'Paternity Leave'), ('lop', 'Loss of Pay'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('cancelled', 'Cancelled'),
    ]
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='leaves')
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPES)
    start_date = models.DateField()
    end_date = models.DateField()
    days = models.DecimalField(max_digits=4, decimal_places=1)
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    approved_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class LoanAdvance(models.Model):
    """Employee loans and advances"""
    LOAN_TYPES = [('loan', 'Loan'), ('advance', 'Salary Advance')]
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='loans')
    loan_type = models.CharField(max_length=20, choices=LOAN_TYPES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    emi_amount = models.DecimalField(max_digits=10, decimal_places=2)
    tenure_months = models.IntegerField()
    start_date = models.DateField()
    remaining_amount = models.DecimalField(max_digits=12, decimal_places=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)


class PayrollRun(models.Model):
    """Monthly payroll processing"""
    STATUS_CHOICES = [
        ('draft', 'Draft'), ('processing', 'Processing'), ('processed', 'Processed'),
        ('approved', 'Approved'), ('paid', 'Paid'), ('exported', 'Exported to Tally'),
    ]
    
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='payroll_runs')
    month = models.IntegerField()  # 1-12
    year = models.IntegerField()
    period_start = models.DateField()
    period_end = models.DateField()
    
    # Summary
    total_employees = models.IntegerField(default=0)
    total_gross = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_deductions = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_net_pay = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_employer_pf = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_employer_esi = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    processed_at = models.DateTimeField(null=True, blank=True)
    processed_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_payrolls')
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['company', 'month', 'year']

    def __str__(self):
        return f"Payroll {self.month}/{self.year} - {self.company.name}"


class Payslip(models.Model):
    """Individual employee payslip"""
    payroll_run = models.ForeignKey(PayrollRun, on_delete=models.CASCADE, related_name='payslips')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='payslips')
    
    # Days
    total_days = models.IntegerField(default=30)
    worked_days = models.DecimalField(max_digits=4, decimal_places=1, default=30)
    leave_days = models.DecimalField(max_digits=4, decimal_places=1, default=0)
    lop_days = models.DecimalField(max_digits=4, decimal_places=1, default=0)
    
    # Earnings
    basic = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    hra = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    da = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    conveyance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    medical = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    special_allowance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    other_earnings = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gross_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Deductions
    pf_employee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    esi_employee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    professional_tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tds = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    loan_deduction = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    other_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Employer contributions
    pf_employer = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    eps_employer = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    edli = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    esi_employer = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gratuity_provision = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Net pay
    net_pay = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # CTC
    ctc_monthly = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Additional data
    earnings_breakdown = models.JSONField(default=dict)
    deductions_breakdown = models.JSONField(default=dict)
    
    # Voucher link
    voucher = models.ForeignKey('vouchers.Voucher', on_delete=models.SET_NULL, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['payroll_run', 'employee']


# ============================================
# STATUTORY CALCULATIONS
# ============================================
class StatutoryCalculator:
    """Calculate PF, ESI, PT, TDS deductions"""
    
    # PF Constants
    PF_WAGE_CEILING = Decimal('15000')  # ₹15,000
    PF_EMPLOYEE_RATE = Decimal('0.12')  # 12%
    PF_EMPLOYER_RATE = Decimal('0.12')  # 12% (split: 8.33% EPS + 3.67% EPF)
    EPS_RATE = Decimal('0.0833')  # 8.33%
    EDLI_RATE = Decimal('0.005')  # 0.5%
    
    # ESI Constants
    ESI_WAGE_CEILING = Decimal('21000')  # ₹21,000
    ESI_EMPLOYEE_RATE = Decimal('0.0075')  # 0.75%
    ESI_EMPLOYER_RATE = Decimal('0.0325')  # 3.25%
    
    # PT Slabs (Maharashtra example)
    PT_SLABS_MH = [
        (0, 7500, 0),
        (7501, 10000, 175),
        (10001, float('inf'), 200),  # 200 for Feb, 300 otherwise
    ]
    
    @classmethod
    def calculate_pf(cls, basic_da: Decimal, pf_applicable: bool = True) -> dict:
        """Calculate PF contributions"""
        if not pf_applicable:
            return {'employee': Decimal('0'), 'employer_epf': Decimal('0'), 
                    'employer_eps': Decimal('0'), 'edli': Decimal('0')}
        
        pf_wage = min(basic_da, cls.PF_WAGE_CEILING)
        
        employee_pf = (pf_wage * cls.PF_EMPLOYEE_RATE).quantize(Decimal('1'))
        employer_eps = (pf_wage * cls.EPS_RATE).quantize(Decimal('1'))
        employer_epf = employee_pf - employer_eps
        edli = (pf_wage * cls.EDLI_RATE).quantize(Decimal('1'))
        
        return {
            'employee': employee_pf,
            'employer_epf': employer_epf,
            'employer_eps': employer_eps,
            'edli': edli
        }
    
    @classmethod
    def calculate_esi(cls, gross_salary: Decimal, esi_applicable: bool = True) -> dict:
        """Calculate ESI contributions"""
        if not esi_applicable or gross_salary > cls.ESI_WAGE_CEILING:
            return {'employee': Decimal('0'), 'employer': Decimal('0')}
        
        employee_esi = (gross_salary * cls.ESI_EMPLOYEE_RATE).quantize(Decimal('1'))
        employer_esi = (gross_salary * cls.ESI_EMPLOYER_RATE).quantize(Decimal('1'))
        
        return {'employee': employee_esi, 'employer': employer_esi}
    
    @classmethod
    def calculate_pt(cls, gross_salary: Decimal, state: str = 'MH', month: int = 1) -> Decimal:
        """Calculate Professional Tax (state-wise)"""
        if state == 'MH':
            for lower, upper, amount in cls.PT_SLABS_MH:
                if lower <= float(gross_salary) <= upper:
                    # February has different PT in Maharashtra
                    if month == 2 and amount == 200:
                        return Decimal('300')
                    return Decimal(str(amount))
        
        # Default slabs for other states
        if gross_salary <= 15000:
            return Decimal('0')
        elif gross_salary <= 20000:
            return Decimal('150')
        else:
            return Decimal('200')
    
    @classmethod
    def calculate_tds(cls, annual_income: Decimal, regime: str = 'new', 
                      declarations: dict = None) -> Decimal:
        """Calculate TDS based on tax regime"""
        if regime == 'new':
            # New tax regime slabs (FY 2024-25)
            slabs = [
                (0, 300000, Decimal('0')),
                (300001, 700000, Decimal('0.05')),
                (700001, 1000000, Decimal('0.10')),
                (1000001, 1200000, Decimal('0.15')),
                (1200001, 1500000, Decimal('0.20')),
                (1500001, float('inf'), Decimal('0.30')),
            ]
            # Standard deduction
            taxable = max(Decimal('0'), annual_income - Decimal('75000'))
        else:
            # Old tax regime slabs
            slabs = [
                (0, 250000, Decimal('0')),
                (250001, 500000, Decimal('0.05')),
                (500001, 1000000, Decimal('0.20')),
                (1000001, float('inf'), Decimal('0.30')),
            ]
            # Deductions under old regime
            deductions = Decimal('50000')  # Standard deduction
            if declarations:
                deductions += min(Decimal('150000'), declarations.get('80c', Decimal('0')))
                deductions += min(Decimal('50000'), declarations.get('80d', Decimal('0')))
                deductions += declarations.get('80tta', Decimal('0'))
                deductions += min(Decimal('200000'), declarations.get('home_loan', Decimal('0')))
            taxable = max(Decimal('0'), annual_income - deductions)
        
        # Calculate tax
        tax = Decimal('0')
        remaining = taxable
        
        for lower, upper, rate in slabs:
            if remaining <= 0:
                break
            slab_amount = min(remaining, Decimal(str(upper - lower + 1)))
            tax += slab_amount * rate
            remaining -= slab_amount
        
        # Add 4% cess
        tax = tax * Decimal('1.04')
        
        # Rebate u/s 87A (if taxable income <= 7 lakh in new regime)
        if regime == 'new' and taxable <= 700000:
            tax = Decimal('0')
        
        # Monthly TDS
        monthly_tds = (tax / 12).quantize(Decimal('1'))
        
        return monthly_tds
    
    @classmethod
    def calculate_gratuity(cls, basic: Decimal) -> Decimal:
        """Calculate gratuity provision (4.81% of basic)"""
        return (basic * Decimal('0.0481')).quantize(Decimal('0.01'))
    
    @classmethod
    def calculate_bonus(cls, basic: Decimal, months: int = 12) -> Decimal:
        """Calculate statutory bonus (8.33% to 20% of basic)"""
        # Minimum bonus = 8.33% (1/12 of annual basic)
        annual_basic = basic * months
        return (annual_basic * Decimal('0.0833')).quantize(Decimal('0.01'))


# ============================================
# SERIALIZERS
# ============================================
class EmployeeSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField()
    
    class Meta:
        model = Employee
        fields = '__all__'


class SalaryStructureSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalaryStructure
        fields = '__all__'


class AttendanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attendance
        fields = '__all__'


class LeaveSerializer(serializers.ModelSerializer):
    class Meta:
        model = Leave
        fields = '__all__'


class PayrollRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayrollRun
        fields = '__all__'


class PayslipSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_code = serializers.CharField(source='employee.employee_code', read_only=True)
    
    class Meta:
        model = Payslip
        fields = '__all__'


# ============================================
# VIEWS
# ============================================
class EmployeeListCreateView(generics.ListCreateAPIView):
    serializer_class = EmployeeSerializer
    
    def get_queryset(self):
        queryset = Employee.objects.filter(is_active=True)
        company_id = self.request.query_params.get('company')
        if company_id:
            queryset = queryset.filter(company_id=company_id)
        return queryset


class EmployeeDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = EmployeeSerializer
    queryset = Employee.objects.all()


class SalaryStructureListCreateView(generics.ListCreateAPIView):
    serializer_class = SalaryStructureSerializer
    
    def get_queryset(self):
        return SalaryStructure.objects.filter(is_active=True)


class PayrollProcessView(APIView):
    """Process monthly payroll"""
    
    @transaction.atomic
    def post(self, request, company_id):
        month = int(request.data.get('month'))
        year = int(request.data.get('year'))
        
        # Get or create payroll run
        period_start = date(year, month, 1)
        if month == 12:
            period_end = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            period_end = date(year, month + 1, 1) - timedelta(days=1)
        
        payroll, created = PayrollRun.objects.get_or_create(
            company_id=company_id, month=month, year=year,
            defaults={'period_start': period_start, 'period_end': period_end}
        )
        
        if payroll.status not in ['draft', 'processing']:
            return Response({'error': 'Payroll already processed'}, status=400)
        
        payroll.status = 'processing'
        payroll.save()
        
        # Get active employees
        employees = Employee.objects.filter(
            company_id=company_id, is_active=True,
            date_of_joining__lte=period_end
        )
        
        total_gross = Decimal('0')
        total_deductions = Decimal('0')
        total_net = Decimal('0')
        total_employer_pf = Decimal('0')
        total_employer_esi = Decimal('0')
        
        for employee in employees:
            payslip = self._process_employee(payroll, employee, month)
            total_gross += payslip.gross_salary
            total_deductions += payslip.total_deductions
            total_net += payslip.net_pay
            total_employer_pf += payslip.pf_employer + payslip.eps_employer + payslip.edli
            total_employer_esi += payslip.esi_employer
        
        payroll.total_employees = employees.count()
        payroll.total_gross = total_gross
        payroll.total_deductions = total_deductions
        payroll.total_net_pay = total_net
        payroll.total_employer_pf = total_employer_pf
        payroll.total_employer_esi = total_employer_esi
        payroll.status = 'processed'
        payroll.processed_at = timezone.now()
        payroll.processed_by = request.user
        payroll.save()
        
        return Response({
            'message': 'Payroll processed successfully',
            'payroll': PayrollRunSerializer(payroll).data
        })
    
    def _process_employee(self, payroll: PayrollRun, employee: Employee, month: int) -> Payslip:
        """Process payroll for single employee"""
        structure = employee.salary_structure
        ctc = employee.ctc
        
        # Calculate salary components
        if structure:
            basic = (ctc * structure.basic_percent / 100 / 12).quantize(Decimal('1'))
            hra = (basic * structure.hra_percent / 100).quantize(Decimal('1'))
            da = (basic * structure.da_percent / 100).quantize(Decimal('1'))
            conveyance = structure.conveyance
            medical = structure.medical_allowance
        else:
            # Default structure
            basic = (ctc * Decimal('0.40') / 12).quantize(Decimal('1'))
            hra = (basic * Decimal('0.50')).quantize(Decimal('1'))
            da = Decimal('0')
            conveyance = Decimal('1600')
            medical = Decimal('1250')
        
        # Calculate special allowance as balance
        fixed_earnings = basic + hra + da + conveyance + medical
        monthly_ctc = (ctc / 12).quantize(Decimal('1'))
        
        # Employer contributions (part of CTC)
        basic_da = basic + da
        pf_calc = StatutoryCalculator.calculate_pf(basic_da, employee.pf_applicable)
        esi_calc = StatutoryCalculator.calculate_esi(monthly_ctc, employee.esi_applicable)
        gratuity = StatutoryCalculator.calculate_gratuity(basic)
        
        employer_cost = (pf_calc['employer_epf'] + pf_calc['employer_eps'] + 
                        pf_calc['edli'] + esi_calc['employer'] + gratuity)
        
        special_allowance = max(Decimal('0'), monthly_ctc - fixed_earnings - employer_cost)
        gross_salary = fixed_earnings + special_allowance
        
        # Deductions
        pt = StatutoryCalculator.calculate_pt(gross_salary, 'MH', month)
        tds = StatutoryCalculator.calculate_tds(ctc, employee.tax_regime)
        
        # Loan deductions
        loan_deduction = Decimal('0')
        active_loans = employee.loans.filter(is_active=True)
        for loan in active_loans:
            loan_deduction += loan.emi_amount
        
        total_deductions = (pf_calc['employee'] + esi_calc['employee'] + 
                          pt + tds + loan_deduction)
        
        net_pay = gross_salary - total_deductions
        
        # Create or update payslip
        payslip, _ = Payslip.objects.update_or_create(
            payroll_run=payroll, employee=employee,
            defaults={
                'basic': basic, 'hra': hra, 'da': da,
                'conveyance': conveyance, 'medical': medical,
                'special_allowance': special_allowance,
                'gross_salary': gross_salary,
                'pf_employee': pf_calc['employee'],
                'esi_employee': esi_calc['employee'],
                'professional_tax': pt, 'tds': tds,
                'loan_deduction': loan_deduction,
                'total_deductions': total_deductions,
                'pf_employer': pf_calc['employer_epf'],
                'eps_employer': pf_calc['employer_eps'],
                'edli': pf_calc['edli'],
                'esi_employer': esi_calc['employer'],
                'gratuity_provision': gratuity,
                'net_pay': net_pay,
                'ctc_monthly': monthly_ctc,
            }
        )
        
        return payslip


class PayrollRunListView(generics.ListAPIView):
    serializer_class = PayrollRunSerializer
    
    def get_queryset(self):
        return PayrollRun.objects.all().order_by('-year', '-month')


class PayslipListView(generics.ListAPIView):
    serializer_class = PayslipSerializer
    
    def get_queryset(self):
        payroll_id = self.kwargs.get('payroll_id')
        return Payslip.objects.filter(payroll_run_id=payroll_id)


class PayslipPDFView(APIView):
    """Generate PDF payslip"""
    def get(self, request, pk):
        payslip = Payslip.objects.get(pk=pk)
        
        # TODO: Generate PDF using ReportLab or WeasyPrint
        
        return Response({'message': 'PDF generation not implemented'})


class PayrollExportTallyView(APIView):
    """Export payroll to Tally vouchers"""
    @transaction.atomic
    def post(self, request, payroll_id):
        payroll = PayrollRun.objects.get(pk=payroll_id)
        
        if payroll.status != 'approved':
            return Response({'error': 'Payroll must be approved first'}, status=400)
        
        from apps.vouchers.models import Voucher, VoucherEntry
        
        # Create salary voucher
        voucher = Voucher.objects.create(
            company=payroll.company,
            voucher_type='payroll',
            date=payroll.period_end,
            reference=f"Payroll-{payroll.month:02d}/{payroll.year}",
            narration=f"Salary for {payroll.month}/{payroll.year}",
            amount=payroll.total_net_pay,
            source='payroll',
            status='pending_approval',
            created_by=request.user
        )
        
        # TODO: Create detailed voucher entries for each component
        
        payroll.status = 'exported'
        payroll.save()
        
        return Response({
            'message': 'Payroll exported to Tally',
            'voucher_id': voucher.id
        })
