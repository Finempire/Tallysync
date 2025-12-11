"""
Management command to create a desktop connector and generate API key
"""
from django.core.management.base import BaseCommand
from apps.tally_connector.models import DesktopConnector
from apps.companies.models import Company
import secrets


class Command(BaseCommand):
    help = 'Create a desktop connector for Tally integration'

    def add_arguments(self, parser):
        parser.add_argument('--company', type=str, help='Company name (optional)')
        parser.add_argument('--name', type=str, default='Local Connector', help='Connector name')

    def handle(self, *args, **options):
        # Get or create a company
        company_name = options.get('company')
        
        if company_name:
            company = Company.objects.filter(name=company_name).first()
        else:
            company = Company.objects.first()
        
        if not company:
            self.stdout.write(self.style.ERROR('No company found. Please create a company first.'))
            return
        
        # Create connector
        connector_name = options.get('name', 'Local Connector')
        api_key = secrets.token_urlsafe(32)
        
        connector, created = DesktopConnector.objects.get_or_create(
            company=company,
            name=connector_name,
            defaults={
                'api_key': api_key,
                'status': 'inactive'
            }
        )
        
        if not created:
            # Update API key for existing connector
            connector.api_key = api_key
            connector.save()
            self.stdout.write(self.style.WARNING(f'Updated existing connector: {connector_name}'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Created new connector: {connector_name}'))
        
        self.stdout.write('')
        self.stdout.write('=' * 60)
        self.stdout.write(self.style.SUCCESS('TALLY CONNECTOR API KEY'))
        self.stdout.write('=' * 60)
        self.stdout.write(f'Company: {company.name}')
        self.stdout.write(f'Connector: {connector.name}')
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'API Key: {connector.api_key}'))
        self.stdout.write('')
        self.stdout.write('Copy this API key and paste it in the TallySync Connector application.')
        self.stdout.write('=' * 60)
