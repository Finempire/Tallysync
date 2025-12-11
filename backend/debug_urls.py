import os
import django
from django.conf import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.urls import resolve, reverse
from django.urls.exceptions import Resolver404

print(f"ROOT_URLCONF: {settings.ROOT_URLCONF}")
print(f"PUBLIC_SCHEMA_URLCONF: {settings.PUBLIC_SCHEMA_URLCONF}")

def test_resolve(path):
    try:
        match = resolve(path)
        print(f"Resolved '{path}' to {match.func_name} (view: {match.func})")
    except Resolver404:
        print(f"FAILED to resolve '{path}'")
    except Exception as e:
        print(f"ERROR resolving '{path}': {e}")

test_resolve('/admin-public/')
test_resolve('/admin-root/')
test_resolve('/admin/')
test_resolve('/api/v1/ping-root/')
test_resolve('/api/v1/auth/profile/')
