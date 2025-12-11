import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.tenants.models import Tenant, Domain

def create_public_tenant():
    if Tenant.objects.filter(schema_name='public').exists():
        print("Public Tenant already exists.")
        tenant = Tenant.objects.get(schema_name='public')
    else:
        print("Creating Public Tenant...")
        tenant = Tenant(
            schema_name='public',
            name='Public Tenant',
            on_trial=False
        )
        tenant.save()
        print("Public Tenant created.")

    if Domain.objects.filter(domain='localhost').exists():
        print("Domain 'localhost' already exists.")
    else:
        print("Creating Domain 'localhost'...")
        domain = Domain(
            domain='localhost',
            tenant=tenant,
            is_primary=True
        )
        domain.save()
        print("Domain 'localhost' created.")

if __name__ == "__main__":
    create_public_tenant()
