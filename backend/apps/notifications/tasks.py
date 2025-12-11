"""Celery Tasks for Notifications"""
from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


@shared_task
def send_notification(user_id: int, event: str, data: dict = None):
    """Send notification to user"""
    from apps.notifications.models import NotificationService
    from apps.users.models import User
    
    user = User.objects.get(pk=user_id)
    notification = NotificationService.notify_user(user, event, data)
    
    if notification:
        logger.info(f"Sent notification {notification.id} to user {user_id}")
    return {'notification_id': notification.id if notification else None}


@shared_task
def send_bulk_notifications(user_ids: list, event: str, data: dict = None):
    """Send notification to multiple users"""
    for user_id in user_ids:
        send_notification.delay(user_id, event, data)
    return {'queued': len(user_ids)}


@shared_task
def generate_compliance_reminders():
    """Generate compliance reminders for all companies"""
    from apps.notifications.models import ComplianceReminderService
    from apps.companies.models import Company
    from django.utils import timezone
    
    today = timezone.now().date()
    
    for company in Company.objects.filter(is_active=True):
        ComplianceReminderService.generate_monthly_reminders(
            company.id, today.month, today.year
        )
    
    logger.info("Generated compliance reminders")


@shared_task
def send_compliance_due_reminders():
    """Send reminders for upcoming compliance due dates"""
    from apps.notifications.models import ComplianceReminderService
    
    ComplianceReminderService.send_due_reminders(days_before=3)
    ComplianceReminderService.send_due_reminders(days_before=1)
    
    logger.info("Sent compliance due reminders")


@shared_task
def send_weekly_summary():
    """Send weekly summary to users"""
    from apps.users.models import User
    from apps.notifications.models import NotificationPreference
    
    users = User.objects.filter(
        is_active=True,
        notification_preferences__weekly_summary=True
    )
    
    for user in users:
        # Generate summary data
        summary_data = {
            'period': 'Last 7 days',
            'vouchers_created': 0,  # TODO: Calculate actual stats
            'vouchers_synced': 0,
            'invoices_processed': 0
        }
        send_notification.delay(user.id, 'weekly_summary', summary_data)
    
    logger.info(f"Queued weekly summary for {users.count()} users")


@shared_task
def check_connector_status():
    """Check for offline connectors and notify"""
    from apps.tally_connector.models import DesktopConnector
    from apps.users.models import User
    from django.utils import timezone
    from datetime import timedelta
    
    threshold = timezone.now() - timedelta(minutes=10)
    
    offline_connectors = DesktopConnector.objects.filter(
        status='active',
        last_heartbeat__lt=threshold
    )
    
    for connector in offline_connectors:
        connector.status = 'disconnected'
        connector.save()
        
        # Notify admins
        admins = User.objects.filter(role='admin')
        for admin in admins:
            send_notification.delay(
                admin.id,
                'connector_offline',
                {'connector_name': connector.name, 'company': connector.company.name}
            )
    
    if offline_connectors.exists():
        logger.warning(f"Marked {offline_connectors.count()} connectors as disconnected")
