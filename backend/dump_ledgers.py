import os
import django
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.companies.models import Ledger

print("--- Dumping All Ledgers ---")
for l in Ledger.objects.all():
    print(f"'{l.name}' (Group: {l.ledger_group})")
