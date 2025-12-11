from django.urls import path
from .models import (NotificationListView, NotificationMarkReadView, NotificationMarkAllReadView,
                     NotificationPreferenceView, ComplianceReminderListView, UnreadCountView)

urlpatterns = [
    path('', NotificationListView.as_view(), name='notifications'),
    path('<int:pk>/read/', NotificationMarkReadView.as_view(), name='mark-read'),
    path('read-all/', NotificationMarkAllReadView.as_view(), name='mark-all-read'),
    path('preferences/', NotificationPreferenceView.as_view(), name='preferences'),
    path('<int:company_id>/compliance-reminders/', ComplianceReminderListView.as_view(), name='compliance-reminders'),
    path('unread-count/', UnreadCountView.as_view(), name='unread-count'),
]
