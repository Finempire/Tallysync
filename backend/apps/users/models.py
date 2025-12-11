"""
Users App - Complete Implementation
Models, Serializers, Views for Authentication & User Management
"""
from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from rest_framework import serializers, generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
import secrets


# ============================================
# MODELS
# ============================================
class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'admin')
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    ROLE_CHOICES = [
        ('admin', 'Administrator'),
        ('accountant', 'Accountant'),
        ('viewer', 'Viewer'),
        ('data_entry', 'Data Entry Operator'),
    ]
    
    username = None
    email = models.EmailField('Email Address', unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='viewer')
    phone = models.CharField(max_length=15, blank=True, null=True)
    designation = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    email_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = UserManager()
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.email

    def has_permission(self, permission):
        permissions_map = {
            'admin': ['all'],
            'accountant': ['view', 'create', 'edit', 'approve', 'sync_tally'],
            'data_entry': ['view', 'create', 'edit'],
            'viewer': ['view'],
        }
        user_permissions = permissions_map.get(self.role, [])
        return 'all' in user_permissions or permission in user_permissions


class UserInvitation(models.Model):
    email = models.EmailField()
    role = models.CharField(max_length=20, choices=User.ROLE_CHOICES, default='viewer')
    invited_by = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=20, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()


# ============================================
# SERIALIZERS
# ============================================
class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField()
    
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'full_name', 'role', 'phone', 'designation', 'is_active', 'created_at']
        read_only_fields = ['id', 'email', 'created_at']


class UserRegistrationSerializer(serializers.Serializer):
    tenant_name = serializers.CharField(max_length=100)
    subdomain = serializers.CharField(max_length=50)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    first_name = serializers.CharField(max_length=150, required=False)
    last_name = serializers.CharField(max_length=150, required=False)
    phone = serializers.CharField(max_length=15, required=False)

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password": "Passwords don't match"})
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(required=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({"new_password": "Passwords don't match"})
        return attrs


# ============================================
# VIEWS
# ============================================
class RegisterTenantView(APIView):
    permission_classes = [AllowAny]
    
    @transaction.atomic
    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        
        from apps.tenants.models import Tenant, Domain
        
        tenant = Tenant.objects.create(
            name=data['tenant_name'],
            schema_name=data['subdomain'],
            email=data['email'],
            on_trial=True,
            paid_until=timezone.now().date() + timedelta(days=14)
        )
        
        Domain.objects.create(
            domain=f"{data['subdomain']}.localhost",
            tenant=tenant,
            is_primary=True
        )
        
        from django.db import connection
        connection.set_tenant(tenant)
        
        user = User.objects.create(
            email=data['email'],
            first_name=data.get('first_name', ''),
            last_name=data.get('last_name', ''),
            role='admin',
            is_active=True
        )
        user.set_password(data['password'])
        user.save()
        
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'message': 'Registration successful',
            'tenant': {'id': str(tenant.id), 'name': tenant.name, 'subdomain': data['subdomain']},
            'user': UserSerializer(user).data,
            'tokens': {'refresh': str(refresh), 'access': str(refresh.access_token)}
        }, status=status.HTTP_201_CREATED)


class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    
    def get_object(self):
        return self.request.user


class ChangePasswordView(APIView):
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        if not request.user.check_password(serializer.validated_data['old_password']):
            return Response({'old_password': 'Wrong password'}, status=status.HTTP_400_BAD_REQUEST)
        
        request.user.set_password(serializer.validated_data['new_password'])
        request.user.save()
        return Response({'message': 'Password changed successfully'})


class UserListView(generics.ListCreateAPIView):
    serializer_class = UserSerializer
    
    def get_queryset(self):
        return User.objects.filter(is_active=True)


class InviteUserView(APIView):
    def post(self, request):
        if request.user.role != 'admin':
            return Response({'error': 'Only admins can invite users'}, status=status.HTTP_403_FORBIDDEN)
        
        invitation = UserInvitation.objects.create(
            email=request.data.get('email'),
            role=request.data.get('role', 'viewer'),
            invited_by=request.user,
            token=secrets.token_urlsafe(32),
            expires_at=timezone.now() + timedelta(days=7)
        )
        return Response({'message': f"Invitation sent to {invitation.email}"})
