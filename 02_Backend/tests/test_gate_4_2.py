import tempfile
from io import StringIO
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.contrib.auth.models import User
from datetime import date
from decimal import Decimal

from core.models import (
    Installation, Account, FinancialYear, AccountHead,
    ImportBatch, ImportedRecord, Transaction,
    OutflowNature, BudgetType, UserProfile
)
from core.import_services import parse_import_file, validate_import_batch, execute_import_batch

class Gate42Tests(TestCase):
    def setUp(self):
        self.user_admin = User.objects.create_user(username='admin_user2', password='123')
        UserProfile.objects.create(user=self.user_admin, role=UserProfile.Role.ADMINISTRATOR)
        
        self.inst = Installation.objects.create(installation_code='INST-02', installation_name='Main')
        self.qpf = Account.objects.create(installation=self.inst, code='QPF', name='QPF Fund')
        
        self.fy26 = FinancialYear.objects.create(
            code='2026-27', name='FY 2026-27', start_date=date(2026, 7, 1), end_date=date(2027, 6, 30), status='OPEN'
        )
        
        # Masters from migration
        self.head_salaries = AccountHead.objects.create(account=self.qpf, name='Salaries', code='QPF-SAL')
        self.head_fin = AccountHead.objects.create(account=self.qpf, name='Fin Asst Indls', code='QPF-FAI')
        self.head_sib = AccountHead.objects.create(account=self.qpf, name='Received from SIB', code='QPF-SIB')
        self.head_cap = AccountHead.objects.create(account=self.qpf, name='Cap Enhancement MP', code='QPF-CEM')
        self.head_pass = AccountHead.objects.create(account=self.qpf, name='All pass through transactions', code='QPF-PTT')
        self.head_tea = AccountHead.objects.create(account=self.qpf, name='Tea Bar', code='QPF-TEA')
        self.head_ps3 = AccountHead.objects.create(account=self.qpf, name='Received from Parade Fund Acct', code='QPF-PS3')
        self.head_ps4 = AccountHead.objects.create(account=self.qpf, name='Received from Umra & Haj Acct', code='QPF-PS4')
        
        self.out_addl = OutflowNature.objects.create(code='ADDL', name='Addl')
        self.out_routine = OutflowNature.objects.create(code='ROUTINE', name='Routine')

    def test_mappings(self):
        content = "Date,Amount,HeadCode,UnitType,Direction\n"
        # 1. Salaries maps to Salaries
        content += "2026-08-01,100.00,Salaries,,\n"
        # 2. Fin Asst Indis maps to Fin Asst Indls
        content += "2026-08-02,200.00,Fin Asst Indis,,\n"
        # 3. Amount Tfr from SIB maps to Received from SIB
        content += "2026-08-03,300.00,Amount Tfr from SIB,,\n"
        # 4. Cap Enhancement MP maps to Cap Enhancement MP
        content += "2026-08-04,400.00,Cap Enhancement MP,,\n"
        # 5/9. Pass Through Transactions maps to All pass through transactions and pass_through=True
        content += "2026-08-05,500.00,Pass Through Transactions,Pass Through,\n"
        # 6. Tea Bar maps to Tea Bar
        content += "2026-08-06,600.00,Tea Bar,,\n"
        # 7. Amount Tfr from PS-3 maps to Received from Parade Fund Acct
        content += "2026-08-07,700.00,Amount Tfr from PS-3,,\n"
        # 8. Amount Tfr from PS-4 maps to Received from Umra & Haj Acct
        content += "2026-08-08,800.00,Amount Tfr from PS-4,,\n"
        # 11. Addl maps to Outflow Nature Addl
        content += "2026-08-09,900.00,Salaries,Addl,\n"
        # 12. Routine maps to Outflow Nature Routine
        content += "2026-08-10,1000.00,Salaries,Routine,\n"
        # 13. Unknown values are not silently imported
        content += "2026-08-11,1100.00,Unknown Head,,\n"
        
        csv_file = SimpleUploadedFile("import.csv", content.encode('utf-8'))
        batch = ImportBatch.objects.create(
            account=self.qpf, source_file=csv_file, source_type='CSV', imported_by=self.user_admin
        )
        parse_import_file(batch)
        mapping = {'date': 'Date', 'amount': 'Amount', 'head_code': 'HeadCode', 'unit_type': 'UnitType'}
        validate_import_batch(batch, mapping)
        
        records = batch.records.order_by('original_row_number')
        
        # Test 1-8, 11, 12 should be valid
        for i in range(10):
            self.assertEqual(records[i].validation_status, 'VALID', f"Row {i} failed: {records[i].error_message}")
            
        # Test 13
        self.assertEqual(records[10].validation_status, 'INVALID')
        self.assertIn("Unknown Account Head", records[10].error_message)
        
        # Now execute and check db attributes
        execute_import_batch(batch, mapping)
        
        # 9. Pass Through check
        txn_pass = Transaction.objects.get(account_head=self.head_pass)
        self.assertTrue(txn_pass.pass_through)
        
        # 11/12 Outflow check
        txn_addl = Transaction.objects.get(transaction_date=date(2026, 8, 9))
        self.assertEqual(txn_addl.outflow_nature, self.out_addl)
        
        txn_routine = Transaction.objects.get(transaction_date=date(2026, 8, 10))
        self.assertEqual(txn_routine.outflow_nature, self.out_routine)
        
    def test_reimbursement_is_not_budget_type(self):
        # 10. Reimbursement is not a BudgetType
        self.assertFalse(BudgetType.objects.filter(name__iexact='Reimbursement').exists())
