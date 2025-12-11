
import pandas as pd
from io import BytesIO
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.db import transaction
from django.utils import timezone
from .models import Voucher, VoucherSettings

class VoucherImportView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    @transaction.atomic
    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return Response({'error': 'File is required'}, status=400)
            
        company_id = request.data.get('company_id')
        transaction_type = request.data.get('transaction_type', 'sales') # default to sales
        default_ledger_id = request.data.get('default_ledger_id')
        tax_ledger_ids = request.data.get('tax_ledger_ids', '') # comma separated
        
        # Update/Create Default Settings if ledgers provided
        if default_ledger_id or tax_ledger_ids:
            try:
                settings, created = VoucherSettings.objects.get_or_create(
                    company_id=company_id, 
                    transaction_type=transaction_type
                )
                if default_ledger_id:
                    if transaction_type == 'sales': settings.default_sales_ledger_id = default_ledger_id
                    elif transaction_type == 'purchase': settings.default_purchase_ledger_id = default_ledger_id
                
                if tax_ledger_ids:
                    # For MVP, assume tax_ledger_ids might contain specific CGST/SGST/IGST mapping logic
                    # But if user selects multiple, we might just set them generally?
                    # Since VoucherSettings has specific fields (default_cgst_ledger etc.), mapping 'generic' tax ledgers is hard.
                    # Ideally, the user should set "CGST", "SGST" specifically.
                    # But the modal has one "Tax Ledger" multi-select.
                    # Let's verify standard behavior: User selects "Output CGST 9%", "Output SGST 9%".
                    # We can try to guess which is which by name matching 'CGST', 'SGST' etc.
                    
                    ids = [int(x) for x in str(tax_ledger_ids).split(',') if x.strip()]
                    from apps.companies.models import Ledger
                    ledgers = Ledger.objects.filter(id__in=ids)
                    
                    for l in ledgers:
                        lname = l.name.upper()
                        if 'CGST' in lname: settings.default_cgst_ledger = l
                        elif 'SGST' in lname: settings.default_sgst_ledger = l
                        elif 'IGST' in lname: settings.default_igst_ledger = l
                        elif 'CESS' in lname: settings.default_cess_ledger = l
                        
                settings.save()
            except Exception as e:
                print(f"Error saving settings: {e}")
                pass # Non-critical for import itself, but good for persistence

        # For MVP, let's parse columns
        try:
            df = None
            if file.name.endswith('.xlsx') or file.name.endswith('.xls'):
                df = pd.read_excel(file)
            elif file.name.endswith('.csv'):
                df = pd.read_csv(file)
            else:
                return Response({'error': 'Unsupported file format'}, status=400)
            
            # Basic Column Helper
            # We look for: Date, Voucher No, Party Name, Amount, Narration, Tax Columns (CGST, SGST, IGST)
            
            def get_col(candidates):
                for col in df.columns:
                    if str(col).lower().strip() in candidates:
                        return col
                return None
                
            col_date = get_col(['date', 'invoice date', 'voucher date', 'txn date'])
            col_no = get_col(['voucher number', 'voucher no', 'invoice no', 'invoice number', 'ref no'])
            col_party = get_col(['party name', 'customer name', 'vendor name', 'ledger name', 'party'])
            col_amount = get_col(['amount', 'total amount', 'invoice amount', 'grand total'])
            col_narration = get_col(['narration', 'description', 'remarks', 'particulars'])
            
            # Tax columns
            col_cgst = get_col(['cgst', 'cgst amount', 'output cgst', 'input cgst'])
            col_sgst = get_col(['sgst', 'sgst amount', 'output sgst', 'input sgst'])
            col_igst = get_col(['igst', 'igst amount', 'output igst', 'input igst'])
            col_cess = get_col(['cess', 'cess amount'])

            if not col_date or not col_party or not col_amount:
                 return Response({
                     'error': f'Missing critical columns. Found: {list(df.columns)}. Expected Date, Party Name, Amount.'
                 }, status=400)

            created_vouchers = []
            
            for index, row in df.iterrows():
                # Parse Date
                date_val = row[col_date]
                # Try simple parsing
                try:
                    date_obj = pd.to_datetime(date_val).date()
                except:
                    continue # Skip invalid date rows
                
                # Parse Amount
                try:
                    amount = float(str(row[col_amount]).replace(',', '').strip())
                except:
                    continue
                    
                gst_details = {
                    'cgst': float(str(row[col_cgst]).replace(',', '')) if col_cgst and pd.notna(row[col_cgst]) else 0,
                    'sgst': float(str(row[col_sgst]).replace(',', '')) if col_sgst and pd.notna(row[col_sgst]) else 0,
                    'igst': float(str(row[col_igst]).replace(',', '')) if col_igst and pd.notna(row[col_igst]) else 0,
                    'cess': float(str(row[col_cess]).replace(',', '')) if col_cess and pd.notna(row[col_cess]) else 0,
                }
                
                voucher = Voucher.objects.create(
                    company_id=company_id,
                    voucher_type=transaction_type,
                    date=date_obj,
                    voucher_number=str(row[col_no]) if col_no and pd.notna(row[col_no]) else '',
                    party_name=str(row[col_party]).strip(),
                    # party_ledger will be mapped later
                    amount=amount,
                    narration=str(row[col_narration]) if col_narration and pd.notna(row[col_narration]) else '',
                    gst_details=gst_details,
                    status='draft',
                    verification_status='unverified',
                    source='import',
                    created_by=request.user
                )
                created_vouchers.append(voucher)
                
            return Response({'message': f'Successfully imported {len(created_vouchers)} vouchers'}, status=201)
            
        except Exception as e:
            return Response({'error': str(e)}, status=500)

from django.http import HttpResponse

class VoucherTemplateView(APIView):
    def get(self, request):
        voucher_type = request.query_params.get('type', 'sales')
        
        # Create a sample DataFrame based on type
        # For now, fields are mostly same but we can customize headers if needed
        data = {
            'Date': ['2023-04-01'],
            'Voucher No': ['INV-001'],
            'Party Name': ['Sample Party'], # Generic name
            'Amount': [1180.00],
            'CGST': [90.00],
            'SGST': [90.00],
            'IGST': [0.00],
            'Cess': [0.00],
            'Narration': [f'Being {voucher_type} made']
        }
        df = pd.DataFrame(data)
        
        output = BytesIO()
        writer = pd.ExcelWriter(output, engine='openpyxl')
        df.to_excel(writer, index=False, sheet_name='Sheet1')
        writer.close()
        output.seek(0)
        
        response = HttpResponse(output.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename={voucher_type}_template.xlsx'
        return response
