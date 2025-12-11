"""
Vouchers App - Complete Implementation
Models, Serializers, Views for Voucher Management & Tally Sync
"""
from django.db import models
from django.utils import timezone
from rest_framework import serializers, generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import transaction


# ============================================
# MODELS
# ============================================

class VoucherSettings(models.Model):
    TRANSACTION_TYPES = [
        ('sales', 'Sales'), ('purchase', 'Purchase'), ('journal', 'Journal'),
        ('payment', 'Payment'), ('receipt', 'Receipt'), ('contra', 'Contra')
    ]

    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='voucher_settings')
    transaction_type = models.CharField(max_length=50, choices=TRANSACTION_TYPES)
    
    # Default Ledgers (Store IDs to link to Ledger model, but keep as ForeignKey)
    default_sales_ledger = models.ForeignKey('companies.Ledger', on_delete=models.SET_NULL, null=True, blank=True, related_name='defaults_as_sales')
    default_purchase_ledger = models.ForeignKey('companies.Ledger', on_delete=models.SET_NULL, null=True, blank=True, related_name='defaults_as_purchase')
    
    # Tax Ledgers
    default_cgst_ledger = models.ForeignKey('companies.Ledger', on_delete=models.SET_NULL, null=True, blank=True, related_name='defaults_as_cgst')
    default_sgst_ledger = models.ForeignKey('companies.Ledger', on_delete=models.SET_NULL, null=True, blank=True, related_name='defaults_as_sgst')
    default_igst_ledger = models.ForeignKey('companies.Ledger', on_delete=models.SET_NULL, null=True, blank=True, related_name='defaults_as_igst')
    default_cess_ledger = models.ForeignKey('companies.Ledger', on_delete=models.SET_NULL, null=True, blank=True, related_name='defaults_as_cess')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['company', 'transaction_type']


class Voucher(models.Model):
    VOUCHER_TYPES = [
        ('payment', 'Payment'), ('receipt', 'Receipt'), ('journal', 'Journal'),
        ('contra', 'Contra'), ('sales', 'Sales'), ('purchase', 'Purchase'),
        ('credit_note', 'Credit Note'), ('debit_note', 'Debit Note'), ('payroll', 'Payroll'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Draft'), ('pending_approval', 'Pending Approval'), ('approved', 'Approved'),
        ('queued', 'Queued'), ('syncing', 'Syncing'), ('synced', 'Synced'), ('failed', 'Failed'), ('cancelled', 'Cancelled'),
    ]

    VERIFICATION_STATUS_CHOICES = [
        ('unverified', 'Unverified'), ('verified', 'Verified'), ('error', 'Error')
    ]
    
    SOURCE_CHOICES = [
        ('bank_statement', 'Bank Statement'), ('invoice_ocr', 'Invoice OCR'),
        ('manual', 'Manual'), ('import', 'Import'), ('api', 'API'), ('payroll', 'Payroll'),
    ]
    
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='vouchers')
    voucher_type = models.CharField(max_length=20, choices=VOUCHER_TYPES)
    invoice_type = models.CharField(max_length=20, choices=[
        ('accounting', 'Accounting Invoice'),
        ('item', 'Item Invoice')
    ], default='accounting')
    voucher_number = models.CharField(max_length=50, blank=True)
    date = models.DateField()
    reference = models.CharField(max_length=100, blank=True)
    narration = models.TextField(blank=True)
    
    party_name = models.CharField(max_length=255, blank=True, help_text="Raw party name from import")
    party_ledger = models.ForeignKey('companies.Ledger', on_delete=models.SET_NULL, null=True, blank=True, related_name='party_vouchers')
    
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    
    # GST Details
    gst_details = models.JSONField(default=dict, blank=True, help_text="Stores cgst, sgst, igst, cess amounts")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    verification_status = models.CharField(max_length=20, choices=VERIFICATION_STATUS_CHOICES, default='unverified')
    
    tally_master_id = models.CharField(max_length=100, blank=True)
    tally_guid = models.CharField(max_length=100, blank=True)
    sync_attempted_at = models.DateTimeField(null=True, blank=True)
    sync_completed_at = models.DateTimeField(null=True, blank=True)
    sync_error = models.TextField(blank=True)
    sync_attempts = models.IntegerField(default=0)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='manual')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True)
    approved_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_vouchers')
    approved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.get_voucher_type_display()} - {self.voucher_number or 'Draft'} - ₹{self.amount}"

    def generate_tally_xml(self):
        from apps.tally_connector.xml_builder import VoucherXMLBuilder
        builder = VoucherXMLBuilder(self)
        return builder.build()


class VoucherEntry(models.Model):
    voucher = models.ForeignKey(Voucher, on_delete=models.CASCADE, related_name='entries')
    ledger = models.ForeignKey('companies.Ledger', on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    is_debit = models.BooleanField(default=True)
    bill_number = models.CharField(max_length=50, blank=True)
    bill_type = models.CharField(max_length=20, blank=True)
    cost_center = models.CharField(max_length=100, blank=True)
    order = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.ledger.name} - ₹{self.amount} {'Dr' if self.is_debit else 'Cr'}"


class VoucherSyncLog(models.Model):
    voucher = models.ForeignKey(Voucher, on_delete=models.CASCADE, related_name='sync_logs')
    action = models.CharField(max_length=20, choices=[('create', 'Create'), ('update', 'Update'), ('delete', 'Delete')])
    status = models.CharField(max_length=20, choices=[('started', 'Started'), ('success', 'Success'), ('failed', 'Failed')])
    request_xml = models.TextField(blank=True)
    response_xml = models.TextField(blank=True)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.IntegerField(null=True, blank=True)
    connector_id = models.CharField(max_length=100, blank=True)


class VoucherItem(models.Model):
    """Line items for Item Invoice vouchers (With Item type)"""
    voucher = models.ForeignKey(Voucher, on_delete=models.CASCADE, related_name='items')
    stock_item = models.ForeignKey('companies.StockItem', on_delete=models.PROTECT, null=True, blank=True)
    item_name = models.CharField(max_length=200)  # Fallback if stock_item not linked
    quantity = models.DecimalField(max_digits=18, decimal_places=3, default=0)
    rate = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    hsn_code = models.CharField(max_length=20, blank=True)
    order = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['order']
    
    def __str__(self):
        return f"{self.item_name} x {self.quantity} @ ₹{self.rate}"


# View and Serializer classes moved to views.py and serializers.py
