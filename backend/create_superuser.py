import os
import django
from django.contrib.auth import get_user_model

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django_tenants.utils import schema_context

User = get_user_model()

def create_superuser():
    with schema_context('public'):
        if not User.objects.filter(email='admin@tallysync.com').exists():
            print("Creating superuser...")
            User.objects.create_superuser(
                email='admin@tallysync.com',
                password='admin',
                first_name='Admin',
                last_name='User'
            )
            print("Superuser created.")
        else:
            print("Superuser already exists.")

if __name__ == "__main__":
    create_superuser()
