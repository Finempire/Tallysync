import os
import django
import sys
import traceback

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.reports.models import AnalyticsEngine

def debug_engine():
    try:
        print("Initializing AnalyticsEngine for Company ID 1...")
        engine = AnalyticsEngine(company_id=1)
        print("Calling get_dashboard_stats()...")
        stats = engine.get_dashboard_stats()
        print("Success!")
        print(stats)
    except Exception:
        print("Crash detected!")
        traceback.print_exc()

if __name__ == "__main__":
    debug_engine()
