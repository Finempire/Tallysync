"""
Sales Import Workflow - Views
Complete API for multi-step sales voucher import workflow
"""
import pandas as pd
from io import BytesIO
from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.db import transaction, models
from django.utils import timezone
import numpy as np

from .sales_import_models import SalesImport, SalesImportRow
from .sales_import_serializers import (
    SalesImportSerializer, SalesImportDetailSerializer,
    SalesImportRowSerializer, SalesImportRowUpdateSerializer
)
from apps.companies.models import Ledger, StockItem


def convert_to_json_safe(obj):
    """Convert pandas/numpy types to JSON-serializable Python types"""
    if isinstance(obj, dict):
        return {k: convert_to_json_safe(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_json_safe(v) for v in obj]
    elif isinstance(obj, pd.Timestamp):
        return obj.strftime('%d-%m-%Y') if pd.notna(obj) else ''
    elif isinstance(obj, (np.integer, np.floating)):
        return obj.item()
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif pd.isna(obj):
        return ''
    else:
        return obj


class SalesImportUploadView(APIView):
    """Step 1: Upload file, parse columns, create import session"""
    parser_classes = [MultiPartParser, FormParser]
    
    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return Response({'error': 'File is required'}, status=400)
        
        company_id = request.data.get('company_id')
        import_type = request.data.get('import_type', 'without_item')
        voucher_type = request.data.get('voucher_type', 'sales')
        
        if not company_id:
            return Response({'error': 'Company ID is required'}, status=400)
        
        try:
            # Parse file to detect columns
            df = None
            filename = file.name
            
            if filename.endswith('.xlsx') or filename.endswith('.xls'):
                df = pd.read_excel(file)
            elif filename.endswith('.csv'):
                file.seek(0)
                df = pd.read_csv(file)
            else:
                return Response({'error': 'Unsupported file format. Use Excel or CSV.'}, status=400)
            
            if df.empty:
                return Response({'error': 'File is empty'}, status=400)
            
            # Get column names and sample data
            columns = df.columns.tolist()
            # Convert timestamps and numpy types to JSON-safe formats (DD-MM-YYYY for dates)
            sample_data = convert_to_json_safe(df.head(5).fillna('').to_dict('records'))
            total_rows = len(df)
            
            # Save file and create import record
            file.seek(0)
            
            sales_import = SalesImport.objects.create(
                company_id=company_id,
                import_type=import_type,
                voucher_type=voucher_type,
                original_file=file,
                original_filename=filename,
                detected_columns=columns,
                sample_data=sample_data,
                total_rows=total_rows,
                status='columns_detected',
                created_by=request.user
            )
            
            # Create row entries for each data row
            rows_to_create = []
            for idx, row in df.iterrows():
                rows_to_create.append(SalesImportRow(
                    sales_import=sales_import,
                    row_number=idx + 1,
                    raw_data=convert_to_json_safe(row.fillna('').to_dict())
                ))
            SalesImportRow.objects.bulk_create(rows_to_create)
            
            return Response({
                'id': sales_import.id,
                'columns': columns,
                'sample_data': sample_data,
                'total_rows': total_rows,
                'import_type': import_type,
                'status': 'columns_detected'
            }, status=201)
            
        except Exception as e:
            return Response({'error': str(e)}, status=500)


class SalesImportDetailView(generics.RetrieveAPIView):
    """Get details of an import session"""
    serializer_class = SalesImportDetailSerializer
    queryset = SalesImport.objects.all()


class SalesImportFieldMappingView(APIView):
    """Step 2: Save column → field mapping"""
    
    def get(self, request, pk):
        """Get current mapping and available fields"""
        sales_import = SalesImport.objects.get(pk=pk)
        
        # Define available Tally fields based on import type
        if sales_import.import_type == 'without_item':
            available_fields = [
                {'key': 'reference_no', 'label': 'Reference No / Invoice No', 'required': False},
                {'key': 'date', 'label': 'Invoice Date', 'required': True},
                {'key': 'party_name', 'label': 'Party Name / Customer', 'required': True},
                {'key': 'sales_ledger', 'label': 'Sales Ledger', 'required': False},
                {'key': 'amount', 'label': 'Taxable Amount', 'required': True},
                {'key': 'total_amount', 'label': 'Total Amount (incl. tax)', 'required': False},
                {'key': 'gst_no', 'label': 'GST Number', 'required': False},
                {'key': 'place_of_supply', 'label': 'Place of Supply', 'required': False},
                {'key': 'cgst', 'label': 'CGST Amount', 'required': False},
                {'key': 'sgst', 'label': 'SGST Amount', 'required': False},
                {'key': 'igst', 'label': 'IGST Amount', 'required': False},
                {'key': 'cess', 'label': 'Cess Amount', 'required': False},
                {'key': 'narration', 'label': 'Narration / Remarks', 'required': False},
                {'key': 'voucher_number', 'label': 'Voucher Number', 'required': False},
            ]
        else:  # with_item
            available_fields = [
                {'key': 'reference_no', 'label': 'Reference No / Invoice No', 'required': False},
                {'key': 'date', 'label': 'Invoice Date', 'required': True},
                {'key': 'party_name', 'label': 'Party Name / Customer', 'required': True},
                {'key': 'sales_ledger', 'label': 'Sales Ledger', 'required': False},
                {'key': 'item_name', 'label': 'Item Name / Product', 'required': True},
                {'key': 'quantity', 'label': 'Quantity', 'required': True},
                {'key': 'rate', 'label': 'Rate / Unit Price', 'required': False},
                {'key': 'amount', 'label': 'Amount', 'required': True},
                {'key': 'unit', 'label': 'Unit (UOM)', 'required': False},
                {'key': 'hsn_code', 'label': 'HSN Code', 'required': False},
                {'key': 'gst_rate', 'label': 'GST Rate %', 'required': False},
                {'key': 'discount', 'label': 'Discount', 'required': False},
                {'key': 'gst_no', 'label': 'GST Number', 'required': False},
                {'key': 'place_of_supply', 'label': 'Place of Supply', 'required': False},
                {'key': 'cgst', 'label': 'CGST Amount', 'required': False},
                {'key': 'sgst', 'label': 'SGST Amount', 'required': False},
                {'key': 'igst', 'label': 'IGST Amount', 'required': False},
                {'key': 'narration', 'label': 'Narration / Remarks', 'required': False},
            ]
        
        return Response({
            'detected_columns': sales_import.detected_columns,
            'sample_data': sales_import.sample_data,
            'available_fields': available_fields,
            'current_mapping': sales_import.column_mapping,
            'import_type': sales_import.import_type
        })
    
    def post(self, request, pk):
        """Save field mapping"""
        sales_import = SalesImport.objects.get(pk=pk)
        mapping = request.data.get('mapping', {})
        
        if not mapping:
            return Response({'error': 'Mapping is required'}, status=400)
        
        sales_import.column_mapping = mapping
        sales_import.status = 'field_mapped'
        sales_import.save()
        
        # Apply mapping to all rows
        self._apply_mapping_to_rows(sales_import, mapping)
        
        return Response({
            'message': 'Field mapping saved',
            'status': sales_import.status
        })
    
    def _apply_mapping_to_rows(self, sales_import, mapping):
        """Apply column mapping to all rows"""
        # Invert mapping: {excel_col: tally_field} to enable lookup
        for row in sales_import.rows.all():
            mapped_data = {}
            for excel_col, tally_field in mapping.items():
                if tally_field and excel_col in row.raw_data:
                    mapped_data[tally_field] = row.raw_data[excel_col]
            row.mapped_data = mapped_data
            row.save()


class SalesImportPreviewView(APIView):
    """Preview mapped data before proceeding"""
    
    def get(self, request, pk):
        sales_import = SalesImport.objects.get(pk=pk)
        rows = sales_import.rows.all()[:20]  # First 20 rows
        
        return Response({
            'total_rows': sales_import.total_rows,
            'preview_rows': SalesImportRowSerializer(rows, many=True).data,
            'column_mapping': sales_import.column_mapping
        })


class SalesImportGSTConfigView(APIView):
    """Step 3: Configure GST calculation settings"""
    
    def get(self, request, pk):
        sales_import = SalesImport.objects.get(pk=pk)
        
        # Get available tax ledgers from company - include synced status
        # First get synced ledgers (they should be prioritized)
        tax_ledgers_qs = Ledger.objects.filter(
            company_id=sales_import.company_id,
            is_active=True
        ).filter(
            models.Q(parent_group__icontains='duties') |
            models.Q(parent_group__icontains='tax') |
            models.Q(name__icontains='gst') |
            models.Q(name__icontains='tax') |
            models.Q(name__icontains='cgst') |
            models.Q(name__icontains='sgst') |
            models.Q(name__icontains='igst') |
            models.Q(name__icontains='cess')
        ).order_by('-synced_from_tally', 'name')  # Synced first, then alphabetically
        
        tax_ledgers = list(tax_ledgers_qs.values('id', 'name', 'parent_group', 'synced_from_tally'))
        
        return Response({
            'current_config': sales_import.gst_config,
            'tax_ledgers': tax_ledgers,
            'gst_options': [
                {'key': 'auto_calculate', 'label': 'Auto-calculate GST (Suvit/Tally calculates)'},
                {'key': 'from_excel', 'label': 'Take GST values from Excel columns'},
                {'key': 'no_gst', 'label': 'No GST applicable'}
            ]
        })
    
    def post(self, request, pk):
        sales_import = SalesImport.objects.get(pk=pk)
        config = request.data.get('config', {})
        
        sales_import.gst_config = config
        sales_import.status = 'gst_configured'
        sales_import.save()
        
        return Response({
            'message': 'GST configuration saved',
            'status': sales_import.status
        })


class SalesImportLedgerMappingView(APIView):
    """Step 4: Map additional ledgers (freight, discount, etc.)"""
    
    def get(self, request, pk):
        sales_import = SalesImport.objects.get(pk=pk)
        
        # Get all ledgers for additional mapping - include synced status
        ledgers_qs = Ledger.objects.filter(
            company_id=sales_import.company_id,
            is_active=True
        ).order_by('-synced_from_tally', 'name')  # Synced first, then alphabetically
        
        ledgers = list(ledgers_qs.values('id', 'name', 'parent_group', 'ledger_group', 'synced_from_tally'))
        
        # Suggest unmapped columns
        mapped_cols = set(sales_import.column_mapping.keys())
        unmapped_cols = [c for c in sales_import.detected_columns if c not in mapped_cols]
        
        return Response({
            'unmapped_columns': unmapped_cols,
            'current_mapping': sales_import.ledger_mapping,
            'available_ledgers': ledgers,
            'suggested_mappings': [
                {'column_hint': 'freight', 'ledger_type': 'Freight / Transport'},
                {'column_hint': 'discount', 'ledger_type': 'Discount'},
                {'column_hint': 'round', 'ledger_type': 'Round Off'},
                {'column_hint': 'other', 'ledger_type': 'Other Charges'}
            ]
        })
    
    def post(self, request, pk):
        sales_import = SalesImport.objects.get(pk=pk)
        mapping = request.data.get('mapping', {})
        
        sales_import.ledger_mapping = mapping
        sales_import.status = 'ledger_mapped'
        sales_import.save()
        
        return Response({
            'message': 'Ledger mapping saved',
            'status': sales_import.status
        })


class SalesImportRowsView(APIView):
    """Step 5: Get all rows with validation status for processing screen"""
    
    def get(self, request, pk):
        sales_import = SalesImport.objects.get(pk=pk)
        
        # Validate all rows first
        self._validate_all_rows(sales_import)
        
        # Get filter params
        status_filter = request.query_params.get('status')
        
        rows = sales_import.rows.all()
        if status_filter:
            rows = rows.filter(validation_status=status_filter)
        
        # Update stats
        sales_import.valid_rows = sales_import.rows.filter(validation_status='valid').count()
        sales_import.warning_rows = sales_import.rows.filter(validation_status='warning').count()
        sales_import.error_rows = sales_import.rows.filter(validation_status='error').count()
        sales_import.status = 'processing'
        sales_import.save()
        
        return Response({
            'total_rows': sales_import.total_rows,
            'stats': {
                'valid': sales_import.valid_rows,
                'warning': sales_import.warning_rows,
                'error': sales_import.error_rows,
                'processed': sales_import.processed_rows,
                'synced': sales_import.synced_rows
            },
            'rows': SalesImportRowSerializer(rows, many=True).data
        })
    
    def _validate_all_rows(self, sales_import):
        """Validate all rows and try to resolve references"""
        from apps.companies.models import Ledger
        
        for row in sales_import.rows.filter(validation_status='pending'):
            mapped = row.mapped_data
            
            # Try to find party ledger
            party_name = mapped.get('party_name', '')
            if party_name and not row.party_ledger:
                # Exact match first
                ledger = Ledger.objects.filter(
                    company_id=sales_import.company_id,
                    name__iexact=party_name
                ).first()
                
                if not ledger:
                    # Fuzzy match
                    ledger = Ledger.objects.filter(
                        company_id=sales_import.company_id,
                        name__icontains=party_name
                    ).first()
                
                if ledger:
                    row.party_ledger = ledger
                    row.save()
            
            row.validate_row()


class SalesImportRowDetailView(APIView):
    """Update individual row"""
    
    def patch(self, request, pk, row_id):
        row = SalesImportRow.objects.get(pk=row_id, sales_import_id=pk)
        
        # Update mapped data
        if 'mapped_data' in request.data:
            row.mapped_data.update(request.data['mapped_data'])
        
        # Update party ledger
        if 'party_ledger_id' in request.data:
            row.party_ledger_id = request.data['party_ledger_id']
        
        # Update sales ledger
        if 'sales_ledger_id' in request.data:
            row.sales_ledger_id = request.data['sales_ledger_id']
        
        row.save()
        
        # Re-validate
        row.validate_row()
        
        return Response(SalesImportRowSerializer(row).data)


class SalesImportBulkUpdateView(APIView):
    """Bulk update multiple rows"""
    
    @transaction.atomic
    def post(self, request, pk):
        sales_import = SalesImport.objects.get(pk=pk)
        row_ids = request.data.get('row_ids', [])
        updates = request.data.get('updates', {})
        
        if not row_ids:
            return Response({'error': 'No rows selected'}, status=400)
        
        rows = sales_import.rows.filter(id__in=row_ids)
        updated_count = 0
        
        for row in rows:
            if 'party_ledger_id' in updates:
                row.party_ledger_id = updates['party_ledger_id']
            if 'sales_ledger_id' in updates:
                row.sales_ledger_id = updates['sales_ledger_id']
            if 'mapped_data' in updates:
                row.mapped_data.update(updates['mapped_data'])
            row.save()
            row.validate_row()
            updated_count += 1
        
        return Response({
            'message': f'{updated_count} rows updated',
            'updated_count': updated_count
        })


class SalesImportCreatePartyView(APIView):
    """Create missing party ledger on-the-fly"""
    
    @transaction.atomic
    def post(self, request, pk):
        sales_import = SalesImport.objects.get(pk=pk)
        
        party_name = request.data.get('name')
        gstin = request.data.get('gstin', '')
        row_ids = request.data.get('row_ids', [])  # Rows to update after creation
        
        if not party_name:
            return Response({'error': 'Party name is required'}, status=400)
        
        # Check if already exists
        existing = Ledger.objects.filter(
            company_id=sales_import.company_id,
            name__iexact=party_name
        ).first()
        
        if existing:
            ledger = existing
        else:
            # Create new party ledger
            ledger = Ledger.objects.create(
                company_id=sales_import.company_id,
                name=party_name,
                ledger_group='sundry_debtors' if sales_import.voucher_type == 'sales' else 'sundry_creditors',
                parent_group='Sundry Debtors' if sales_import.voucher_type == 'sales' else 'Sundry Creditors',
                gstin=gstin,
                synced_from_tally=False
            )
        
        # Update specified rows
        if row_ids:
            updated = sales_import.rows.filter(id__in=row_ids).update(party_ledger=ledger)
            # Re-validate updated rows
            for row in sales_import.rows.filter(id__in=row_ids):
                row.validate_row()
        
        return Response({
            'ledger_id': ledger.id,
            'ledger_name': ledger.name,
            'message': f"Party '{party_name}' {'found' if existing else 'created'}"
        })


class SalesImportCreateItemView(APIView):
    """Create missing stock item on-the-fly"""
    
    @transaction.atomic
    def post(self, request, pk):
        sales_import = SalesImport.objects.get(pk=pk)
        
        item_name = request.data.get('name')
        unit = request.data.get('unit', 'Nos')
        gst_rate = request.data.get('gst_rate', 0)
        hsn_code = request.data.get('hsn_code', '')
        
        if not item_name:
            return Response({'error': 'Item name is required'}, status=400)
        
        # Check if already exists
        existing = StockItem.objects.filter(
            company_id=sales_import.company_id,
            name__iexact=item_name
        ).first()
        
        if existing:
            stock_item = existing
        else:
            stock_item = StockItem.objects.create(
                company_id=sales_import.company_id,
                name=item_name,
                unit=unit,
                gst_rate=gst_rate,
                hsn_code=hsn_code,
                synced_from_tally=False
            )
        
        return Response({
            'item_id': stock_item.id,
            'item_name': stock_item.name,
            'message': f"Item '{item_name}' {'found' if existing else 'created'}"
        })


class SalesImportProcessView(APIView):
    """Create vouchers from validated rows"""
    
    @transaction.atomic
    def post(self, request, pk):
        from .models import Voucher, VoucherEntry, VoucherItem
        
        sales_import = SalesImport.objects.get(pk=pk)
        row_ids = request.data.get('row_ids', [])
        
        # Get rows to process
        if row_ids:
            rows = sales_import.rows.filter(id__in=row_ids, validation_status__in=['valid', 'warning'])
        else:
            rows = sales_import.rows.filter(validation_status__in=['valid', 'warning'])
        
        created_vouchers = []
        errors = []
        
        for row in rows:
            try:
                mapped = row.mapped_data
                gst_config = sales_import.gst_config
                
                # Parse date
                date_val = mapped.get('date')
                try:
                    date_obj = pd.to_datetime(date_val).date()
                except:
                    errors.append(f"Row {row.row_number}: Invalid date")
                    continue
                
                # Parse amount
                try:
                    amount = float(str(mapped.get('amount', 0)).replace(',', ''))
                except:
                    errors.append(f"Row {row.row_number}: Invalid amount")
                    continue
                
                # Calculate GST
                gst_details = {}
                if gst_config.get('method') == 'from_excel':
                    gst_details = {
                        'cgst': float(str(mapped.get('cgst', 0)).replace(',', '') or 0),
                        'sgst': float(str(mapped.get('sgst', 0)).replace(',', '') or 0),
                        'igst': float(str(mapped.get('igst', 0)).replace(',', '') or 0),
                        'cess': float(str(mapped.get('cess', 0)).replace(',', '') or 0),
                    }
                elif gst_config.get('method') == 'auto_calculate':
                    rate = float(gst_config.get('gst_rate', 18))
                    is_igst = gst_config.get('is_igst', False)
                    if is_igst:
                        gst_details = {'igst': amount * rate / 100, 'cgst': 0, 'sgst': 0}
                    else:
                        half_rate = rate / 2
                        gst_details = {'cgst': amount * half_rate / 100, 'sgst': amount * half_rate / 100, 'igst': 0}
                
                # Create voucher
                voucher = Voucher.objects.create(
                    company_id=sales_import.company_id,
                    voucher_type=sales_import.voucher_type,
                    invoice_type='item' if sales_import.import_type == 'with_item' else 'accounting',
                    date=date_obj,
                    voucher_number=str(mapped.get('voucher_number', mapped.get('reference_no', ''))),
                    reference=str(mapped.get('reference_no', '')),
                    party_name=str(mapped.get('party_name', '')),
                    party_ledger=row.party_ledger,
                    amount=amount,
                    gst_details=gst_details,
                    narration=str(mapped.get('narration', '')),
                    status='draft',
                    verification_status='verified' if row.party_ledger else 'unverified',
                    source='import',
                    created_by=request.user
                )
                
                # Create voucher items if item-based
                if sales_import.import_type == 'with_item':
                    VoucherItem.objects.create(
                        voucher=voucher,
                        item_name=str(mapped.get('item_name', '')),
                        quantity=float(str(mapped.get('quantity', 1)).replace(',', '') or 1),
                        rate=float(str(mapped.get('rate', 0)).replace(',', '') or 0),
                        amount=amount,
                        gst_rate=float(str(mapped.get('gst_rate', 0)).replace(',', '') or 0),
                        hsn_code=str(mapped.get('hsn_code', ''))
                    )
                
                row.voucher = voucher
                row.validation_status = 'processed'
                row.processed_at = timezone.now()
                row.save()
                
                created_vouchers.append(voucher.id)
                
            except Exception as e:
                errors.append(f"Row {row.row_number}: {str(e)}")
        
        # Update import stats
        sales_import.processed_rows = sales_import.rows.filter(validation_status='processed').count()
        sales_import.save()
        
        return Response({
            'created_count': len(created_vouchers),
            'voucher_ids': created_vouchers,
            'errors': errors
        })


class SalesImportPushTallyView(APIView):
    """Push processed vouchers to Tally"""
    
    @transaction.atomic
    def post(self, request, pk):
        from .models import Voucher
        from apps.tally_connector.models import DesktopConnector, SyncOperation
        
        sales_import = SalesImport.objects.get(pk=pk)
        row_ids = request.data.get('row_ids', [])
        
        # Get processed rows
        if row_ids:
            rows = sales_import.rows.filter(id__in=row_ids, validation_status='processed')
        else:
            rows = sales_import.rows.filter(validation_status='processed')
        
        voucher_ids = rows.values_list('voucher_id', flat=True)
        vouchers = Voucher.objects.filter(id__in=voucher_ids)
        
        # Get connector
        connector = DesktopConnector.objects.filter(
            company_id=sales_import.company_id,
            status='active'
        ).first()
        
        if not connector:
            return Response({'error': 'No active Tally connector found'}, status=400)
        
        synced_count = 0
        for voucher in vouchers:
            try:
                SyncOperation.objects.create(
                    connector=connector,
                    operation_type='create_voucher',
                    voucher=voucher,
                    request_xml=voucher.generate_tally_xml(),
                    priority=2
                )
                voucher.status = 'queued'
                voucher.save()
                synced_count += 1
            except Exception as e:
                continue
        
        # Update row status
        for row in rows:
            if row.voucher and row.voucher.status == 'queued':
                row.validation_status = 'synced'
                row.save()
        
        sales_import.synced_rows = sales_import.rows.filter(validation_status='synced').count()
        if sales_import.synced_rows == sales_import.total_rows:
            sales_import.status = 'completed'
        sales_import.save()
        
        return Response({
            'synced_count': synced_count,
            'message': f'{synced_count} vouchers queued for Tally sync'
        })
