
from rest_framework import serializers
from .models import Voucher, VoucherEntry, VoucherSettings

class VoucherEntrySerializer(serializers.ModelSerializer):
    ledger_name = serializers.CharField(source='ledger.name', read_only=True)
    
    class Meta:
        model = VoucherEntry
        fields = '__all__'


class VoucherSerializer(serializers.ModelSerializer):
    entries = VoucherEntrySerializer(many=True, read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)
    party_ledger_name = serializers.CharField(source='party_ledger.name', read_only=True)
    
    class Meta:
        model = Voucher
        fields = '__all__'


class VoucherCreateSerializer(serializers.ModelSerializer):
    entries = VoucherEntrySerializer(many=True)
    
    class Meta:
        model = Voucher
        fields = ['company', 'voucher_type', 'date', 'reference', 'narration', 'party_ledger', 'entries', 'gst_details', 'amount', 'party_name']
    
    def validate_entries(self, entries):
        total_debit = sum(e['amount'] for e in entries if e.get('is_debit', True))
        total_credit = sum(e['amount'] for e in entries if not e.get('is_debit', True))
        # if total_debit != total_credit:
             # raise serializers.ValidationError(f"Debits ({total_debit}) must equal credits ({total_credit})")
        return entries
    
    def create(self, validated_data):
        entries_data = validated_data.pop('entries')
        # validated_data['amount'] = sum(e['amount'] for e in entries_data if e.get('is_debit', True)) # Trust the amount passed or calc?
        # Let's trust amount passed for now or recalc if needed. 
        voucher = Voucher.objects.create(**validated_data)
        for idx, entry_data in enumerate(entries_data):
            VoucherEntry.objects.create(voucher=voucher, order=idx, **entry_data)
        return voucher


class VoucherSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = VoucherSettings
        fields = '__all__'
