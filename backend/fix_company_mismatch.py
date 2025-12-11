import os
import django
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.bank_statements.models import BankStatement, BankAccount
from apps.companies.models import Ledger, Company

print("--- Checking Companies ---")
for c in Company.objects.all():
    print(f"ID: {c.id} | Name: '{c.name}'")

print("\n--- Checking Bank Accounts Validity ---")

statements = BankStatement.objects.all().order_by('-uploaded_at')
for stmt in statements:
    acct = stmt.bank_account
    print(f"\nStatement ID: {stmt.id} | File: {stmt.original_filename}")
    print(f"  Current Company ID: {acct.company.id} ({acct.company.name})")
    print(f"  Bank Account: '{acct.bank_name}' (ID: {acct.id})")

    if not acct.tally_ledger:
        print("  [!] NOT LINKED TO TALLY LEDGER")
        
        # Check all companies for this ledger
        print("  Searching for ledger in ALL companies:")
        matches = Ledger.objects.filter(name__iexact=acct.bank_name)
        if matches.exists():
            for m in matches:
                print(f"    [FOUND] in Company {m.company.id} ({m.company.name}) -> Ledger ID: {m.id}")
                
            # AUTO FIX if only one match or obvious choice
            # We move the BankAccount to the correct company if needed
            correct_ledger = matches.first()
            if correct_ledger.company.id != acct.company.id:
                print(f"    -> MISMATCH DETECTED! Account is in Co {acct.company.id}, Ledger is in Co {correct_ledger.company.id}")
                print("    -> MOVING BANK ACCOUNT TO CORRECT COMPANY...")
                acct.company = correct_ledger.company
                acct.tally_ledger = correct_ledger
                acct.save()
                print("    -> FIXED.")
            else:
                print(f"    -> Same company, just linking...")
                acct.tally_ledger = correct_ledger
                acct.save()
                print("    -> FIXED.")
        else:
            print(f"    [NO MATCH FOUND GLOBALLY] for '{acct.bank_name}'")
