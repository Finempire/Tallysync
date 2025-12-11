import os
import django
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.bank_statements.models import BankStatement, BankAccount
from apps.companies.models import Ledger

print("--- Checking Bank Accounts Validity ---")

statements = BankStatement.objects.all().order_by('-uploaded_at')
for stmt in statements:
    acct = stmt.bank_account
    print(f"\nStatement ID: {stmt.id} | File: {stmt.original_filename}")
    print(f"  Bank Account ID: {acct.id}")
    print(f"  Bank Name: '{acct.bank_name}'")
    print(f"  Account Number: '{acct.account_number}'")
    print(f"  Linked Tally Ledger: {acct.tally_ledger}")

    if not acct.tally_ledger:
        print("  [!] NOT LINKED TO TALLY LEDGER")
        # Try to find match
        print("  Suggesting matches:")
        exact_match = Ledger.objects.filter(company=acct.company, name__iexact=acct.bank_name).first()
        if exact_match:
            print(f"    [MATCH FOUND] Found exact match: '{exact_match.name}'")
            print("    -> FIXING NOW...")
            acct.tally_ledger = exact_match
            acct.save()
            print("    -> FIXED.")
        else:
            print(f"    [NO EXACT MATCH] for '{acct.bank_name}'")
            # List some bank matching ledgers
            candidates = Ledger.objects.filter(company=acct.company, name__icontains='bank')
            print("    Potential candidates in DB:")
            for c in candidates:
                print(f"      - {c.name}")
    else:
        print(f"  [OK] Linked to: {acct.tally_ledger.name}")
