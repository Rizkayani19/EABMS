from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import IntegrityError
from core.models import Account, MajorHead, AccountHead, FinancialYear, Transaction, UserProfile
from core.forms import InflowForm, OutflowForm


class AhfConsolidatedMastersTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_initial_data', verbosity=0)
        call_command('seed_ahf_consolidated_masters', verbosity=0)

        cls.user = get_user_model().objects.filter(is_superuser=True).first()
        if not cls.user:
            cls.user = get_user_model().objects.create_superuser('admin', 'admin@example.com', 'admin123')
        if not hasattr(cls.user, 'profile'):
            UserProfile.objects.create(user=cls.user, role=UserProfile.Role.ADMIN)

        from datetime import date
        cls.account = Account.objects.get(code='AHF')
        cls.fy, _ = FinancialYear.objects.get_or_create(
            code='2025-26',
            defaults={
                'name': 'FY 2025-26',
                'start_date': date(2025, 7, 1),
                'end_date': date(2026, 6, 30),
            }
        )

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)
        session = self.client.session
        session['active_account_id'] = self.account.id
        session['active_fy_id'] = self.fy.id
        session.save()

    def test_01_sub_funds_count_and_names(self):
        sub_funds = list(MajorHead.objects.filter(account=self.account).order_by('display_order'))
        self.assertEqual(len(sub_funds), 3)
        expected = [
            (1, 'Hajj Fund', 'SF-01'),
            (2, 'Umrah Sub-Fund', 'SF-02'),
            (3, 'General Sub-Fund', 'SF-03'),
        ]
        for sf, (exp_order, exp_name, exp_code) in zip(sub_funds, expected):
            self.assertEqual(sf.display_order, exp_order)
            self.assertEqual(sf.name, exp_name)
            self.assertEqual(sf.code, exp_code)
            self.assertTrue(sf.is_active)

    def test_02_account_heads_count_per_subfund(self):
        hf = MajorHead.objects.get(account=self.account, name='Hajj Fund')
        uf = MajorHead.objects.get(account=self.account, name='Umrah Sub-Fund')
        gf = MajorHead.objects.get(account=self.account, name='General Sub-Fund')

        self.assertEqual(AccountHead.objects.filter(account=self.account, major_head=hf).count(), 15)
        self.assertEqual(AccountHead.objects.filter(account=self.account, major_head=uf).count(), 15)
        self.assertEqual(AccountHead.objects.filter(account=self.account, major_head=gf).count(), 14)
        self.assertEqual(AccountHead.objects.filter(account=self.account).count(), 44)

    def test_03_ser_1_to_6_head_type_is_both(self):
        for sf_name in ['Hajj Fund', 'Umrah Sub-Fund']:
            sf = MajorHead.objects.get(account=self.account, name=sf_name)
            heads = list(AccountHead.objects.filter(account=self.account, major_head=sf).order_by('display_order'))[:6]
            for h in heads:
                self.assertEqual(h.head_type, AccountHead.HeadType.BOTH, f'{h.name} must be BOTH')

    def test_04_exact_conventions_and_running_cases(self):
        gf = MajorHead.objects.get(account=self.account, name='General Sub-Fund')
        head_names = set(AccountHead.objects.filter(account=self.account, major_head=gf).values_list('name', flat=True))

        self.assertIn('Profit from Running acc', head_names)
        self.assertIn('Received from Parade Fund', head_names)
        self.assertNotIn('Received from Trade Fund', head_names)
        self.assertIn('Received from AG br', head_names)
        self.assertIn('Salaries', head_names)
        self.assertIn('Refreshment exp', head_names)
        self.assertIn('Travelling exp', head_names)
        self.assertIn('Unforeseen exp', head_names)
        self.assertIn('Misc exp', head_names)

        hf = MajorHead.objects.get(account=self.account, name='Hajj Fund')
        hf_names = set(AccountHead.objects.filter(account=self.account, major_head=hf).values_list('name', flat=True))
        self.assertIn('Payment to Tour OP', hf_names)
        self.assertIn('Reimbursement from Tour OP', hf_names)
        self.assertIn('Recce & Prep exp', hf_names)
        self.assertIn('Adm exp', hf_names)
        self.assertIn('Other exp', hf_names)
        self.assertIn('Misc exp', hf_names)

    def test_05_multi_subfund_name_coexistence(self):
        # 'Misc exp' exists under all 3 Sub-Funds concurrently
        misc_heads = AccountHead.objects.filter(account=self.account, name='Misc exp')
        self.assertEqual(misc_heads.count(), 3)
        self.assertEqual(set(misc_heads.values_list('major_head__name', flat=True)), {'Hajj Fund', 'Umrah Sub-Fund', 'General Sub-Fund'})

        # Same name under same major_head should fail uniqueness
        hf = MajorHead.objects.get(account=self.account, name='Hajj Fund')
        with self.assertRaises(IntegrityError):
            AccountHead.objects.create(account=self.account, major_head=hf, name='Misc exp', head_type='OUTFLOW')

    def test_06_inflow_and_outflow_form_support(self):
        hf = MajorHead.objects.get(account=self.account, name='Hajj Fund')
        hajj_ser1 = AccountHead.objects.get(account=self.account, major_head=hf, display_order=1)

        inflow_form = InflowForm(account=self.account, financial_year=self.fy)
        self.assertIn(hajj_ser1, inflow_form.fields['account_head'].queryset)

        outflow_form = OutflowForm(account=self.account, financial_year=self.fy)
        self.assertIn(hajj_ser1, outflow_form.fields['account_head'].queryset)

    def test_07_ajax_load_account_heads_direction_filtering(self):
        hf = MajorHead.objects.get(account=self.account, name='Hajj Fund')
        res_inflow = self.client.get(f'/transactions/ajax/load-account-heads/?major_head={hf.id}&direction=INFLOW')
        self.assertEqual(res_inflow.status_code, 200)
        content_inflow = res_inflow.content.decode('utf-8')
        self.assertIn('Hajj Subs', content_inflow)
        self.assertIn('Package / Accommodation Difference', content_inflow)
        self.assertNotIn('Airline & Travel', content_inflow)

        res_outflow = self.client.get(f'/transactions/ajax/load-account-heads/?major_head={hf.id}&direction=OUTFLOW')
        self.assertEqual(res_outflow.status_code, 200)
        content_outflow = res_outflow.content.decode('utf-8')
        self.assertIn('Hajj Subs', content_outflow)
        self.assertIn('Airline & Travel', content_outflow)
        self.assertNotIn('Package / Accommodation Difference', content_outflow)

    def test_08_crud_major_heads(self):
        # List
        res = self.client.get('/masters/major-heads/')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Hajj Fund')
        self.assertContains(res, 'Umrah Sub-Fund')
        self.assertContains(res, 'General Sub-Fund')

        # Create
        res = self.client.post('/masters/major-heads/new/', {
            'account': self.account.id,
            'name': 'Special Projects Sub-Fund',
            'code': 'SF-04',
            'display_order': 4,
            'is_active': True,
        })
        self.assertRedirects(res, '/masters/major-heads/')
        new_mh = MajorHead.objects.filter(account=self.account, name='Special Projects Sub-Fund').first()
        self.assertIsNotNone(new_mh)

        # Update
        res = self.client.post(f'/masters/major-heads/{new_mh.id}/edit/', {
            'account': self.account.id,
            'name': 'Special Projects Sub-Fund (Updated)',
            'code': 'SF-04-REV',
            'display_order': 4,
            'is_active': True,
        })
        self.assertRedirects(res, '/masters/major-heads/')
        new_mh.refresh_from_db()
        self.assertEqual(new_mh.name, 'Special Projects Sub-Fund (Updated)')

        # Toggle
        res = self.client.post(f'/masters/major-heads/{new_mh.id}/toggle/')
        new_mh.refresh_from_db()
        self.assertFalse(new_mh.is_active)

        # Bulk Delete
        res = self.client.post('/masters/major-heads/bulk-delete/', {'selected_ids': [new_mh.id]})
        self.assertRedirects(res, '/masters/major-heads/')
        self.assertFalse(MajorHead.objects.filter(id=new_mh.id).exists())

    def test_09_crud_account_heads(self):
        # List
        res = self.client.get('/masters/account-heads/')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Hajj Subs — Self-Finance')
        self.assertContains(res, 'Sub-Fund (Tier 1)')

        # Filter by Major Head
        hf = MajorHead.objects.get(account=self.account, name='Hajj Fund')
        res_filter = self.client.get(f'/masters/account-heads/?major_head_id={hf.id}')
        self.assertEqual(res_filter.status_code, 200)
        self.assertEqual(res_filter.context['total_count'], 15)

        # Create
        res = self.client.post('/masters/account-heads/new/', {
            'account': self.account.id,
            'major_head': hf.id,
            'name': 'Special Emergency Subsidy',
            'code': 'AHF-HF-16',
            'head_type': 'BOTH',
            'display_order': 16,
            'is_active': True,
        })
        self.assertRedirects(res, '/masters/account-heads/')
        new_ah = AccountHead.objects.filter(account=self.account, name='Special Emergency Subsidy').first()
        self.assertIsNotNone(new_ah)

        # Update
        res = self.client.post(f'/masters/account-heads/{new_ah.id}/edit/', {
            'account': self.account.id,
            'major_head': hf.id,
            'name': 'Special Emergency Subsidy (Revised)',
            'code': 'AHF-HF-16-REV',
            'head_type': 'OUTFLOW',
            'display_order': 16,
            'is_active': True,
        })
        self.assertRedirects(res, '/masters/account-heads/')
        new_ah.refresh_from_db()
        self.assertEqual(new_ah.name, 'Special Emergency Subsidy (Revised)')
        self.assertEqual(new_ah.head_type, 'OUTFLOW')

        # Toggle
        res = self.client.post(f'/masters/account-heads/{new_ah.id}/toggle/')
        new_ah.refresh_from_db()
        self.assertFalse(new_ah.is_active)

        # Bulk Delete
        res = self.client.post('/masters/account-heads/bulk-delete/', {'selected_ids': [new_ah.id]})
        self.assertRedirects(res, '/masters/account-heads/')
        self.assertFalse(AccountHead.objects.filter(id=new_ah.id).exists())
