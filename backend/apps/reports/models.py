"""
Reports App - Complete Implementation (Phase 5)
Advanced Analytics, Cash Flow Forecasting, Custom Reports
"""
from decimal import Decimal
from datetime import date, timedelta
from django.db import models
from django.db.models import Sum, Count, Avg, F, Q
from django.utils import timezone
from rest_framework import serializers, generics
from rest_framework.views import APIView
from rest_framework.response import Response


# ============================================
# MODELS
# ============================================
class ReportTemplate(models.Model):
    """Custom report templates"""
    REPORT_TYPES = [
        ('financial', 'Financial Report'),
        ('gst', 'GST Report'),
        ('payroll', 'Payroll Report'),
        ('bank', 'Bank Reconciliation'),
        ('custom', 'Custom Report'),
    ]
    
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='report_templates')
    name = models.CharField(max_length=100)
    report_type = models.CharField(max_length=20, choices=REPORT_TYPES)
    description = models.TextField(blank=True)
    config = models.JSONField(default=dict)
    sql_query = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class GeneratedReport(models.Model):
    """Generated report instances"""
    template = models.ForeignKey(ReportTemplate, on_delete=models.CASCADE, null=True, blank=True)
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    report_type = models.CharField(max_length=50)
    parameters = models.JSONField(default=dict)
    data = models.JSONField(default=dict)
    file = models.FileField(upload_to='reports/%Y/%m/', blank=True)
    format = models.CharField(max_length=10, default='json')
    generated_at = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True)


class DashboardWidget(models.Model):
    """Dashboard widgets configuration"""
    WIDGET_TYPES = [
        ('stat_card', 'Statistic Card'),
        ('line_chart', 'Line Chart'),
        ('bar_chart', 'Bar Chart'),
        ('pie_chart', 'Pie Chart'),
        ('table', 'Data Table'),
        ('gauge', 'Gauge'),
    ]
    
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='widgets')
    name = models.CharField(max_length=100)
    widget_type = models.CharField(max_length=20, choices=WIDGET_TYPES)
    data_source = models.CharField(max_length=50)
    config = models.JSONField(default=dict)
    position = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)


class CashFlowForecast(models.Model):
    """Cash flow forecasting data"""
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE)
    forecast_date = models.DateField()
    expected_inflow = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    expected_outflow = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    actual_inflow = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    actual_outflow = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    opening_balance = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    closing_balance = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['company', 'forecast_date']


# ============================================
# REPORT GENERATORS
# ============================================
class ReportGenerator:
    """Base report generator"""
    
    def __init__(self, company_id: int):
        self.company_id = company_id
    
    def generate(self, start_date: date, end_date: date, **kwargs) -> dict:
        raise NotImplementedError


class TrialBalanceReport(ReportGenerator):
    """Generate Trial Balance"""
    
    def generate(self, start_date: date, end_date: date, **kwargs) -> dict:
        from apps.vouchers.models import VoucherEntry
        from apps.companies.models import Ledger
        
        ledgers = Ledger.objects.filter(company_id=self.company_id, is_active=True)
        
        data = []
        total_debit = Decimal('0')
        total_credit = Decimal('0')
        
        for ledger in ledgers:
            entries = VoucherEntry.objects.filter(
                ledger=ledger,
                voucher__date__gte=start_date,
                voucher__date__lte=end_date,
                voucher__status='synced'
            )
            
            debit = entries.filter(is_debit=True).aggregate(total=Sum('amount'))['total'] or Decimal('0')
            credit = entries.filter(is_debit=False).aggregate(total=Sum('amount'))['total'] or Decimal('0')
            
            opening = ledger.opening_balance if ledger.is_debit else -ledger.opening_balance
            closing = opening + debit - credit
            
            if debit or credit or ledger.opening_balance:
                data.append({
                    'ledger_name': ledger.name,
                    'group': ledger.ledger_group,
                    'opening_balance': float(opening),
                    'debit': float(debit),
                    'credit': float(credit),
                    'closing_balance': float(closing)
                })
                total_debit += debit
                total_credit += credit
        
        return {
            'report_type': 'trial_balance',
            'period': {'start': str(start_date), 'end': str(end_date)},
            'data': data,
            'totals': {'debit': float(total_debit), 'credit': float(total_credit)}
        }


class ProfitLossReport(ReportGenerator):
    """Generate Profit & Loss Statement"""
    
    def generate(self, start_date: date, end_date: date, **kwargs) -> dict:
        from apps.vouchers.models import VoucherEntry
        
        income_groups = ['direct_income', 'indirect_income']
        expense_groups = ['direct_expenses', 'indirect_expenses']
        
        income = VoucherEntry.objects.filter(
            voucher__company_id=self.company_id,
            voucher__date__gte=start_date,
            voucher__date__lte=end_date,
            voucher__status='synced',
            ledger__ledger_group__in=income_groups,
            is_debit=False
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        expenses = VoucherEntry.objects.filter(
            voucher__company_id=self.company_id,
            voucher__date__gte=start_date,
            voucher__date__lte=end_date,
            voucher__status='synced',
            ledger__ledger_group__in=expense_groups,
            is_debit=True
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        return {
            'report_type': 'profit_loss',
            'period': {'start': str(start_date), 'end': str(end_date)},
            'income': float(income),
            'expenses': float(expenses),
            'net_profit': float(income - expenses)
        }


class GSTSummaryReport(ReportGenerator):
    """Generate GST Summary"""
    
    def generate(self, start_date: date, end_date: date, **kwargs) -> dict:
        from apps.gst.models import EInvoice
        
        invoices = EInvoice.objects.filter(
            company_id=self.company_id,
            doc_date__gte=start_date,
            doc_date__lte=end_date,
            status='generated'
        )
        
        return {
            'report_type': 'gst_summary',
            'period': {'start': str(start_date), 'end': str(end_date)},
            'total_invoices': invoices.count(),
            'total_taxable': float(invoices.aggregate(t=Sum('taxable_value'))['t'] or 0),
            'total_cgst': float(invoices.aggregate(t=Sum('cgst_amount'))['t'] or 0),
            'total_sgst': float(invoices.aggregate(t=Sum('sgst_amount'))['t'] or 0),
            'total_igst': float(invoices.aggregate(t=Sum('igst_amount'))['t'] or 0),
        }


class PayrollSummaryReport(ReportGenerator):
    """Generate Payroll Summary"""
    
    def generate(self, start_date: date, end_date: date, **kwargs) -> dict:
        from apps.payroll.models import PayrollRun, Payslip
        
        payrolls = PayrollRun.objects.filter(
            company_id=self.company_id,
            period_start__gte=start_date,
            period_end__lte=end_date
        )
        
        summary = payrolls.aggregate(
            total_gross=Sum('total_gross'),
            total_deductions=Sum('total_deductions'),
            total_net=Sum('total_net_pay'),
            total_pf=Sum('total_employer_pf'),
            total_esi=Sum('total_employer_esi')
        )
        
        return {
            'report_type': 'payroll_summary',
            'period': {'start': str(start_date), 'end': str(end_date)},
            'total_employees': payrolls.aggregate(t=Sum('total_employees'))['t'] or 0,
            'total_gross': float(summary['total_gross'] or 0),
            'total_deductions': float(summary['total_deductions'] or 0),
            'total_net_pay': float(summary['total_net'] or 0),
            'employer_pf': float(summary['total_pf'] or 0),
            'employer_esi': float(summary['total_esi'] or 0)
        }


class CashFlowReport(ReportGenerator):
    """Generate Cash Flow Statement"""
    
    def generate(self, start_date: date, end_date: date, **kwargs) -> dict:
        from apps.vouchers.models import Voucher
        
        # Receipts
        receipts = Voucher.objects.filter(
            company_id=self.company_id,
            voucher_type='receipt',
            date__gte=start_date,
            date__lte=end_date,
            status='synced'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        # Payments
        payments = Voucher.objects.filter(
            company_id=self.company_id,
            voucher_type='payment',
            date__gte=start_date,
            date__lte=end_date,
            status='synced'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        return {
            'report_type': 'cash_flow',
            'period': {'start': str(start_date), 'end': str(end_date)},
            'total_inflows': float(receipts),
            'total_outflows': float(payments),
            'net_cash_flow': float(receipts - payments)
        }


# ============================================
# ANALYTICS ENGINE
# ============================================
class AnalyticsEngine:
    """Advanced analytics and insights"""
    
    def __init__(self, company_id: int):
        self.company_id = company_id
    
    def get_dashboard_stats(self) -> dict:
        from apps.vouchers.models import Voucher
        from apps.bank_statements.models import BankStatement, ParsedTransaction
        from apps.invoices.models import Invoice
        
        today = timezone.now().date()
        month_start = today.replace(day=1)
        
        return {
            'vouchers': {
                'total': Voucher.objects.filter(company_id=self.company_id).count(),
                'pending': Voucher.objects.filter(company_id=self.company_id, status='pending_approval').count(),
                'synced_today': Voucher.objects.filter(company_id=self.company_id, sync_completed_at__date=today).count(),
            },
            'bank_statements': {
                'total': BankStatement.objects.filter(bank_account__company_id=self.company_id).count(),
                'pending_mapping': ParsedTransaction.objects.filter(
                    statement__bank_account__company_id=self.company_id,
                    status='pending'
                ).count(),
            },
            'invoices': {
                'total': Invoice.objects.filter(company_id=self.company_id).count(),
                'pending_approval': Invoice.objects.filter(company_id=self.company_id, status='extracted').count(),
            }
        }
    
    def get_trend_data(self, days: int = 30) -> dict:
        from apps.vouchers.models import Voucher
        
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        vouchers = Voucher.objects.filter(
            company_id=self.company_id,
            date__gte=start_date,
            date__lte=end_date
        ).values('date').annotate(
            count=Count('id'),
            total=Sum('amount')
        ).order_by('date')
        
        return {
            'period': {'start': str(start_date), 'end': str(end_date)},
            'daily_data': list(vouchers)
        }
    
    def forecast_cash_flow(self, days: int = 30) -> list:
        """Simple cash flow forecasting based on historical patterns"""
        from apps.vouchers.models import Voucher
        
        # Get historical averages
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=90)
        
        avg_daily_receipts = Voucher.objects.filter(
            company_id=self.company_id,
            voucher_type='receipt',
            date__gte=start_date,
            date__lte=end_date
        ).aggregate(avg=Avg('amount'))['avg'] or Decimal('0')
        
        avg_daily_payments = Voucher.objects.filter(
            company_id=self.company_id,
            voucher_type='payment',
            date__gte=start_date,
            date__lte=end_date
        ).aggregate(avg=Avg('amount'))['avg'] or Decimal('0')
        
        forecast = []
        current_balance = Decimal('0')  # TODO: Get actual opening balance
        
        for i in range(days):
            forecast_date = end_date + timedelta(days=i+1)
            inflow = avg_daily_receipts
            outflow = avg_daily_payments
            current_balance = current_balance + inflow - outflow
            
            forecast.append({
                'date': str(forecast_date),
                'expected_inflow': float(inflow),
                'expected_outflow': float(outflow),
                'projected_balance': float(current_balance)
            })
        
        return forecast


# ============================================
# SERIALIZERS
# ============================================
class ReportTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportTemplate
        fields = '__all__'


class GeneratedReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeneratedReport
        fields = '__all__'


class DashboardWidgetSerializer(serializers.ModelSerializer):
    class Meta:
        model = DashboardWidget
        fields = '__all__'


# ============================================
# VIEWS
# ============================================
class DashboardStatsView(APIView):
    """Get dashboard statistics"""
    def get(self, request, company_id):
        engine = AnalyticsEngine(company_id)
        return Response(engine.get_dashboard_stats())


class TrendDataView(APIView):
    """Get trend data for charts"""
    def get(self, request, company_id):
        days = int(request.query_params.get('days', 30))
        engine = AnalyticsEngine(company_id)
        return Response(engine.get_trend_data(days))


class CashFlowForecastView(APIView):
    """Get cash flow forecast"""
    def get(self, request, company_id):
        days = int(request.query_params.get('days', 30))
        engine = AnalyticsEngine(company_id)
        return Response({'forecast': engine.forecast_cash_flow(days)})


class GenerateReportView(APIView):
    """Generate various reports"""
    def post(self, request, company_id):
        report_type = request.data.get('report_type')
        start_date = date.fromisoformat(request.data.get('start_date'))
        end_date = date.fromisoformat(request.data.get('end_date'))
        
        generators = {
            'trial_balance': TrialBalanceReport,
            'profit_loss': ProfitLossReport,
            'gst_summary': GSTSummaryReport,
            'payroll_summary': PayrollSummaryReport,
            'cash_flow': CashFlowReport,
        }
        
        generator_class = generators.get(report_type)
        if not generator_class:
            return Response({'error': 'Invalid report type'}, status=400)
        
        generator = generator_class(company_id)
        data = generator.generate(start_date, end_date)
        
        # Save generated report
        report = GeneratedReport.objects.create(
            company_id=company_id,
            name=f"{report_type}_{start_date}_{end_date}",
            report_type=report_type,
            parameters={'start_date': str(start_date), 'end_date': str(end_date)},
            data=data,
            generated_by=request.user
        )
        
        return Response(GeneratedReportSerializer(report).data)


class ReportTemplateListView(generics.ListCreateAPIView):
    serializer_class = ReportTemplateSerializer
    
    def get_queryset(self):
        return ReportTemplate.objects.filter(is_active=True)


class GeneratedReportListView(generics.ListAPIView):
    serializer_class = GeneratedReportSerializer
    
    def get_queryset(self):
        company_id = self.kwargs.get('company_id')
        return GeneratedReport.objects.filter(company_id=company_id).order_by('-generated_at')
