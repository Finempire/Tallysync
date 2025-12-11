"""
Sales Import Workflow - Multi-step import for Sales Vouchers
Implements Suvit-style workflow: Upload → Map → GST Config → Process → Push to Tally
"""
from django.db import models
from django.utils import timezone


class SalesImport(models.Model):
    """Tracks a sales import session through all workflow steps"""
    
    IMPORT_TYPES = [
        ('with_item', 'With Item (Item Invoice)'),
        ('without_item', 'Without Item (Accounting Invoice)')
    ]
    
    STATUS_CHOICES = [
        ('uploaded', 'File Uploaded'),
        ('columns_detected', 'Columns Detected'),
        ('field_mapped', 'Fields Mapped'),
        ('gst_configured', 'GST Configured'),
        ('ledger_mapped', 'Ledgers Mapped'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed')
    ]
    
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='sales_imports')
    import_type = models.CharField(max_length=20, choices=IMPORT_TYPES, default='without_item')
    voucher_type = models.CharField(max_length=20, default='sales')  # sales, purchase, etc.
    
    # File storage
    original_file = models.FileField(upload_to='sales_imports/')
    original_filename = models.CharField(max_length=255)
    
    # Parsed data from Excel/CSV
    detected_columns = models.JSONField(default=list, blank=True)  # List of column names found
    sample_data = models.JSONField(default=list, blank=True)  # First 5 rows for preview
    total_rows = models.IntegerField(default=0)
    
    # User configurations at each step
    column_mapping = models.JSONField(default=dict, blank=True)  # {excel_col: tally_field}
    gst_config = models.JSONField(default=dict, blank=True)  # GST calculation settings
    ledger_mapping = models.JSONField(default=dict, blank=True)  # Extra charges mapping
    
    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='uploaded')
    error_message = models.TextField(blank=True)
    
    # Stats
    valid_rows = models.IntegerField(default=0)
    warning_rows = models.IntegerField(default=0)
    error_rows = models.IntegerField(default=0)
    processed_rows = models.IntegerField(default=0)
    synced_rows = models.IntegerField(default=0)
    
    created_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Import #{self.id} - {self.original_filename} ({self.get_status_display()})"


class SalesImportRow(models.Model):
    """Individual row in an import with validation status"""
    
    VALIDATION_STATUS = [
        ('pending', 'Pending Validation'),
        ('valid', 'Valid'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('processed', 'Processed'),
        ('synced', 'Synced to Tally')
    ]
    
    sales_import = models.ForeignKey(SalesImport, on_delete=models.CASCADE, related_name='rows')
    row_number = models.IntegerField()
    
    # Original data from Excel
    raw_data = models.JSONField(default=dict)
    
    # Mapped data after field mapping applied
    mapped_data = models.JSONField(default=dict, blank=True)
    
    # Resolved references
    party_ledger = models.ForeignKey('companies.Ledger', on_delete=models.SET_NULL, null=True, blank=True, related_name='import_rows_as_party')
    sales_ledger = models.ForeignKey('companies.Ledger', on_delete=models.SET_NULL, null=True, blank=True, related_name='import_rows_as_sales')
    
    # For item-based imports
    stock_items_data = models.JSONField(default=list, blank=True)  # List of {item_id, qty, rate, amount}
    
    # Validation
    validation_status = models.CharField(max_length=20, choices=VALIDATION_STATUS, default='pending')
    validation_errors = models.JSONField(default=list, blank=True)  # List of error messages
    validation_warnings = models.JSONField(default=list, blank=True)  # List of warning messages
    
    # Created voucher reference
    voucher = models.ForeignKey('vouchers.Voucher', on_delete=models.SET_NULL, null=True, blank=True, related_name='import_rows')
    
    # Timestamps
    validated_at = models.DateTimeField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['row_number']
        unique_together = ['sales_import', 'row_number']
    
    def __str__(self):
        return f"Row {self.row_number} - {self.get_validation_status_display()}"
    
    def validate_row(self):
        """Validate this row and update status"""
        errors = []
        warnings = []
        
        mapped = self.mapped_data
        
        # Required field checks
        if not mapped.get('date'):
            errors.append('Invoice date is required')
        if not mapped.get('party_name'):
            errors.append('Party name is required')
        if not mapped.get('amount') and not mapped.get('total_amount'):
            errors.append('Amount is required')
        
        # Party ledger check
        if not self.party_ledger:
            if mapped.get('party_name'):
                warnings.append(f"Party '{mapped.get('party_name')}' not found in Tally. Create or map manually.")
        
        # Item-based checks
        if self.sales_import.import_type == 'with_item':
            if not mapped.get('item_name') and not self.stock_items_data:
                errors.append('Item name is required for Item Invoice')
            if not mapped.get('quantity'):
                warnings.append('Quantity not specified')
        
        self.validation_errors = errors
        self.validation_warnings = warnings
        
        if errors:
            self.validation_status = 'error'
        elif warnings:
            self.validation_status = 'warning'
        else:
            self.validation_status = 'valid'
        
        self.validated_at = timezone.now()
        self.save()
        
        return self.validation_status
