import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.tenants.models import Tenant, Domain

def add_domain():
    try:
        tenant = Tenant.objects.get(schema_name='public')
        if not Domain.objects.filter(domain='127.0.0.1').exists():
            print("Adding 127.0.0.1 domain...")
            Domain.objects.create(
                domain='127.0.0.1',
                tenant=tenant,
                is_primary=False
            )
            print("Domain 127.0.0.1 added.")
        else:
            print("Domain 127.0.0.1 already exists.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    add_domain()
