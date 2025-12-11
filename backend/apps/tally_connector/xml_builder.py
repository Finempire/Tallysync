from django.utils.html import escape

class VoucherXMLBuilder:
    def __init__(self, voucher):
        self.voucher = voucher

    def build(self):
        v = self.voucher
        # Map voucher type to Tally VCHTYPE
        vch_type_map = {
            'payment': 'Payment',
            'receipt': 'Receipt',
            'sales': 'Sales',
            'purchase': 'Purchase',
            'journal': 'Journal',
            'contra': 'Contra'
        }
        tally_type = vch_type_map.get(v.voucher_type.lower(), 'Journal')
        
        # Build XML
        xml = f"""<ENVELOPE>
    <HEADER>
        <TALLYREQUEST>Import Data</TALLYREQUEST>
    </HEADER>
    <BODY>
        <IMPORTDATA>
            <REQUESTDESC>
                <REPORTNAME>Vouchers</REPORTNAME>
            </REQUESTDESC>
            <REQUESTDATA>
                <TALLYMESSAGE xmlns:UDF="TallyUDF">
                    <VOUCHER VCHTYPE="{tally_type}" ACTION="Create" OBJVIEW="Accounting Voucher View">
                        <DATE>{v.date.strftime('%Y%m%d')}</DATE>
                        <VOUCHERTYPENAME>{tally_type}</VOUCHERTYPENAME>
                        <VOUCHERNUMBER>{v.voucher_number or ''}</VOUCHERNUMBER>
                        <REFERENCE>{escape(v.reference or '')}</REFERENCE>
                        <NARRATION>{escape(v.narration or '')}</NARRATION>
                        <PARTYLEDGERNAME>{escape(v.party_ledger.name if v.party_ledger else '')}</PARTYLEDGERNAME>
                        <EFFECTIVEDATE>{v.date.strftime('%Y%m%d')}</EFFECTIVEDATE>
                        <ISINVOICE>No</ISINVOICE>
"""
        
        # Add Ledger Entries
        entries_xml = ""
        
        if v.entries.exists():
            # Use existing entries
            for entry in v.entries.all().order_by('order'):
                ledger_name = escape(entry.ledger.name)
                # Tally Logic: Debit is negative, Credit is positive (Usually)
                # But ALLLEDGERENTRIES content usually follows ISDEEMEDPOSITIVE flag
                # IF ISDEEMEDPOSITIVE = Yes (Debit), Amount should be negative?
                # Let's follow standard Tally XML practice:
                # Debit = Negative number, ISDEEMEDPOSITIVE = Yes
                # Credit = Positive number, ISDEEMEDPOSITIVE = No
                
                amount_val = -abs(entry.amount) if entry.is_debit else abs(entry.amount)
                
                entries_xml += f"""
                        <ALLLEDGERENTRIES.LIST>
                            <LEDGERNAME>{ledger_name}</LEDGERNAME>
                            <ISDEEMEDPOSITIVE>{'Yes' if entry.is_debit else 'No'}</ISDEEMEDPOSITIVE>
                            <LEDGERFROMITEM>No</LEDGERFROMITEM>
                            <REMOVEZEROENTRIES>No</REMOVEZEROENTRIES>
                            <ISPARTYLEDGER>{"Yes" if entry.ledger == v.party_ledger else "No"}</ISPARTYLEDGER>
                            <ISLASTDEEMEDPOSITIVE>{'Yes' if entry.is_debit else 'No'}</ISLASTDEEMEDPOSITIVE>
                            <AMOUNT>{amount_val}</AMOUNT>
                        </ALLLEDGERENTRIES.LIST>"""
        else:
            # Dynamic Generation from Settings
            from apps.vouchers.models import VoucherSettings
            try:
                settings = VoucherSettings.objects.get(company=v.company, transaction_type=v.voucher_type)
            except VoucherSettings.DoesNotExist:
                # Fallback or error? For now, we need settings.
                # If no settings, maybe we can't generate valid XML.
                # However, to avoid crash, we skip or use Party Only.
                settings = None
            
            # 1. Party Ledger Entry
            if v.party_ledger:
                is_party_debit = v.voucher_type in ['sales', 'payment'] # Sales -> Party Dr, Payment -> Party Dr (Wait, Payment -> Party Dr)
                # Sales: Party Dr, Sales Cr
                # Purchase: Purchase Dr, Party Cr
                # Payment: Party Dr (Receiver), Bank Cr
                # Receipt: Bank Dr, Party Cr (Giver)
                
                # Determine sign based on type
                if v.voucher_type == 'sales': is_party_debit = True
                elif v.voucher_type == 'purchase': is_party_debit = False
                elif v.voucher_type == 'payment': is_party_debit = True
                elif v.voucher_type == 'receipt': is_party_debit = False
                
                party_amount = -abs(v.amount) if is_party_debit else abs(v.amount)
                
                entries_xml += f"""
                        <ALLLEDGERENTRIES.LIST>
                            <LEDGERNAME>{escape(v.party_ledger.name)}</LEDGERNAME>
                            <ISDEEMEDPOSITIVE>{'Yes' if is_party_debit else 'No'}</ISDEEMEDPOSITIVE>
                            <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
                            <AMOUNT>{party_amount}</AMOUNT>
                        </ALLLEDGERENTRIES.LIST>"""
            
            # 2. Sales/Purchase Ledger Entry (Account)
            # Calculated Amount = Total - Tax
            gst = v.gst_details or {}
            total_tax = sum(float(gst.get(k, 0)) for k in ['cgst', 'sgst', 'igst', 'cess'])
            base_amount = float(v.amount) - total_tax
            
            acct_ledger = None
            if v.voucher_type == 'sales': acct_ledger = settings.default_sales_ledger if settings else None
            elif v.voucher_type == 'purchase': acct_ledger = settings.default_purchase_ledger if settings else None
            
            if acct_ledger:
                is_acct_debit = not is_party_debit # Opposite of Party
                acct_val_signed = -abs(base_amount) if is_acct_debit else abs(base_amount)
                
                entries_xml += f"""
                        <ALLLEDGERENTRIES.LIST>
                            <LEDGERNAME>{escape(acct_ledger.name)}</LEDGERNAME>
                            <ISDEEMEDPOSITIVE>{'Yes' if is_acct_debit else 'No'}</ISDEEMEDPOSITIVE>
                            <ISPARTYLEDGER>No</ISPARTYLEDGER>
                            <AMOUNT>{acct_val_signed}</AMOUNT>
                        </ALLLEDGERENTRIES.LIST>"""
            
            # 3. Tax Ledgers
            # Tax is same side as Sales/Purchase Ledger (Sales Cr -> Tax Cr, Purchase Dr -> Tax Dr)
            is_tax_debit = is_acct_debit if acct_ledger else (not is_party_debit)
            
            def add_tax_entry(ledger, amount):
                if ledger and amount > 0:
                     val = -abs(amount) if is_tax_debit else abs(amount)
                     return f"""
                        <ALLLEDGERENTRIES.LIST>
                            <LEDGERNAME>{escape(ledger.name)}</LEDGERNAME>
                            <ISDEEMEDPOSITIVE>{'Yes' if is_tax_debit else 'No'}</ISDEEMEDPOSITIVE>
                            <ISPARTYLEDGER>No</ISPARTYLEDGER>
                            <AMOUNT>{val}</AMOUNT>
                        </ALLLEDGERENTRIES.LIST>"""
                return ""

            if settings:
                entries_xml += add_tax_entry(settings.default_cgst_ledger, gst.get('cgst', 0))
                entries_xml += add_tax_entry(settings.default_sgst_ledger, gst.get('sgst', 0))
                entries_xml += add_tax_entry(settings.default_igst_ledger, gst.get('igst', 0))
                entries_xml += add_tax_entry(settings.default_cess_ledger, gst.get('cess', 0))

        xml += entries_xml
        
        xml += """
                    </VOUCHER>
                </TALLYMESSAGE>
            </REQUESTDATA>
        </IMPORTDATA>
    </BODY>
</ENVELOPE>"""
        
        return xml.strip()
