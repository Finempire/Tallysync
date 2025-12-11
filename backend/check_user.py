import os
import django

# Must be before importing models
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth import get_user_model
from django_tenants.utils import schema_context

User = get_user_model()

from django.contrib.auth import authenticate

def check_user():
    with schema_context('public'):
        users = User.objects.all()
        print(f"Users in public schema: {users.count()}")
        for u in users:
            print(f"Email: {u.email}, Active: {u.is_active}, Password match 'admin': {u.check_password('admin')}")
            
        print("Testing authenticate()...")
        user = authenticate(email='admin@tallysync.com', password='admin')
        if user:
            print(f"Authenticated user: {user.email}")
        else:
            print("Authentication FAILED")

if __name__ == "__main__":
    check_user()
