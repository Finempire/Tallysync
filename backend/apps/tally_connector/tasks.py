"""Celery Tasks for Tally Sync Operations"""
from celery import shared_task
from celery.utils.log import get_task_logger
from django.utils import timezone

logger = get_task_logger(__name__)


@shared_task(bind=True, max_retries=3)
def process_sync_operation(self, operation_id: str):
    """Process a single sync operation (called by desktop connector webhook)"""
    from apps.tally_connector.models import SyncOperation
    
    try:
        operation = SyncOperation.objects.get(pk=operation_id)
        operation.status = 'in_progress'
        operation.started_at = timezone.now()
        operation.save()
        
        logger.info(f"Processing sync operation {operation_id}")
        
        # Operation is processed by desktop connector
        # This task just monitors timeout
        
    except Exception as e:
        logger.error(f"Sync operation {operation_id} failed: {e}")
        raise self.retry(exc=e)


@shared_task
def check_stale_operations():
    """Check for operations stuck in processing"""
    from apps.tally_connector.models import SyncOperation
    from datetime import timedelta
    
    stale_cutoff = timezone.now() - timedelta(minutes=10)
    
    stale_ops = SyncOperation.objects.filter(
        status='in_progress',
        started_at__lt=stale_cutoff
    )
    
    for op in stale_ops:
        if op.retry_count < op.max_retries:
            op.status = 'pending'
            op.retry_count += 1
            op.save()
            logger.info(f"Retrying stale operation {op.id}")
        else:
            op.status = 'failed'
            op.error_message = 'Operation timed out'
            op.save()
            logger.error(f"Operation {op.id} failed after max retries")


@shared_task
def sync_ledgers_from_tally(company_id: int, connector_id: str):
    """Queue operation to sync ledgers from Tally"""
    from apps.tally_connector.models import SyncOperation, DesktopConnector, LedgerSyncXMLBuilder
    
    connector = DesktopConnector.objects.get(pk=connector_id)
    builder = LedgerSyncXMLBuilder()
    
    operation = SyncOperation.objects.create(
        connector=connector,
        operation_type='sync_ledgers',
        request_xml=builder.build_export_request(),
        priority=2
    )
    
    logger.info(f"Queued ledger sync operation {operation.id}")
    return str(operation.id)


@shared_task
def queue_voucher_sync(voucher_id: int):
    """Queue a voucher for Tally sync"""
    from apps.vouchers.models import Voucher
    from apps.tally_connector.models import SyncOperation, VoucherXMLBuilder
    
    voucher = Voucher.objects.select_related('company').prefetch_related('entries__ledger').get(pk=voucher_id)
    
    connector = voucher.company.connectors.filter(status='active').first()
    if not connector:
        logger.warning(f"No active connector for company {voucher.company_id}")
        return None
    
    builder = VoucherXMLBuilder()
    xml = builder.build_create_voucher(voucher)
    
    operation = SyncOperation.objects.create(
        connector=connector,
        voucher=voucher,
        operation_type='create_voucher',
        request_xml=xml,
        priority=1
    )
    
    voucher.status = 'queued'
    voucher.save()
    
    logger.info(f"Queued voucher {voucher_id} for sync")
    return str(operation.id)


@shared_task
def bulk_queue_vouchers(voucher_ids: list):
    """Queue multiple vouchers for Tally sync"""
    results = []
    for vid in voucher_ids:
        result = queue_voucher_sync.delay(vid)
        results.append(result.id)
    return results
