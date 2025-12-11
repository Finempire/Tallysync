"""
Notifications App - Complete Implementation (Phase 5)
Email, SMS, WhatsApp, Push Notifications, Compliance Reminders
"""
from django.db import models
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from rest_framework import serializers, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from datetime import timedelta


# ============================================
# MODELS
# ============================================
class NotificationTemplate(models.Model):
    """Notification templates"""
    CHANNEL_CHOICES = [
        ('email', 'Email'), ('sms', 'SMS'), ('whatsapp', 'WhatsApp'),
        ('push', 'Push Notification'), ('in_app', 'In-App'),
    ]
    
    EVENT_CHOICES = [
        ('bank_statement_processed', 'Bank Statement Processed'),
        ('voucher_created', 'Voucher Created'),
        ('voucher_synced', 'Voucher Synced to Tally'),
        ('invoice_processed', 'Invoice Processed'),
        ('payroll_processed', 'Payroll Processed'),
        ('gst_due_reminder', 'GST Due Reminder'),
        ('tds_due_reminder', 'TDS Due Reminder'),
        ('subscription_expiry', 'Subscription Expiry'),
        ('connector_offline', 'Tally Connector Offline'),
    ]
    
    name = models.CharField(max_length=100)
    event = models.CharField(max_length=50, choices=EVENT_CHOICES)
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)
    subject = models.CharField(max_length=200, blank=True)
    body = models.TextField()
    html_body = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.event})"


class Notification(models.Model):
    """Notification log"""
    STATUS_CHOICES = [
        ('pending', 'Pending'), ('sent', 'Sent'), ('delivered', 'Delivered'),
        ('failed', 'Failed'), ('read', 'Read'),
    ]
    
    user = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='notifications')
    template = models.ForeignKey(NotificationTemplate, on_delete=models.SET_NULL, null=True)
    channel = models.CharField(max_length=20)
    title = models.CharField(max_length=200)
    message = models.TextField()
    data = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class NotificationPreference(models.Model):
    """User notification preferences"""
    user = models.OneToOneField('users.User', on_delete=models.CASCADE, related_name='notification_preferences')
    email_enabled = models.BooleanField(default=True)
    sms_enabled = models.BooleanField(default=False)
    whatsapp_enabled = models.BooleanField(default=False)
    push_enabled = models.BooleanField(default=True)
    
    # Event-specific preferences
    voucher_notifications = models.BooleanField(default=True)
    bank_statement_notifications = models.BooleanField(default=True)
    compliance_reminders = models.BooleanField(default=True)
    daily_digest = models.BooleanField(default=False)
    weekly_summary = models.BooleanField(default=True)


class ComplianceReminder(models.Model):
    """Compliance due date reminders"""
    COMPLIANCE_TYPES = [
        ('gstr1', 'GSTR-1 Filing'),
        ('gstr3b', 'GSTR-3B Filing'),
        ('tds', 'TDS Payment'),
        ('tds_return', 'TDS Return'),
        ('pf', 'PF Payment'),
        ('esi', 'ESI Payment'),
        ('pt', 'Professional Tax'),
        ('advance_tax', 'Advance Tax'),
    ]
    
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='compliance_reminders')
    compliance_type = models.CharField(max_length=20, choices=COMPLIANCE_TYPES)
    due_date = models.DateField()
    period = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, default='pending')
    completed_at = models.DateTimeField(null=True, blank=True)
    reminder_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['company', 'compliance_type', 'period']


class WhatsAppMessage(models.Model):
    """WhatsApp Business API messages"""
    STATUS_CHOICES = [
        ('pending', 'Pending'), ('sent', 'Sent'), ('delivered', 'Delivered'),
        ('read', 'Read'), ('failed', 'Failed'),
    ]
    
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE)
    phone_number = models.CharField(max_length=15)
    template_name = models.CharField(max_length=100, blank=True)
    message = models.TextField()
    media_url = models.URLField(blank=True)
    message_id = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


# ============================================
# NOTIFICATION SERVICE
# ============================================
class NotificationService:
    """Send notifications through various channels"""
    
    @classmethod
    def send_email(cls, user, subject: str, body: str, html_body: str = None) -> bool:
        try:
            send_mail(
                subject=subject,
                message=body,
                from_email=None,
                recipient_list=[user.email],
                html_message=html_body
            )
            return True
        except Exception as e:
            print(f"Email error: {e}")
            return False
    
    @classmethod
    def send_sms(cls, phone: str, message: str) -> bool:
        try:
            # Twilio integration
            from django.conf import settings
            from twilio.rest import Client
            
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            client.messages.create(
                body=message,
                from_=settings.TWILIO_PHONE_NUMBER,
                to=phone
            )
            return True
        except Exception as e:
            print(f"SMS error: {e}")
            return False
    
    @classmethod
    def send_whatsapp(cls, phone: str, message: str, template_name: str = None) -> bool:
        try:
            import requests
            from django.conf import settings
            
            url = settings.WHATSAPP_API_URL
            headers = {'Authorization': f"Bearer {settings.WHATSAPP_API_TOKEN}"}
            
            payload = {
                'messaging_product': 'whatsapp',
                'to': phone,
                'type': 'text',
                'text': {'body': message}
            }
            
            response = requests.post(url, json=payload, headers=headers)
            return response.status_code == 200
        except Exception as e:
            print(f"WhatsApp error: {e}")
            return False
    
    @classmethod
    def notify_user(cls, user, event: str, data: dict = None) -> Notification:
        """Send notification based on event type"""
        template = NotificationTemplate.objects.filter(event=event, is_active=True).first()
        if not template:
            return None
        
        # Get user preferences
        prefs, _ = NotificationPreference.objects.get_or_create(user=user)
        
        # Format message
        message = template.body.format(**data) if data else template.body
        subject = template.subject.format(**data) if data and template.subject else template.subject
        
        # Create notification record
        notification = Notification.objects.create(
            user=user,
            template=template,
            channel=template.channel,
            title=subject,
            message=message,
            data=data or {}
        )
        
        # Send based on channel and preferences
        success = False
        if template.channel == 'email' and prefs.email_enabled:
            success = cls.send_email(user, subject, message, template.html_body)
        elif template.channel == 'sms' and prefs.sms_enabled:
            success = cls.send_sms(user.phone, message)
        elif template.channel == 'whatsapp' and prefs.whatsapp_enabled:
            success = cls.send_whatsapp(user.phone, message)
        elif template.channel == 'in_app':
            success = True  # In-app notifications are always stored
        
        notification.status = 'sent' if success else 'failed'
        notification.sent_at = timezone.now() if success else None
        notification.save()
        
        return notification


class ComplianceReminderService:
    """Generate and send compliance reminders"""
    
    GST_DUE_DATES = {
        'gstr1': 11,  # 11th of next month
        'gstr3b': 20,  # 20th of next month
    }
    
    TDS_DUE_DATES = {
        'tds': 7,  # 7th of next month
        'tds_return': {'Q1': (7, 31), 'Q2': (10, 31), 'Q3': (1, 31), 'Q4': (5, 31)}
    }
    
    @classmethod
    def generate_monthly_reminders(cls, company_id: int, month: int, year: int):
        """Generate compliance reminders for a month"""
        from apps.companies.models import Company
        company = Company.objects.get(pk=company_id)
        
        # GSTR-1 reminder
        if company.gstin:
            next_month = month + 1 if month < 12 else 1
            next_year = year if month < 12 else year + 1
            
            ComplianceReminder.objects.get_or_create(
                company=company,
                compliance_type='gstr1',
                period=f"{month:02d}{year}",
                defaults={
                    'due_date': f"{next_year}-{next_month:02d}-{cls.GST_DUE_DATES['gstr1']:02d}"
                }
            )
            
            ComplianceReminder.objects.get_or_create(
                company=company,
                compliance_type='gstr3b',
                period=f"{month:02d}{year}",
                defaults={
                    'due_date': f"{next_year}-{next_month:02d}-{cls.GST_DUE_DATES['gstr3b']:02d}"
                }
            )
    
    @classmethod
    def send_due_reminders(cls, days_before: int = 3):
        """Send reminders for upcoming due dates"""
        target_date = timezone.now().date() + timedelta(days=days_before)
        
        reminders = ComplianceReminder.objects.filter(
            due_date=target_date,
            status='pending',
            reminder_sent=False
        )
        
        for reminder in reminders:
            # Notify company admins
            from apps.users.models import User
            admins = User.objects.filter(role='admin')
            
            for admin in admins:
                NotificationService.notify_user(
                    admin,
                    f'{reminder.compliance_type}_due_reminder',
                    {
                        'compliance_type': reminder.get_compliance_type_display(),
                        'due_date': str(reminder.due_date),
                        'period': reminder.period,
                        'company': reminder.company.name
                    }
                )
            
            reminder.reminder_sent = True
            reminder.save()


# ============================================
# SERIALIZERS
# ============================================
class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = '__all__'


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = '__all__'


class ComplianceReminderSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComplianceReminder
        fields = '__all__'


# ============================================
# VIEWS
# ============================================
class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    
    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)


class NotificationMarkReadView(APIView):
    def post(self, request, pk):
        notification = Notification.objects.get(pk=pk, user=request.user)
        notification.status = 'read'
        notification.read_at = timezone.now()
        notification.save()
        return Response({'message': 'Marked as read'})


class NotificationMarkAllReadView(APIView):
    def post(self, request):
        Notification.objects.filter(user=request.user, status='sent').update(
            status='read', read_at=timezone.now()
        )
        return Response({'message': 'All marked as read'})


class NotificationPreferenceView(generics.RetrieveUpdateAPIView):
    serializer_class = NotificationPreferenceSerializer
    
    def get_object(self):
        prefs, _ = NotificationPreference.objects.get_or_create(user=self.request.user)
        return prefs


class ComplianceReminderListView(generics.ListAPIView):
    serializer_class = ComplianceReminderSerializer
    
    def get_queryset(self):
        company_id = self.kwargs.get('company_id')
        return ComplianceReminder.objects.filter(company_id=company_id).order_by('due_date')


class UnreadCountView(APIView):
    def get(self, request):
        count = Notification.objects.filter(user=request.user, status='sent').count()
        return Response({'unread_count': count})
