import pytest
from decimal import Decimal
from django.test import Client, TestCase
from django.contrib.auth import get_user_model
from django.core.management import call_command
from core.models import Account, FinancialYear, MajorHead, AccountHead, Transaction
from core.services import get_balance_available, get_sub_fund_distribution_summary

@pytest.mark.django_db
class SubFundTransfersAndReconciliationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_initial_data', verbosity=0)
        call_command('seed_qpf_subheads', verbosity=0)
        cls.fy, _ = FinancialYear.objects.get_or_create(
            name='FY 2025-26',
            defaults={'code': '2025-26', 'start_date': '2025-07-01', 'end_date': '2026-06-30',
                      'status': FinancialYear.Status.CLOSED}
        )
        call_command('import_qpf_historical', commit=True, verbosity=0)
        cls.user = get_user_model().objects.get(username='admin')
        cls.qpf = Account.objects.get(name='Quaid Portrait Fund')

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)
        session = self.client.session
        session['active_account_id'] = self.qpf.id
        session['active_fy_id'] = self.fy.id
        session.save()

    def test_sub_fund_distribution_summary_and_reconciliation(self):
        # 1. Test summary service
        dist = get_sub_fund_distribution_summary(self.qpf, self.fy)
        self.assertGreaterEqual(len(dist['sub_funds']), 4)
        self.assertTrue(dist['is_reconciled'])
        self.assertEqual(dist['variance'], Decimal('0.00'))
        self.assertEqual(dist['fund_balance_available'], dist['totals']['net_balance'])

        # 2. Test Client GET on both hub URLs and ledger
        for url in ['/transactions/', '/transactions/transfer/new/', '/transactions/transfers/']:
            res = self.client.get(url)
            self.assertEqual(res.status_code, 200)
            if 'transfer' in url:
                self.assertIn(b'Sub-Fund Distribution', res.content)
                self.assertIn(b'Zero Net Cash Impact Guarantee', res.content)

        # 3. Test Inter-Sub-Fund Transfer
        self.fy.status = FinancialYear.Status.OPEN
        self.fy.save()

        mh_qpf = MajorHead.objects.filter(account=self.qpf, code__icontains='QPF').first() or MajorHead.objects.filter(account=self.qpf).first()
        ah_qpf = AccountHead.objects.filter(account=self.qpf, major_head=mh_qpf).first()
        mh_mess = MajorHead.objects.filter(account=self.qpf, code__icontains='MESS').first()
        if not mh_mess:
            mhs = list(MajorHead.objects.filter(account=self.qpf))
            mh_mess = mhs[1] if len(mhs) > 1 else mhs[0]
        ah_mess = AccountHead.objects.filter(account=self.qpf, major_head=mh_mess).first()

        initial_bal = get_balance_available(self.qpf, self.fy)
        initial_dist = get_sub_fund_distribution_summary(self.qpf, self.fy)
        qpf_bal_before = [x['net_balance'] for x in initial_dist['sub_funds'] if x['id'] == mh_qpf.id][0]
        mess_bal_before = [x['net_balance'] for x in initial_dist['sub_funds'] if x['id'] == mh_mess.id][0]

        transfer_amt = Decimal('500000.00')

        res = self.client.post('/transactions/transfer/new/', {
            'transaction_date': '2026-05-20',
            'source_major_head': mh_qpf.id,
            'source_account_head': ah_qpf.id,
            'dest_major_head': mh_mess.id,
            'dest_account_head': ah_mess.id,
            'amount': str(transfer_amt),
            'sanction_reference': 'TEST-SUB-FUND-RECON',
            'description': 'Reallocation between sub-funds',
        }, follow=True)

        self.assertEqual(res.status_code, 200)

        # Verify balances after transfer
        final_bal = get_balance_available(self.qpf, self.fy)
        final_dist = get_sub_fund_distribution_summary(self.qpf, self.fy)
        qpf_bal_after = [x['net_balance'] for x in final_dist['sub_funds'] if x['id'] == mh_qpf.id][0]
        mess_bal_after = [x['net_balance'] for x in final_dist['sub_funds'] if x['id'] == mh_mess.id][0]

        # Verify 0 net cash impact and proper sub-fund balance shift
        self.assertEqual(final_bal, initial_bal)
        self.assertEqual(qpf_bal_after, qpf_bal_before - transfer_amt)
        self.assertEqual(mess_bal_after, mess_bal_before + transfer_amt)
        self.assertTrue(final_dist['is_reconciled'])
