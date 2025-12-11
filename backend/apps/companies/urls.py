from django.urls import path
from .models import CompanyListCreateView, CompanyDetailView, LedgerListCreateView, LedgerDetailView, MappingRuleListCreateView

urlpatterns = [
    path('', CompanyListCreateView.as_view(), name='company-list'),
    path('<int:pk>/', CompanyDetailView.as_view(), name='company-detail'),
    path('<int:company_id>/ledgers/', LedgerListCreateView.as_view(), name='ledger-list'),
    path('ledgers/<int:pk>/', LedgerDetailView.as_view(), name='ledger-detail'),
    path('<int:company_id>/mapping-rules/', MappingRuleListCreateView.as_view(), name='mapping-rules'),
]
