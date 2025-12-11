import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.companies.models import Company
from apps.users.models import User
from django_tenants.utils import schema_context

def check_company():
    with schema_context('public'):
        if Company.objects.filter(id=1).exists():
            print("Company ID 1 exists.")
            c = Company.objects.get(id=1)
            print(f"Company: {c.name}")
        else:
            print("Company ID 1 MISSING. Creating it...")
            try:
                user = User.objects.get(email='admin@tallysync.com')
                c = Company.objects.create(name="Demo Company", owner=user)
                print(f"Created Company ID {c.id}: {c.name}")
            except Exception as e:
                print(f"Error creating company: {e}")

if __name__ == "__main__":
    check_company()
