"""Celery configuration"""
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('tally_automation')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.task_routes = {
    'apps.bank_statements.tasks.*': {'queue': 'bank_statements'},
    'apps.tally_connector.tasks.*': {'queue': 'tally_sync'},
    'apps.invoices.tasks.*': {'queue': 'ocr'},
    'apps.payroll.tasks.*': {'queue': 'payroll'},
    'apps.notifications.tasks.*': {'queue': 'notifications'},
}

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
