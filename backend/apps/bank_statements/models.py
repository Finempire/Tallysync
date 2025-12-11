"""
Bank Statements App - Complete Implementation (Phase 1 MVP)
Models, Parser, Serializers, Views for Bank Statement Processing
"""
import re
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import pandas as pd
from io import BytesIO

from django.db import models
from django.core.validators import FileExtensionValidator
from django.utils import timezone
from rest_framework import serializers, generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.db import transaction


# ============================================
# MODELS
# ============================================
class BankAccount(models.Model):
    BANK_FORMATS = [
        ('auto', 'Auto Detect'), ('sbi', 'SBI'), ('hdfc', 'HDFC Bank'),
        ('icici', 'ICICI Bank'), ('axis', 'Axis Bank'), ('kotak', 'Kotak Mahindra'),
        ('pnb', 'Punjab National Bank'), ('bob', 'Bank of Baroda'),
        ('canara', 'Canara Bank'), ('union', 'Union Bank'), ('idbi', 'IDBI Bank'),
        ('yes', 'Yes Bank'), ('indusind', 'IndusInd Bank'), ('federal', 'Federal Bank'),
        ('rbl', 'RBL Bank'), ('generic', 'Generic Format'),
    ]
    
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='bank_accounts')
    bank_name = models.CharField(max_length=100)
    account_number = models.CharField(max_length=50)
    ifsc_code = models.CharField(max_length=15, blank=True)
    account_type = models.CharField(max_length=20, choices=[
        ('current', 'Current'), ('savings', 'Savings'), ('cc', 'Cash Credit'), ('od', 'Overdraft')
    ], default='current')
    tally_ledger = models.ForeignKey('companies.Ledger', on_delete=models.SET_NULL, null=True, blank=True)
    statement_format = models.CharField(max_length=50, choices=BANK_FORMATS, default='auto')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['company', 'account_number']

    def __str__(self):
        return f"{self.bank_name} - {self.account_number}"


class BankStatement(models.Model):
    STATUS_CHOICES = [
        ('uploaded', 'Uploaded'), ('processing', 'Processing'), ('parsed', 'Parsed'),
        ('mapped', 'Mapped'), ('approved', 'Approved'), ('synced', 'Synced'), ('failed', 'Failed'),
    ]
    
    bank_account = models.ForeignKey(BankAccount, on_delete=models.CASCADE, related_name='statements')
    file = models.FileField(upload_to='bank_statements/%Y/%m/', 
                           validators=[FileExtensionValidator(['pdf', 'xlsx', 'xls', 'csv'])])
    original_filename = models.CharField(max_length=255)
    file_type = models.CharField(max_length=10)
    file_size = models.IntegerField()
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='uploaded')
    processing_started = models.DateTimeField(null=True, blank=True)
    processing_completed = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    total_transactions = models.IntegerField(default=0)
    mapped_transactions = models.IntegerField(default=0)
    approved_transactions = models.IntegerField(default=0)
    synced_transactions = models.IntegerField(default=0)
    opening_balance = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    closing_balance = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True)
    approved_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_statements')
    approved_at = models.DateTimeField(null=True, blank=True)

    def get_mapping_progress(self):
        if self.total_transactions == 0:
            return 0
        return round((self.mapped_transactions / self.total_transactions) * 100, 1)


class ParsedTransaction(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'), ('auto_mapped', 'Auto Mapped'), ('manually_mapped', 'Manually Mapped'),
        ('approved', 'Approved'), ('voucher_created', 'Voucher Created'), ('synced', 'Synced'), ('skipped', 'Skipped'),
    ]
    
    statement = models.ForeignKey(BankStatement, on_delete=models.CASCADE, related_name='transactions')
    date = models.DateField()
    value_date = models.DateField(null=True, blank=True)
    description = models.TextField()
    reference_number = models.CharField(max_length=100, blank=True)
    debit = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    credit = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    balance = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    transaction_type = models.CharField(max_length=20, choices=[('debit', 'Debit'), ('credit', 'Credit')])
    cheque_number = models.CharField(max_length=20, blank=True)
    suggested_ledger = models.ForeignKey('companies.Ledger', on_delete=models.SET_NULL, null=True, blank=True, related_name='suggested_transactions')
    confidence_score = models.FloatField(default=0)
    mapped_ledger = models.ForeignKey('companies.Ledger', on_delete=models.SET_NULL, null=True, blank=True, related_name='mapped_transactions')
    voucher = models.ForeignKey('vouchers.Voucher', on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    mapped_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True)
    mapped_at = models.DateTimeField(null=True, blank=True)
    row_number = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def amount(self):
        return self.debit or self.credit or 0

    def save(self, *args, **kwargs):
        if self.debit and self.debit > 0:
            self.transaction_type = 'debit'
        elif self.credit and self.credit > 0:
            self.transaction_type = 'credit'
        super().save(*args, **kwargs)


# ============================================
# PARSER
# ============================================
@dataclass
class ParsedTxn:
    date: datetime
    description: str
    debit: Optional[Decimal]
    credit: Optional[Decimal]
    balance: Optional[Decimal]
    reference: str = ''
    value_date: Optional[datetime] = None
    cheque_number: str = ''
    row_number: int = 0


class BankStatementParser:
    BANK_FORMATS = {
        'hdfc': {
            'date_col': ['Date', 'Txn Date', 'Transaction Date'],
            'description_col': ['Narration', 'Description', 'Particulars'],
            'debit_col': ['Withdrawal Amt', 'Debit', 'Withdrawal'],
            'credit_col': ['Deposit Amt', 'Credit', 'Deposit'],
            'balance_col': ['Closing Balance', 'Balance'],
            'date_format': ['%d/%m/%y', '%d/%m/%Y', '%d-%m-%Y'],
        },
        'icici': {
            'date_col': ['Transaction Date', 'Date', 'VALUE DATE'],
            'description_col': ['Transaction Remarks', 'Particulars', 'Description'],
            'debit_col': ['Withdrawal Amount (INR)', 'Debit', 'Dr Amount'],
            'credit_col': ['Deposit Amount (INR)', 'Credit', 'Cr Amount'],
            'balance_col': ['Balance (INR)', 'Balance'],
            'date_format': ['%d-%m-%Y', '%d/%m/%Y'],
        },
        'sbi': {
            'date_col': ['Txn Date', 'Date', 'Transaction Date'],
            'description_col': ['Description', 'Narration', 'Particulars'],
            'debit_col': ['Debit', 'Withdrawal'],
            'credit_col': ['Credit', 'Deposit'],
            'balance_col': ['Balance'],
            'date_format': ['%d %b %Y', '%d-%m-%Y', '%d/%m/%Y'],
        },
        'generic': {
            'date_col': ['Date', 'Transaction Date', 'Txn Date', 'VALUE DATE'],
            'description_col': ['Description', 'Narration', 'Particulars', 'Remarks'],
            'debit_col': ['Debit', 'Withdrawal', 'Dr', 'Debit Amount'],
            'credit_col': ['Credit', 'Deposit', 'Cr', 'Credit Amount'],
            'balance_col': ['Balance', 'Closing Balance'],
            'date_format': ['%d/%m/%Y', '%d-%m-%Y', '%d %b %Y', '%Y-%m-%d'],
        }
    }
    
    def __init__(self, bank_format='auto'):
        self.bank_format = bank_format
        self.detected_format = None
    
    def parse_file(self, file_content: bytes, filename: str) -> Tuple[List[ParsedTxn], Dict]:
        ext = filename.lower().split('.')[-1]
        if ext == 'pdf':
            return self.parse_pdf(file_content)
        elif ext in ['xlsx', 'xls']:
            return self.parse_excel(file_content)
        elif ext == 'csv':
            return self.parse_csv(file_content)
        raise ValueError(f"Unsupported format: {ext}")
    
    def parse_excel(self, file_content: bytes) -> Tuple[List[ParsedTxn], Dict]:
        df = pd.read_excel(BytesIO(file_content), engine='openpyxl')
        return self._parse_dataframe(df)
    
    def parse_csv(self, file_content: bytes) -> Tuple[List[ParsedTxn], Dict]:
        df = None
        read_error = None
        
        for encoding in ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']:
            try:
                df = pd.read_csv(BytesIO(file_content), encoding=encoding)
                break
            except Exception as e:
                read_error = e
                continue
                
        if df is None:
            raise ValueError(f"Could not decode CSV. Last error: {str(read_error)}")
            
        try:
            return self._parse_dataframe(df)
        except Exception as e:
            raise ValueError(f"Error parsing CSV data: {str(e)}")
    
    def parse_pdf(self, file_content: bytes) -> Tuple[List[ParsedTxn], Dict]:
        try:
            import tabula
            tables = tabula.read_pdf(BytesIO(file_content), pages='all', multiple_tables=True)
            if tables:
                df = pd.concat(tables, ignore_index=True)
                return self._parse_dataframe(df)
        except:
            pass
        raise ValueError("Could not extract tables from PDF")
    
    def _parse_dataframe(self, df: pd.DataFrame) -> Tuple[List[ParsedTxn], Dict]:
        transactions = []
        metadata = {'total_rows': len(df), 'parsed_rows': 0, 'skipped_rows': 0}
        
        format_config = self.BANK_FORMATS.get(self.bank_format if self.bank_format != 'auto' else 'generic')
        columns = self._map_columns(df, format_config)
        
        for idx, row in df.iterrows():
            try:
                txn = self._parse_row(row, columns, format_config, idx)
                if txn:
                    transactions.append(txn)
                    metadata['parsed_rows'] += 1
            except:
                metadata['skipped_rows'] += 1
        
        if transactions:
            transactions.sort(key=lambda x: x.date)
            metadata['period_start'] = transactions[0].date.date() if hasattr(transactions[0].date, 'date') else transactions[0].date
            metadata['period_end'] = transactions[-1].date.date() if hasattr(transactions[-1].date, 'date') else transactions[-1].date
        
        return transactions, metadata
    
    def _map_columns(self, df: pd.DataFrame, config: Dict) -> Dict:
        column_map = {}
        df_columns = {str(c).lower().strip(): c for c in df.columns}
        
        for field, possible_names in [
            ('date', config['date_col']), ('description', config['description_col']),
            ('debit', config['debit_col']), ('credit', config['credit_col']), ('balance', config['balance_col']),
        ]:
            for name in possible_names:
                if name.lower() in df_columns:
                    column_map[field] = df_columns[name.lower()]
                    break
        return column_map
    
    def _parse_row(self, row, columns: Dict, config: Dict, row_idx: int) -> Optional[ParsedTxn]:
        date_val = row.get(columns.get('date'))
        if pd.isna(date_val):
            return None
        
        date = self._parse_date(date_val, config['date_format'])
        if not date:
            return None
        
        description = str(row.get(columns.get('description'), '')).strip()
        if not description:
            return None
        
        debit = self._parse_amount(row.get(columns.get('debit')))
        credit = self._parse_amount(row.get(columns.get('credit')))
        balance = self._parse_amount(row.get(columns.get('balance')))
        
        if not debit and not credit:
            return None
        
        reference, cheque = self._extract_reference(description)
        
        return ParsedTxn(date=date, description=description, debit=debit, credit=credit,
                        balance=balance, reference=reference, cheque_number=cheque, row_number=row_idx + 1)
    
    def _parse_date(self, value, formats: List[str]) -> Optional[datetime]:
        if isinstance(value, datetime):
            return value
        if pd.isna(value):
            return None
        value = str(value).strip()
        for fmt in formats:
            try:
                return datetime.strptime(value, fmt)
            except:
                continue
        return None
    
    def _parse_amount(self, value) -> Optional[Decimal]:
        if pd.isna(value) or value is None:
            return None
        value = str(value).strip()
        if not value or value.lower() in ['nan', 'none', '-', '']:
            return None
        value = re.sub(r'[₹$,\s]', '', value)
        value = re.sub(r'\s*(Dr|Cr)\.?\s*$', '', value, flags=re.IGNORECASE)
        try:
            amount = Decimal(value)
            return amount if amount != 0 else None
        except:
            return None
    
    def _extract_reference(self, description: str) -> Tuple[str, str]:
        reference = ''
        cheque = ''
        upi_match = re.search(r'UPI[/-]?(\d{12})', description, re.IGNORECASE)
        if upi_match:
            reference = upi_match.group(1)
        neft_match = re.search(r'(NEFT|RTGS)[/-]?([A-Z0-9]+)', description, re.IGNORECASE)
        if neft_match:
            reference = neft_match.group(2)
        cheque_match = re.search(r'CHQ\.?\s*(?:NO\.?)?\s*(\d{6})', description, re.IGNORECASE)
        if cheque_match:
            cheque = cheque_match.group(1)
        return reference, cheque


class LedgerSuggestionEngine:
    def __init__(self, company_id: int):
        self.company_id = company_id
        self._load_rules()
    
    def _load_rules(self):
        from apps.companies.models import LedgerMappingRule
        self.rules = list(LedgerMappingRule.objects.filter(
            company_id=self.company_id, is_active=True
        ).select_related('ledger').order_by('-priority'))
    
    def suggest_ledger(self, transaction: ParsedTxn) -> Tuple[Optional[int], float, Optional[int]]:
        description = transaction.description.lower()
        txn_type = 'debit' if transaction.debit else 'credit'
        
        for rule in self.rules:
            if rule.transaction_type not in ['both', txn_type]:
                continue
            
            pattern = rule.pattern.lower()
            matched = False
            
            if rule.pattern_type == 'contains':
                matched = pattern in description
            elif rule.pattern_type == 'starts_with':
                matched = description.startswith(pattern)
            elif rule.pattern_type == 'ends_with':
                matched = description.endswith(pattern)
            elif rule.pattern_type == 'exact':
                matched = description == pattern
            elif rule.pattern_type == 'regex':
                try:
                    matched = bool(re.search(rule.pattern, description, re.IGNORECASE))
                except:
                    pass
            
            if matched:
                confidence = 0.7 + min(0.2, rule.times_used * 0.01)
                return rule.ledger_id, confidence, rule.id
        
        return None, 0.0, None


# ============================================
# SERIALIZERS
# ============================================
class BankAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankAccount
        fields = '__all__'


class BankStatementSerializer(serializers.ModelSerializer):
    mapping_progress = serializers.ReadOnlyField(source='get_mapping_progress')
    
    class Meta:
        model = BankStatement
        fields = '__all__'


class ParsedTransactionSerializer(serializers.ModelSerializer):
    amount = serializers.ReadOnlyField()
    suggested_ledger_name = serializers.CharField(source='suggested_ledger.name', read_only=True)
    mapped_ledger_name = serializers.CharField(source='mapped_ledger.name', read_only=True)
    
    class Meta:
        model = ParsedTransaction
        fields = '__all__'


# ============================================
# VIEWS
# ============================================
class BankAccountListCreateView(generics.ListCreateAPIView):
    serializer_class = BankAccountSerializer
    
    def get_queryset(self):
        return BankAccount.objects.filter(is_active=True)


class BankStatementUploadView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    
    @transaction.atomic
    def post(self, request):
        bank_account_id = request.data.get('bank_account')
        bank_ledger_name = request.data.get('bank_ledger_name', '').strip()
        uploaded_file = request.FILES.get('file')
        
        if not uploaded_file:
            return Response({'error': 'file is required'}, status=400)
        
        bank_account = None
        
        # If bank_account_id is provided and valid, use it
        if bank_account_id:
            try:
                bank_account = BankAccount.objects.get(pk=bank_account_id)
            except (BankAccount.DoesNotExist, ValueError):
                pass
        
        # If no bank_account but we have a Tally ledger name, auto-create one
        if not bank_account and bank_ledger_name:
            from apps.companies.models import Company
            
            # Get the first company (for local dev) or user's company
            company = Company.objects.first()
            if not company:
                return Response({'error': 'No company found. Please create a company first.'}, status=400)
            
            # Create or get bank account from Tally ledger name
            bank_account, created = BankAccount.objects.get_or_create(
                company=company,
                account_number=bank_ledger_name[:50],  # Use ledger name as account number
                defaults={
                    'bank_name': bank_ledger_name,
                    'statement_format': 'auto',
                    'account_type': 'current',
                    'is_active': True
                }
            )
            
            # Ensure Tally ledger is linked
            if bank_ledger_name:
                from apps.companies.models import Ledger
                # Auto-create ledger if it doesn't exist (it might be live from Tally but not synced)
                ledger, _ = Ledger.objects.get_or_create(
                    company=company, 
                    name__iexact=bank_ledger_name,
                    defaults={
                        'name': bank_ledger_name,
                        'ledger_group': 'bank_accounts',
                        'is_active': True
                    }
                )
                if not bank_account.tally_ledger:
                    bank_account.tally_ledger = ledger
                    bank_account.save(update_fields=['tally_ledger'])
        
        if not bank_account:
            return Response({'error': 'Please select a bank account or Tally ledger'}, status=400)
        
        statement = BankStatement.objects.create(
            bank_account=bank_account,
            file=uploaded_file,
            original_filename=uploaded_file.name,
            file_type=uploaded_file.name.split('.')[-1].lower(),
            file_size=uploaded_file.size,
            status='processing',
            processing_started=timezone.now(),
            uploaded_by=request.user
        )
        
        try:
            parser = BankStatementParser(bank_format=bank_account.statement_format)
            
            # Reset file pointer to beginning as it was read during model creation
            uploaded_file.seek(0)
            transactions, metadata = parser.parse_file(uploaded_file.read(), uploaded_file.name)
            
            statement.period_start = metadata.get('period_start')
            statement.period_end = metadata.get('period_end')
            statement.total_transactions = len(transactions)
            
            suggestion_engine = LedgerSuggestionEngine(bank_account.company_id)
            
            parsed_txns = []
            for txn in transactions:
                suggested_id, confidence, _ = suggestion_engine.suggest_ledger(txn)
                
                parsed_txn = ParsedTransaction(
                    statement=statement,
                    date=txn.date.date() if hasattr(txn.date, 'date') else txn.date,
                    description=txn.description,
                    reference_number=txn.reference,
                    debit=txn.debit,
                    credit=txn.credit,
                    balance=txn.balance,
                    cheque_number=txn.cheque_number,
                    row_number=txn.row_number,
                    suggested_ledger_id=suggested_id,
                    confidence_score=confidence,
                    status='auto_mapped' if suggested_id and confidence >= 0.6 else 'pending'
                )
                parsed_txns.append(parsed_txn)
            
            ParsedTransaction.objects.bulk_create(parsed_txns)
            
            statement.mapped_transactions = ParsedTransaction.objects.filter(
                statement=statement, status__in=['auto_mapped', 'manually_mapped']
            ).count()
            statement.status = 'parsed'
            statement.processing_completed = timezone.now()
            statement.save()
            
            return Response({
                'message': 'Statement parsed successfully',
                'statement': BankStatementSerializer(statement).data,
                'metadata': metadata
            }, status=201)
            
        except Exception as e:
            statement.status = 'failed'
            statement.error_message = str(e)
            statement.save()
            return Response({'error': str(e)}, status=400)



class BankStatementListView(generics.ListAPIView):
    serializer_class = BankStatementSerializer
    
    def get_queryset(self):
        return BankStatement.objects.all()


class TransactionListView(generics.ListAPIView):
    serializer_class = ParsedTransactionSerializer
    pagination_class = None
    
    def get_queryset(self):
        statement_id = self.kwargs.get('statement_id')
        return ParsedTransaction.objects.filter(statement_id=statement_id)


class TransactionMapView(APIView):
    @transaction.atomic
    def post(self, request):
        transaction_ids = request.data.get('transaction_ids', [])
        if not transaction_ids:
            return Response({'error': 'No transactions selected'}, status=400)

        ledger_id = request.data.get('ledger_id')
        ledger_name = request.data.get('ledger_name')
        
        if not ledger_name and not ledger_id:
             return Response({'error': 'Ledger is required'}, status=400)

        from apps.companies.models import Ledger, LedgerMappingRule
        
        # Get context from first transaction
        first_txn = ParsedTransaction.objects.filter(id=transaction_ids[0]).select_related('statement__bank_account__company').first()
        if not first_txn:
             return Response({'error': 'Transaction not found'}, status=404)
             
        company = first_txn.statement.bank_account.company
        
        # 1. Resolve Ledger (Find or Create)
        if not ledger_id:
            ledger_name = ledger_name.strip()
            ledger = Ledger.objects.filter(company=company, name__iexact=ledger_name).first()
            
            if not ledger:
                # Auto-create placeholder ledger to prevent "Not Found" error
                # This allows work to continue even if Tally sync hasn't happened yet
                ledger = Ledger.objects.create(
                    company=company,
                    name=ledger_name,
                    ledger_group='suspense_account', # Default group until synced
                    is_active=True,
                    synced_from_tally=False
                )
            ledger_id = ledger.id
        else:
            ledger = Ledger.objects.get(pk=ledger_id)

        # 2. Map Transactions
        transactions = ParsedTransaction.objects.filter(id__in=transaction_ids)
        updated = transactions.update(
            mapped_ledger_id=ledger_id,
            status='manually_mapped',
            mapped_by=request.user,
            mapped_at=timezone.now()
        )
        
        # 3. Learn Rule (Smart Pattern Generation)
        # Instead of strict exact match, we try to create a REGEX pattern that ignores variable parts
        # like Reference Numbers, Dates, etc.
        
        raw_description = first_txn.description.strip()
        
        # Helper to generate regex from description
        def generate_smart_pattern(text):
            # Escape valid regex characters first to be safe
            pattern = re.escape(text)
            
            # 1. Replace Date-like patterns (DD/MM/YYYY, DD-MM-YYYY, etc) with .*
            # specific enough to catch common formats but generic enough to be safe
            pattern = re.sub(r'\d{2}[-/]\d{2}[-/]\d{4}', '.*', pattern)
            
            # 2. Replace long sequences of digits (likely ref numbers, > 4 digits)
            pattern = re.sub(r'\d{5,}', '.*', pattern)
            
            # 3. Replace mixed alphanumeric IDs that are roughly ref-number like (e.g. UPI/12304/...)
            # This is tricky without being too aggressive. 
            # safe bet: if we see "text-NUMBER-text", replace NUMBER.
            
            # Let's simple-ify: Collapse multiple .* into one
            pattern = re.sub(r'(\.\*)+', '.*', pattern)
            
            # If pattern starts/ends with .*, remove them for cleaner storage if we use 'contains' logic,
            # but for 'regex' type, keeping them allowed is fine.
            # However, for robustness, if the entire string becomes ".*", that's bad.
            if pattern == '.*' or pattern == '':
                return text, 'exact' # Fallback to exact
                
            return pattern, 'regex'

        pattern, pattern_type = generate_smart_pattern(raw_description)
        
        # Check if rule exists with this pattern
        if not LedgerMappingRule.objects.filter(company=company, pattern=pattern, ledger=ledger).exists():
             LedgerMappingRule.objects.create(
                 company=company,
                 pattern=pattern,
                 pattern_type=pattern_type, 
                 ledger=ledger,
                 transaction_type='both', 
                 priority=5, # Higher priority for specific learned rules
                 created_by=request.user
             )
        
        return Response({'message': f'{updated} transactions mapped'})


class TransactionApproveView(APIView):
    @transaction.atomic
    def post(self, request):
        transaction_ids = request.data.get('transaction_ids', [])
        
        transactions = ParsedTransaction.objects.filter(
            id__in=transaction_ids,
            status__in=['auto_mapped', 'manually_mapped']
        )
        
        # For auto-mapped transactions, we must commit the suggested_ledger to mapped_ledger
        # We can't use simple update() for this because it involves field-to-field copy
        # So we iterate or use F expressions
        from django.db.models import F
        
        # 1. Update auto_mapped ones that don't have mapped_ledger
        transactions.filter(status='auto_mapped', mapped_ledger__isnull=True).update(
            mapped_ledger=F('suggested_ledger')
        )
        
        # 2. Now approve all
        updated = transactions.update(status='approved')
        
        return Response({'message': f'{updated} transactions approved'})


class GenerateVouchersView(APIView):
    @transaction.atomic
    def post(self, request):
        statement_id = request.data.get('statement_id')
        statement = BankStatement.objects.get(pk=statement_id)
        
        transactions = ParsedTransaction.objects.filter(statement=statement, status='approved')
        
        if not transactions.exists():
            return Response({'error': 'No approved transactions'}, status=400)
        
        bank_ledger = statement.bank_account.tally_ledger
        
        # Auto-repair: Try to find ledger if missing
        if not bank_ledger and statement.bank_account.bank_name:
            from apps.companies.models import Ledger
            # Auto-create if missing (trusting bank_name is the ledger name from upload)
            ledger, _ = Ledger.objects.get_or_create(
                company=statement.bank_account.company, 
                name__iexact=statement.bank_account.bank_name,
                defaults={
                    'name': statement.bank_account.bank_name,
                    'ledger_group': 'bank_accounts',
                    'is_active': True
                }
            )
            statement.bank_account.tally_ledger = ledger
            statement.bank_account.save(update_fields=['tally_ledger'])
            bank_ledger = ledger

        if not bank_ledger:
            return Response({'error': 'Bank account not linked to Tally ledger'}, status=400)
        
        from apps.vouchers.models import Voucher, VoucherEntry
        
        created = []
        for txn in transactions:
            voucher_type = 'payment' if txn.debit else 'receipt'
            
            voucher = Voucher.objects.create(
                company=statement.bank_account.company,
                voucher_type=voucher_type,
                date=txn.date,
                reference=txn.reference_number or txn.cheque_number,
                narration=txn.description,
                amount=txn.amount,
                party_ledger=txn.mapped_ledger,
                source='bank_statement',
                status='pending_approval',
                created_by=request.user
            )
            
            if voucher_type == 'payment':
                VoucherEntry.objects.create(voucher=voucher, ledger=txn.mapped_ledger, amount=txn.amount, is_debit=True, order=1)
                VoucherEntry.objects.create(voucher=voucher, ledger=bank_ledger, amount=txn.amount, is_debit=False, order=2)
            else:
                VoucherEntry.objects.create(voucher=voucher, ledger=bank_ledger, amount=txn.amount, is_debit=True, order=1)
                VoucherEntry.objects.create(voucher=voucher, ledger=txn.mapped_ledger, amount=txn.amount, is_debit=False, order=2)
            
            txn.voucher = voucher
            txn.status = 'voucher_created'
            txn.save()
            created.append(voucher)
        
        return Response({'message': f'{len(created)} vouchers created', 'voucher_ids': [v.id for v in created]})

class BankStatementDetailView(generics.RetrieveDestroyAPIView):
    queryset = BankStatement.objects.all()
    serializer_class = BankStatementSerializer


class TransactionAutoMapView(APIView):
    @transaction.atomic
    def post(self, request):
        statement_id = request.data.get('statement_id')
        if not statement_id:
            return Response({'error': 'statement_id is required'}, status=400)
            
        statement = BankStatement.objects.get(pk=statement_id)
        
        # Get pending transactions
        transactions = ParsedTransaction.objects.filter(
            statement=statement, 
            status='pending'
        )
        
        if not transactions.exists():
            return Response({'message': 'No pending transactions to auto-map'})
            
        suggestion_engine = LedgerSuggestionEngine(statement.bank_account.company_id)
        
        mapped_count = 0
        updates = []
        
        for txn in transactions:
            suggested_id, confidence, rule_id = suggestion_engine.suggest_ledger(txn)
            
            if suggested_id and confidence >= 0.6:
                txn.suggested_ledger_id = suggested_id
                txn.confidence_score = confidence
                txn.status = 'auto_mapped'
                txn.mapped_ledger_id = suggested_id
                txn.mapped_by = request.user
                txn.mapped_at = timezone.now()
                updates.append(txn)
                mapped_count += 1
                
                # Update rule usage
                if rule_id:
                     from apps.companies.models import LedgerMappingRule
                     LedgerMappingRule.objects.filter(pk=rule_id).update(times_used=models.F('times_used') + 1)
        
        if updates:
            ParsedTransaction.objects.bulk_update(updates, ['suggested_ledger', 'confidence_score', 'status', 'mapped_ledger', 'mapped_by', 'mapped_at'])
            
            # Update statement stats
            statement.mapped_transactions = ParsedTransaction.objects.filter(
                statement=statement, status__in=['auto_mapped', 'manually_mapped']
            ).count()
            statement.save()
            
        return Response({'message': f'{mapped_count} transactions auto-mapped successfully'})


class PushStatementVouchersView(APIView):
    @transaction.atomic
    def post(self, request):
        try:
            statement_id = request.data.get('statement_id')
            transaction_ids = request.data.get('transaction_ids', [])
            
            if not statement_id:
                return Response({'error': 'statement_id is required'}, status=400)
                
            statement = BankStatement.objects.get(pk=statement_id)
            
            # 1. Identify Transactions
            txn_filter = {'statement': statement}
            if transaction_ids:
                txn_filter['id__in'] = transaction_ids
                
            transactions = ParsedTransaction.objects.filter(**txn_filter).select_related('voucher')
            
            if not transactions.exists():
                return Response({'error': 'No transactions found to push'}, status=400)

            # 2. Auto-Process Workflow (Map -> Approve -> Generate -> Push)
            
            # A. Approve Mapped Transactions
            mapped_txns = transactions.filter(status__in=['auto_mapped', 'manually_mapped'])
            if mapped_txns.exists():
                from django.db.models import F
                # Commit suggestions to mapped_ledger for auto_mapped ones
                mapped_txns.filter(status='auto_mapped', mapped_ledger__isnull=True).update(
                    mapped_ledger=F('suggested_ledger')
                )
                mapped_txns.update(status='approved')
            
            # B. Generate Vouchers for Approved Transactions (that don't have one)
            target_txns = ParsedTransaction.objects.filter(**txn_filter, status='approved', voucher__isnull=True)
            
            if target_txns.exists():
                from apps.vouchers.models import Voucher, VoucherEntry
                
                # Check Bank Ledger ONCE
                bank_ledger = statement.bank_account.tally_ledger
                
                # Auto-repair: Try to find ledger if missing
                if not bank_ledger and statement.bank_account.bank_name:
                    from apps.companies.models import Ledger
                    # Auto-create if missing (trusting bank_name is the ledger name from upload)
                    ledger, _ = Ledger.objects.get_or_create(
                        company=statement.bank_account.company, 
                        name__iexact=statement.bank_account.bank_name,
                        defaults={
                            'name': statement.bank_account.bank_name,
                            'ledger_group': 'bank_accounts',
                            'is_active': True
                        }
                    )
                    statement.bank_account.tally_ledger = ledger
                    statement.bank_account.save(update_fields=['tally_ledger'])
                    bank_ledger = ledger

                if not bank_ledger:
                    return Response({'error': 'Bank account not linked to Tally ledger. Please configure in Settings/Companies.'}, status=400)
                
                for txn in target_txns:
                    if not txn.mapped_ledger:
                        continue
                        
                    # Create Voucher
                    voucher = Voucher.objects.create(
                        company=statement.bank_account.company,
                        voucher_type='Payment' if txn.debit else 'Receipt',
                        date=txn.date,
                        reference=f"txn-{txn.id}",
                        narration=txn.description,
                        status='approved',
                        created_by=request.user,
                        amount=txn.amount 
                    )
                    
                    amount = txn.debit or txn.credit or 0
                    is_payment = bool(txn.debit) 
                    
                    # Bank Entry
                    VoucherEntry.objects.create(
                        voucher=voucher,
                        ledger=bank_ledger,
                        amount=amount,
                        is_debit=not is_payment
                    )
                    
                    # Party Entry
                    VoucherEntry.objects.create(
                        voucher=voucher,
                        ledger=txn.mapped_ledger,
                        amount=amount,
                        is_debit=is_payment
                    )
                    
                    txn.voucher = voucher
                    txn.status = 'voucher_created'
                    txn.save()
                    
            # 3. Push Vouchers
            final_txns = ParsedTransaction.objects.filter(**txn_filter, voucher__isnull=False).select_related('voucher')
            
            vouchers_to_push = set()
            for txn in final_txns:
                if txn.voucher.status in ['approved', 'queued', 'failed']:
                    vouchers_to_push.add(txn.voucher)
                    
            if not vouchers_to_push:
                 return Response({'error': 'No ready vouchers found/generated to push'}, status=400)

            from apps.tally_connector.models import DesktopConnector, SyncOperation
            connector = DesktopConnector.objects.filter(company=statement.bank_account.company, status='active').first()
            
            # Auto-provision connector if missing to unblock user
            if not connector:
                 # Check if any connector exists (even inactive)
                 connector = DesktopConnector.objects.filter(company=statement.bank_account.company).first()
                 if not connector:
                     connector = DesktopConnector(
                         company=statement.bank_account.company,
                         name="Auto-Created Connector",
                         tally_host="localhost",
                         tally_port=9000,
                         status="active"
                     )
                     connector.generate_api_key()
                     connector.save()
                 elif connector.status != 'active':
                     connector.status = 'active'
                     connector.save()
            
            if not connector:
                 return Response({'error': 'Failed to auto-provision Tally connector'}, status=500)
                 
            queued_count = 0
            synced_count = 0
            
            # Hybrid Sync: Try Direct execution if Localhost, else Queue
            import requests
            
            for voucher in vouchers_to_push:
                if voucher.status == 'queued':
                    continue

                op = SyncOperation.objects.create(
                    connector=connector,
                    operation_type='create_voucher',
                    voucher=voucher,
                    request_xml=voucher.generate_tally_xml(),
                    priority=2
                )
                voucher.status = 'queued'
                voucher.save()
                queued_count += 1
                
                # Direct Sync Attempt (Fast Path)
                if connector.tally_host in ['localhost', '127.0.0.1']:
                    try:
                        tally_url = f"http://{connector.tally_host}:{connector.tally_port}"
                        resp = requests.post(tally_url, data=op.request_xml, timeout=3)
                        
                        if resp.status_code == 200:
                            # Parse response to ensure it's not a Tally error
                            # Simple check: <CREATED>1</CREATED> or <ERRORS>0</ERRORS>
                            # Logic: If 200 OK and no errors
                            if b"<CREATED>1</CREATED>" in resp.content or b"<ERRORS>0</ERRORS>" in resp.content:
                                voucher.status = 'synced'
                                voucher.sync_completed_at = timezone.now()
                                voucher.save()
                                op.status = 'completed'
                                op.completed_at = timezone.now()
                                op.response_xml = resp.text
                                op.save()
                                synced_count += 1
                                queued_count -= 1
                    except Exception:
                        # Fallback to queued mode silently if Tally is not reachable or timeouts
                        pass
                
            msg = f'{synced_count} vouchers synced directly, ' if synced_count > 0 else ''
            msg += f'{queued_count} vouchers queued (processed {len(transactions)} transactions)'
            
            return Response({'message': msg})
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return Response({'error': f'Internal Error: {str(e)}'}, status=400)
