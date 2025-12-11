from apps.tenants.models import Tenant, Domain

# Create Public Tenant
tenant = Tenant(schema_name='public', name='Public Tenant')
tenant.save()

# Create Domain for localhost
domain = Domain()
domain.domain = 'localhost' # or '127.0.0.1'
domain.tenant = tenant
domain.is_primary = True
domain.save()

print("Public tenant 'localhost' created successfully!")
