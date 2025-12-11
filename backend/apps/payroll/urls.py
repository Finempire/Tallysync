from django.urls import path
from .models import (EmployeeListCreateView, EmployeeDetailView, SalaryStructureListCreateView,
                     PayrollProcessView, PayrollRunListView, PayslipListView, PayslipPDFView, PayrollExportTallyView)

urlpatterns = [
    path('employees/', EmployeeListCreateView.as_view(), name='employee-list'),
    path('employees/<int:pk>/', EmployeeDetailView.as_view(), name='employee-detail'),
    path('salary-structures/', SalaryStructureListCreateView.as_view(), name='salary-structures'),
    path('<int:company_id>/process/', PayrollProcessView.as_view(), name='process'),
    path('runs/', PayrollRunListView.as_view(), name='payroll-runs'),
    path('runs/<int:payroll_id>/payslips/', PayslipListView.as_view(), name='payslips'),
    path('payslips/<int:pk>/pdf/', PayslipPDFView.as_view(), name='payslip-pdf'),
    path('runs/<int:payroll_id>/export-tally/', PayrollExportTallyView.as_view(), name='export-tally'),
]
