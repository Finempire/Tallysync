"""
Celery Tasks for Bank Statement Processing
"""
from celery import shared_task
from celery.utils.log import get_task_logger
from django.db import transaction

logger = get_task_logger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_bank_statement(self, statement_id: int):
    """Process uploaded bank statement asynchronously"""
    from apps.bank_statements.models import BankStatement, ParsedTransaction, BankStatementParser, LedgerSuggestionEngine
    
    try:
        statement = BankStatement.objects.get(pk=statement_id)
        statement.status = 'processing'
        statement.save()
        
        logger.info(f"Processing bank statement {statement_id}")
        
        # Parse the file
        parser = BankStatementParser(statement.bank_account.bank_format)
        file_path = statement.file.path
        
        if file_path.endswith('.pdf'):
            transactions = parser.parse_pdf(file_path)
        elif file_path.endswith(('.xlsx', '.xls')):
            transactions = parser.parse_excel(file_path)
        else:
            transactions = parser.parse_csv(file_path)
        
        # Create parsed transactions
        suggestion_engine = LedgerSuggestionEngine(statement.bank_account.company_id)
        
        with transaction.atomic():
            for idx, txn in enumerate(transactions):
                # Get ledger suggestion
                suggested_ledger, confidence = suggestion_engine.suggest_ledger(txn['description'])
                
                ParsedTransaction.objects.create(
                    statement=statement,
                    date=txn['date'],
                    description=txn['description'],
                    debit=txn.get('debit', 0),
                    credit=txn.get('credit', 0),
                    balance=txn.get('balance', 0),
                    reference_number=txn.get('reference'),
                    suggested_ledger=suggested_ledger,
                    confidence_score=confidence,
                    row_number=idx + 1
                )
            
            statement.total_transactions = len(transactions)
            statement.status = 'parsed'
            statement.save()
        
        logger.info(f"Parsed {len(transactions)} transactions from statement {statement_id}")
        return {'status': 'success', 'transactions': len(transactions)}
        
    except Exception as e:
        logger.error(f"Failed to process statement {statement_id}: {e}")
        statement.status = 'failed'
        statement.error_message = str(e)
        statement.save()
        raise self.retry(exc=e)


@shared_task
def generate_vouchers_from_transactions(transaction_ids: list, user_id: int):
    """Generate vouchers from approved transactions"""
    from apps.bank_statements.models import ParsedTransaction
    from apps.vouchers.models import Voucher, VoucherEntry
    
    logger.info(f"Generating vouchers for {len(transaction_ids)} transactions")
    
    vouchers_created = 0
    
    for txn_id in transaction_ids:
        try:
            txn = ParsedTransaction.objects.select_related('statement__bank_account__company').get(pk=txn_id)
            
            if not txn.mapped_ledger or txn.status != 'approved':
                continue
            
            company = txn.statement.bank_account.company
            bank_ledger = txn.statement.bank_account.default_ledger
            
            # Determine voucher type
            is_receipt = txn.credit > 0
            voucher_type = 'receipt' if is_receipt else 'payment'
            amount = txn.credit if is_receipt else txn.debit
            
            with transaction.atomic():
                voucher = Voucher.objects.create(
                    company=company,
                    voucher_type=voucher_type,
                    date=txn.date,
                    amount=amount,
                    narration=txn.description,
                    source='bank_statement',
                    created_by_id=user_id
                )
                
                # Bank entry
                VoucherEntry.objects.create(
                    voucher=voucher,
                    ledger=bank_ledger,
                    amount=amount,
                    is_debit=is_receipt
                )
                
                # Party entry
                VoucherEntry.objects.create(
                    voucher=voucher,
                    ledger=txn.mapped_ledger,
                    amount=amount,
                    is_debit=not is_receipt
                )
                
                txn.voucher = voucher
                txn.status = 'voucher_created'
                txn.save()
                
                vouchers_created += 1
                
        except Exception as e:
            logger.error(f"Failed to create voucher for transaction {txn_id}: {e}")
    
    logger.info(f"Created {vouchers_created} vouchers")
    return {'vouchers_created': vouchers_created}


@shared_task
def auto_map_transactions(statement_id: int):
    """Auto-map transactions with high confidence suggestions"""
    from apps.bank_statements.models import BankStatement, ParsedTransaction
    
    statement = BankStatement.objects.get(pk=statement_id)
    transactions = ParsedTransaction.objects.filter(
        statement=statement,
        status='pending',
        confidence_score__gte=0.85
    )
    
    mapped_count = 0
    for txn in transactions:
        if txn.suggested_ledger:
            txn.mapped_ledger = txn.suggested_ledger
            txn.status = 'mapped'
            txn.save()
            mapped_count += 1
    
    # Update statement mapping progress
    total = statement.transactions.count()
    mapped = statement.transactions.filter(status__in=['mapped', 'approved']).count()
    statement.mapping_progress = int((mapped / total) * 100) if total > 0 else 0
    statement.save()
    
    logger.info(f"Auto-mapped {mapped_count} transactions for statement {statement_id}")
    return {'auto_mapped': mapped_count}
