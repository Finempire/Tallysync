from django.urls import path
from .models import (DashboardStatsView, TrendDataView, CashFlowForecastView,
                     GenerateReportView, ReportTemplateListView, GeneratedReportListView)

urlpatterns = [
    path('<int:company_id>/dashboard/', DashboardStatsView.as_view(), name='dashboard'),
    path('<int:company_id>/trends/', TrendDataView.as_view(), name='trends'),
    path('<int:company_id>/cash-flow-forecast/', CashFlowForecastView.as_view(), name='cash-flow-forecast'),
    path('<int:company_id>/generate/', GenerateReportView.as_view(), name='generate-report'),
    path('templates/', ReportTemplateListView.as_view(), name='report-templates'),
    path('<int:company_id>/reports/', GeneratedReportListView.as_view(), name='generated-reports'),
]
