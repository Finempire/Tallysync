"""
Companies App - Complete Implementation
Company, Ledger, LedgerMappingRule Models with Serializers and Views
"""
from django.db import models
from django.core.validators import RegexValidator
from rest_framework import serializers, generics, status
from rest_framework.views import APIView
from rest_framework.response import Response


# ============================================
# VALIDATORS
# ============================================
gstin_validator = RegexValidator(
    regex=r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$',
    message='Enter a valid GSTIN'
)

pan_validator = RegexValidator(
    regex=r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$',
    message='Enter a valid PAN'
)


# ============================================
# MODELS
# ============================================
class Company(models.Model):
    name = models.CharField(max_length=200)
    gstin = models.CharField(max_length=15, validators=[gstin_validator], null=True, blank=True)
    pan = models.CharField(max_length=10, validators=[pan_validator], null=True, blank=True)
    address_line1 = models.CharField(max_length=200, blank=True)
    address_line2 = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    state_code = models.CharField(max_length=2, blank=True)
    pincode = models.CharField(max_length=10, blank=True)
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=15, blank=True)
    tally_config = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    tally_connected = models.BooleanField(default=False)
    last_tally_sync = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name_plural = 'Companies'

    def __str__(self):
        return self.name


class Ledger(models.Model):
    LEDGER_GROUPS = [
        ('bank_accounts', 'Bank Accounts'),
        ('cash_in_hand', 'Cash-in-Hand'),
        ('sundry_debtors', 'Sundry Debtors'),
        ('sundry_creditors', 'Sundry Creditors'),
        ('duties_taxes', 'Duties & Taxes'),
        ('direct_expenses', 'Direct Expenses'),
        ('indirect_expenses', 'Indirect Expenses'),
        ('direct_income', 'Direct Income'),
        ('indirect_income', 'Indirect Income'),
        ('fixed_assets', 'Fixed Assets'),
        ('capital_account', 'Capital Account'),
        ('other', 'Other'),
    ]
    
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='ledgers')
    name = models.CharField(max_length=200)
    tally_guid = models.CharField(max_length=100, blank=True)
    parent_group = models.CharField(max_length=200, blank=True)
    ledger_group = models.CharField(max_length=50, choices=LEDGER_GROUPS, default='other')
    gstin = models.CharField(max_length=15, blank=True, null=True)
    gst_registration_type = models.CharField(max_length=50, blank=True)
    bank_name = models.CharField(max_length=100, blank=True)
    account_number = models.CharField(max_length=50, blank=True)
    ifsc_code = models.CharField(max_length=15, blank=True)
    opening_balance = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    is_debit = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    synced_from_tally = models.BooleanField(default=False)
    last_synced = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['company', 'name']

    def __str__(self):
        return f"{self.name} ({self.company.name})"


class LedgerMappingRule(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='mapping_rules')
    pattern = models.CharField(max_length=200)
    pattern_type = models.CharField(max_length=20, choices=[
        ('contains', 'Contains'), ('starts_with', 'Starts With'),
        ('ends_with', 'Ends With'), ('exact', 'Exact Match'), ('regex', 'Regex')
    ], default='contains')
    ledger = models.ForeignKey(Ledger, on_delete=models.CASCADE)
    transaction_type = models.CharField(max_length=10, choices=[
        ('debit', 'Debit'), ('credit', 'Credit'), ('both', 'Both')
    ], default='both')
    priority = models.IntegerField(default=0)
    times_used = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.pattern} → {self.ledger.name}"


class StockItem(models.Model):
    """Stock items for Item Invoice vouchers (With Item type)"""
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='stock_items')
    name = models.CharField(max_length=200)
    tally_guid = models.CharField(max_length=100, blank=True)
    stock_group = models.CharField(max_length=200, blank=True)
    unit = models.CharField(max_length=50, default='Nos')
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    hsn_code = models.CharField(max_length=20, blank=True)
    opening_qty = models.DecimalField(max_digits=18, decimal_places=3, default=0)
    opening_value = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    synced_from_tally = models.BooleanField(default=False)
    last_synced = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['company', 'name']

    def __str__(self):
        return f"{self.name} ({self.company.name})"


# ============================================
# SERIALIZERS
# ============================================
class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'tally_connected', 'last_tally_sync']


class LedgerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ledger
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'synced_from_tally', 'last_synced']


class LedgerMappingRuleSerializer(serializers.ModelSerializer):
    ledger_name = serializers.CharField(source='ledger.name', read_only=True)
    
    class Meta:
        model = LedgerMappingRule
        fields = '__all__'
        read_only_fields = ['id', 'times_used', 'created_at']


# ============================================
# VIEWS
# ============================================
class CompanyListCreateView(generics.ListCreateAPIView):
    serializer_class = CompanySerializer
    
    def get_queryset(self):
        return Company.objects.filter(is_active=True)
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class CompanyDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CompanySerializer
    queryset = Company.objects.all()


class LedgerListCreateView(generics.ListCreateAPIView):
    serializer_class = LedgerSerializer
    
    def get_queryset(self):
        company_id = self.kwargs.get('company_id')
        return Ledger.objects.filter(company_id=company_id, is_active=True)


class LedgerDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = LedgerSerializer
    queryset = Ledger.objects.all()


class MappingRuleListCreateView(generics.ListCreateAPIView):
    serializer_class = LedgerMappingRuleSerializer
    
    def get_queryset(self):
        company_id = self.kwargs.get('company_id')
        return LedgerMappingRule.objects.filter(company_id=company_id, is_active=True)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
