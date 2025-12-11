"""
Tenant models for multi-tenancy - Phase 1
"""
from django.db import models
from django_tenants.models import TenantMixin, DomainMixin


class Tenant(TenantMixin):
    name = models.CharField(max_length=100)
    created_on = models.DateTimeField(auto_now_add=True)
    paid_until = models.DateField(null=True, blank=True)
    on_trial = models.BooleanField(default=True)
    plan = models.ForeignKey('Plan', on_delete=models.SET_NULL, null=True, blank=True)
    razorpay_customer_id = models.CharField(max_length=100, blank=True)
    razorpay_subscription_id = models.CharField(max_length=100, blank=True)
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=15, blank=True)
    auto_create_schema = True

    def __str__(self):
        return self.name


class Domain(DomainMixin):
    pass


class Plan(models.Model):
    PLAN_CHOICES = [
        ('starter', 'Starter'),
        ('professional', 'Professional'),
        ('business', 'Business'),
        ('enterprise', 'Enterprise'),
    ]
    
    name = models.CharField(max_length=50, choices=PLAN_CHOICES, unique=True)
    display_name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    razorpay_plan_id = models.CharField(max_length=100, blank=True)
    max_companies = models.IntegerField(default=1)
    max_transactions_per_month = models.IntegerField(default=500)
    gst_compliance = models.BooleanField(default=False)
    e_invoicing = models.BooleanField(default=False)
    payroll_module = models.BooleanField(default=False)
    api_access = models.BooleanField(default=False)
    features = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.display_name} - ₹{self.price}"


class Subscription(models.Model):
    STATUS_CHOICES = [('active', 'Active'), ('cancelled', 'Cancelled'), ('expired', 'Expired'), ('pending', 'Pending')]
    
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='subscriptions')
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    razorpay_subscription_id = models.CharField(max_length=100, blank=True)
    current_period_start = models.DateTimeField(null=True)
    current_period_end = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
