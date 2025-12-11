"""
Direct Tally Connection Views
Connect directly to Tally from the web without a desktop connector
Works when backend and Tally are on the same machine (local development)
"""
import re
import html
import requests
import xml.etree.ElementTree as ET
from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status


def clean_xml_response(xml_text: str) -> str:
    """
    Clean Tally XML response to handle invalid characters and encoding issues.
    Tally sometimes returns unescaped characters that break XML parsing.
    """
    # Remove invalid XML characters (control characters except tab, newline, carriage return)
    xml_text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', xml_text)
    
    # Remove invalid numeric character references (&#0; through &#31; except &#9; &#10; &#13;)
    # These are control characters that are invalid in XML even as references
    xml_text = re.sub(r'&#([0-8]|1[0-2]|1[4-9]|2[0-9]|3[0-1]);', '', xml_text)
    xml_text = re.sub(r'&#x([0-8]|[bBcC]|[0-1][0-9a-fA-F]);', '', xml_text, flags=re.IGNORECASE)
    
    # Fix common unescaped ampersands (but not already escaped ones)
    xml_text = re.sub(r'&(?!amp;|lt;|gt;|apos;|quot;|#\d+;|#x[0-9a-fA-F]+;)', '&amp;', xml_text)
    
    return xml_text


class TallyDirectConnectionView(APIView):
    """Direct connection to Tally on localhost"""
    permission_classes = [IsAuthenticated]
    
    TALLY_HOST = "localhost"
    TALLY_PORT = 9000
    
    def get_tally_url(self):
        return f"http://{self.TALLY_HOST}:{self.TALLY_PORT}"
    
    def send_to_tally(self, xml_request: str, timeout: int = 30):
        """Send XML request to Tally and return response"""
        try:
            response = requests.post(
                self.get_tally_url(),
                data=xml_request.encode('utf-8'),
                headers={'Content-Type': 'application/xml'},
                timeout=timeout
            )
            return {
                'success': True,
                'status_code': response.status_code,
                'response': response.text
            }
        except requests.Timeout:
            return {'success': False, 'error': 'Tally connection timeout'}
        except requests.ConnectionError:
            return {'success': False, 'error': 'Cannot connect to Tally. Make sure Tally is running with ODBC Server enabled on port 9000.'}
        except Exception as e:
            return {'success': False, 'error': str(e)}


class TallyStatusView(TallyDirectConnectionView):
    """Check if Tally is running and accessible"""
    
    def get(self, request):
        xml_request = """<ENVELOPE>
            <HEADER><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Data</TYPE><ID>List of Companies</ID></HEADER>
            <BODY><DESC><STATICVARIABLES><SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT></STATICVARIABLES></DESC></BODY>
        </ENVELOPE>"""
        
        result = self.send_to_tally(xml_request, timeout=5)
        
        if result['success']:
            return Response({
                'connected': True,
                'message': 'Tally is running and accessible',
                'host': self.TALLY_HOST,
                'port': self.TALLY_PORT
            })
        else:
            return Response({
                'connected': False,
                'message': result.get('error', 'Cannot connect to Tally'),
                'host': self.TALLY_HOST,
                'port': self.TALLY_PORT
            })


class TallyCompaniesView(TallyDirectConnectionView):
    """Get list of companies from Tally"""
    
    def get(self, request):
        # Use TDL Collection format which Tally understands
        xml_request = """<?xml version="1.0" encoding="UTF-8"?>
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Export</TALLYREQUEST>
        <TYPE>Collection</TYPE>
        <ID>ListOfCompanies</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
            </STATICVARIABLES>
            <TDL>
                <TDLMESSAGE>
                    <COLLECTION NAME="ListOfCompanies">
                        <TYPE>Company</TYPE>
                        <FETCH>NAME</FETCH>
                    </COLLECTION>
                </TDLMESSAGE>
            </TDL>
        </DESC>
    </BODY>
</ENVELOPE>"""
        
        result = self.send_to_tally(xml_request)
        
        if not result['success']:
            return Response({'error': result.get('error')}, status=503)
        
        try:
            root = ET.fromstring(clean_xml_response(result['response']))
            companies = []
            
            # Parse company names - Tally returns <COMPANY NAME="CompanyName"><NAME>CompanyName</NAME></COMPANY>
            for company in root.findall('.//COMPANY'):
                # Try NAME attribute first (Tally format)
                name = company.get('NAME')
                if not name:
                    # Fall back to NAME child element
                    name_elem = company.find('NAME')
                    if name_elem is not None:
                        name = name_elem.text
                
                if name:
                    companies.append({'name': name})
            
            return Response({
                'success': True,
                'companies': companies,
                'count': len(companies)
            })
        except ET.ParseError as e:
            return Response({'error': f'Failed to parse Tally response: {e}'}, status=500)


class TallyLedgersView(TallyDirectConnectionView):
    """Get ledgers from Tally for a specific company"""
    
    def get(self, request):
        company_name = request.query_params.get('company', '')
        
        if not company_name:
            return Response({'error': 'Company name is required'}, status=400)
        
        # Use TDL Collection format with proper structure
        xml_request = f"""<?xml version="1.0" encoding="UTF-8"?>
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Export</TALLYREQUEST>
        <TYPE>Collection</TYPE>
        <ID>AllLedgers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVCURRENTCOMPANY>{company_name}</SVCURRENTCOMPANY>
                <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
            </STATICVARIABLES>
            <TDL>
                <TDLMESSAGE>
                    <COLLECTION NAME="AllLedgers">
                        <TYPE>Ledger</TYPE>
                        <FETCH>NAME, PARENT, OPENINGBALANCE, CLOSINGBALANCE</FETCH>
                    </COLLECTION>
                </TDLMESSAGE>
            </TDL>
        </DESC>
    </BODY>
</ENVELOPE>"""
        
        result = self.send_to_tally(xml_request)
        
        if not result['success']:
            return Response({'error': result.get('error')}, status=503)
        
        try:
            root = ET.fromstring(clean_xml_response(result['response']))
            ledgers = []
            
            for ledger in root.findall('.//LEDGER'):
                # Name is in the NAME attribute (e.g., <LEDGER NAME="LedgerName">)
                name = ledger.get('NAME', '')
                
                # Parent and balances are child elements
                parent_elem = ledger.find('PARENT')
                opening_elem = ledger.find('OPENINGBALANCE')
                closing_elem = ledger.find('CLOSINGBALANCE')
                
                parent = parent_elem.text if parent_elem is not None and parent_elem.text else ''
                
                # Parse balance values, handle empty strings
                try:
                    opening = float(opening_elem.text) if opening_elem is not None and opening_elem.text and opening_elem.text.strip() else 0
                except (ValueError, TypeError):
                    opening = 0
                
                try:
                    closing = float(closing_elem.text) if closing_elem is not None and closing_elem.text and closing_elem.text.strip() else 0
                except (ValueError, TypeError):
                    closing = 0
                
                if name:
                    ledgers.append({
                        'name': name,
                        'parent': parent,
                        'opening_balance': opening,
                        'closing_balance': closing,
                    })
            
            return Response({
                'success': True,
                'company': company_name,
                'ledgers': ledgers,
                'count': len(ledgers)
            })
        except ET.ParseError as e:
            return Response({'error': f'Failed to parse Tally response: {e}'}, status=500)


class TallySyncLedgersView(TallyDirectConnectionView):
    """Sync ledgers from Tally to the web app database"""
    
    def post(self, request):
        company_name = request.data.get('company', '')
        
        if not company_name:
            return Response({'error': 'Company name is required'}, status=400)
        
        # Use TDL Collection format with proper structure
        xml_request = f"""<?xml version="1.0" encoding="UTF-8"?>
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Export</TALLYREQUEST>
        <TYPE>Collection</TYPE>
        <ID>AllLedgers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVCURRENTCOMPANY>{company_name}</SVCURRENTCOMPANY>
                <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
            </STATICVARIABLES>
            <TDL>
                <TDLMESSAGE>
                    <COLLECTION NAME="AllLedgers">
                        <TYPE>Ledger</TYPE>
                        <FETCH>NAME, PARENT, OPENINGBALANCE, CLOSINGBALANCE, GUID</FETCH>
                    </COLLECTION>
                </TDLMESSAGE>
            </TDL>
        </DESC>
    </BODY>
</ENVELOPE>"""
        
        result = self.send_to_tally(xml_request)
        
        if not result['success']:
            return Response({'error': result.get('error')}, status=503)
        
        try:
            root = ET.fromstring(clean_xml_response(result['response']))
            synced_count = 0
            errors = []
            
            # Import models here to avoid circular imports
            from apps.companies.models import Company
            from apps.tally_connector.models import TallyMaster
            
            # Get or create the company in our database
            company = Company.objects.first()  # For local dev, use first company
            if not company:
                return Response({'error': 'No company found in database'}, status=400)
            
            for ledger in root.findall('.//LEDGER'):
                try:
                    # Name is in the NAME attribute (e.g., <LEDGER NAME="LedgerName">)
                    name = ledger.get('NAME', '')
                    
                    # Parent, balance, and guid are child elements
                    parent_elem = ledger.find('PARENT')
                    opening_elem = ledger.find('OPENINGBALANCE')
                    guid_elem = ledger.find('GUID')
                    
                    parent = parent_elem.text if parent_elem is not None and parent_elem.text else ''
                    guid = guid_elem.text if guid_elem is not None and guid_elem.text else ''
                    
                    # Parse opening balance
                    try:
                        opening = float(opening_elem.text) if opening_elem is not None and opening_elem.text and opening_elem.text.strip() else 0
                    except (ValueError, TypeError):
                        opening = 0
                    
                    if name:
                        TallyMaster.objects.update_or_create(
                            company=company,
                            master_type='ledger',
                            name=name,
                            defaults={
                                'tally_guid': guid,
                                'data': {
                                    'parent': parent,
                                    'opening_balance': opening,
                                }
                            }
                        )
                        synced_count += 1
                except Exception as e:
                    errors.append(str(e))
            
            return Response({
                'success': True,
                'synced_count': synced_count,
                'errors': errors,
                'message': f'Successfully synced {synced_count} ledgers from Tally'
            })
        except ET.ParseError as e:
            return Response({'error': f'Failed to parse Tally response: {e}'}, status=500)


class TallyVoucherTypesView(TallyDirectConnectionView):
    """Get voucher types from Tally"""
    
    def get(self, request):
        company_name = request.query_params.get('company', '')
        
        if not company_name:
            return Response({'error': 'Company name is required'}, status=400)
        
        xml_request = f"""<ENVELOPE>
            <HEADER><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Collection</TYPE><ID>All Voucher Types</ID></HEADER>
            <BODY>
                <DESC>
                    <STATICVARIABLES>
                        <SVCURRENTCOMPANY>{company_name}</SVCURRENTCOMPANY>
                        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
                    </STATICVARIABLES>
                    <TDL>
                        <TDLMESSAGE>
                            <COLLECTION NAME="All Voucher Types">
                                <TYPE>VoucherType</TYPE>
                                <FETCH>NAME, PARENT</FETCH>
                            </COLLECTION>
                        </TDLMESSAGE>
                    </TDL>
                </DESC>
            </BODY>
        </ENVELOPE>"""
        
        result = self.send_to_tally(xml_request)
        
        if not result['success']:
            return Response({'error': result.get('error')}, status=503)
        
        try:
            root = ET.fromstring(clean_xml_response(result['response']))
            voucher_types = []
            
            for vtype in root.findall('.//VOUCHERTYPE'):
                name = vtype.find('NAME')
                parent = vtype.find('PARENT')
                
                voucher_types.append({
                    'name': name.text if name is not None else '',
                    'parent': parent.text if parent is not None else '',
                })
            
            return Response({
                'success': True,
                'company': company_name,
                'voucher_types': voucher_types,
                'count': len(voucher_types)
            })
        except ET.ParseError as e:
            return Response({'error': f'Failed to parse Tally response: {e}'}, status=500)
