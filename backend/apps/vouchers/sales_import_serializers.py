"""
Sales Import Serializers
"""
from rest_framework import serializers
from .sales_import_models import SalesImport, SalesImportRow
from apps.companies.models import Ledger


class SalesImportSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalesImport
        fields = [
            'id', 'company', 'import_type', 'voucher_type',
            'original_filename', 'total_rows', 'status',
            'valid_rows', 'warning_rows', 'error_rows',
            'processed_rows', 'synced_rows',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class SalesImportDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalesImport
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class SalesImportRowSerializer(serializers.ModelSerializer):
    party_ledger_name = serializers.CharField(source='party_ledger.name', read_only=True, allow_null=True)
    sales_ledger_name = serializers.CharField(source='sales_ledger.name', read_only=True, allow_null=True)
    voucher_id = serializers.IntegerField(source='voucher.id', read_only=True, allow_null=True)
    voucher_status = serializers.CharField(source='voucher.status', read_only=True, allow_null=True)
    
    class Meta:
        model = SalesImportRow
        fields = [
            'id', 'row_number', 'raw_data', 'mapped_data',
            'party_ledger', 'party_ledger_name',
            'sales_ledger', 'sales_ledger_name',
            'validation_status', 'validation_errors', 'validation_warnings',
            'voucher_id', 'voucher_status'
        ]
        read_only_fields = ['id', 'row_number', 'raw_data']


class SalesImportRowUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalesImportRow
        fields = ['mapped_data', 'party_ledger', 'sales_ledger']


class LedgerSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ledger
        fields = ['id', 'name', 'parent_group', 'ledger_group']
