import os
import django
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.bank_statements.models import ParsedTransaction
from django.db.models import F

print("--- Fixing Broken Transactions ---")

# 1. identifying broken approved transactions (approved but no mapped_ledger)
broken = ParsedTransaction.objects.filter(status='approved', mapped_ledger__isnull=True)
count = broken.count()
print(f"Found {count} broken 'approved' transactions (missing mapped_ledger).")

if count > 0:
    print("Reverting them to 'pending' status so they can be re-mapped...")
    # Try to recover from suggested_ledger if present
    recoverable = broken.filter(suggested_ledger__isnull=False)
    rec_count = recoverable.count()
    
    if rec_count > 0:
        print(f"  -> {rec_count} can be recovered from suggestions. Restoring ledger link...")
        recoverable.update(mapped_ledger=F('suggested_ledger'))
        print("  -> Done.")
        
    # The rest (truly empty) go to pending
    still_broken = ParsedTransaction.objects.filter(status='approved', mapped_ledger__isnull=True)
    sb_count = still_broken.count()
    if sb_count > 0:
        print(f"  -> {sb_count} cannot be recovered. Resetting to 'pending'...")
        still_broken.update(status='pending')
        print("  -> Done.")

# 2. fixing auto_mapped ones just in case
broken_auto = ParsedTransaction.objects.filter(status='auto_mapped', mapped_ledger__isnull=True, suggested_ledger__isnull=False)
if broken_auto.exists():
    print(f"Found {broken_auto.count()} broken 'auto_mapped' transactions. Fixing...")
    broken_auto.update(mapped_ledger=F('suggested_ledger'))
    print("-> Done.")

print("\nAll fixed. Please refresh the page and try again.")
