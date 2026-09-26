from django.test import TestCase, Client
from django.core.management import call_command
from core.models import FutureBudget, FutureBudgetLine, FutureBudgetKnownChange, FutureBudgetPersonnel
from core.models import Account, FinancialYear, AccountHead, Transaction, UserProfile
from django.contrib.auth.models import User
from decimal import Decimal
from core.future_budget_services import analyze_account_head, compute_system_suggested, get_future_budget_summary

class Gate7Test(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_initial_data', verbosity=0)
        
        from datetime import date
        FinancialYear.objects.create(code='2025-26', name='FY 2025-26', start_date=date(2025, 7, 1), end_date=date(2026, 6, 30))
        
        call_command('import_qpf_historical', commit=True, verbosity=0)
        call_command('seed_qpf_subheads', verbosity=0)
        
        cls.account = Account.objects.get(code='QPF')
        cls.source_fy = FinancialYear.objects.get(code='2025-26')
        cls.target_fy = FinancialYear.objects.get(code='2026-27')
        
        cls.admin_user = User.objects.create_user(username='admin_fb', password='pwd')
        UserProfile.objects.create(user=cls.admin_user, role=UserProfile.Role.ADMINISTRATOR)
        
        cls.clerk_user = User.objects.create_user(username='clerk_fb', password='pwd')
        UserProfile.objects.create(user=cls.clerk_user, role=UserProfile.Role.CLERK)
        
        # Determine an account head that has transactions
        cls.active_ah = Transaction.objects.filter(account=cls.account, financial_year=cls.source_fy, direction='OUTFLOW').first().account_head

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.admin_user)
        # In test middleware or views, request.account is set. 
        # We need to ensure middleware correctly resolves QPF, which might depend on session or default_account.
        self.admin_user.profile.default_account = self.account
        self.admin_user.profile.save()

    def test_1_create_future_budget(self):
        fb = FutureBudget.objects.create(account=self.account, source_fy=self.source_fy, target_fy=self.target_fy)
        self.assertEqual(fb.status, 'DRAFT')

    def test_2_build_future_budget_lines(self):
        fb = FutureBudget.objects.create(account=self.account, source_fy=self.source_fy, target_fy=self.target_fy)
        from core.future_budget_services import build_future_budget_lines
        build_future_budget_lines(fb)
        self.assertTrue(fb.lines.count() > 0)

    def test_3_analyze_account_head(self):
        from django.db.models import Sum
        txns_total = Transaction.objects.filter(account=self.account, financial_year=self.source_fy, account_head=self.active_ah, direction='OUTFLOW').aggregate(total=Sum('amount'))['total']
        res = analyze_account_head(self.account, self.source_fy, self.active_ah)
        self.assertEqual(res['previous_actual'], txns_total)

    def test_4_is_routine(self):
        # We know routine requires >= 8 months.
        res = analyze_account_head(self.account, self.source_fy, self.active_ah)
        self.assertIn('is_routine', res)

    def test_5_continuing_flag(self):
        res = analyze_account_head(self.account, self.source_fy, self.active_ah)
        if res['previous_actual'] > 0:
            self.assertEqual(res['continuing_flag'], 'needs_more_history')

    def test_6_system_suggested_formula(self):
        sug, brk = compute_system_suggested(Decimal('100'), Decimal('0'), Decimal('0'), Decimal('0'), Decimal('0'), Decimal('0'))
        self.assertEqual(sug, Decimal('100.00'))

    def test_7_suggestion_breakdown(self):
        sug, brk = compute_system_suggested(Decimal('100'), Decimal('0'), Decimal('0'), Decimal('0'), Decimal('0'), Decimal('0'))
        self.assertIn('previous_actual', brk)
        self.assertIn('routine_adjustment', brk)

    def test_8_user_proposed(self):
        fb = FutureBudget.objects.create(account=self.account, source_fy=self.source_fy, target_fy=self.target_fy)
        line = FutureBudgetLine.objects.create(future_budget=fb, account_head=self.active_ah, system_suggested=Decimal('100'))
        line.user_proposed = Decimal('150')
        line.save()
        self.assertEqual(line.user_proposed, Decimal('150'))

    def test_9_known_change_link(self):
        fb = FutureBudget.objects.create(account=self.account, source_fy=self.source_fy, target_fy=self.target_fy)
        kc = FutureBudgetKnownChange.objects.create(future_budget=fb, description='Test KC', amount=Decimal('500'), change_type='NEW')
        self.assertEqual(fb.known_changes.count(), 1)

    def test_10_status_lifecycle_draft_proposed(self):
        fb = FutureBudget.objects.create(account=self.account, source_fy=self.source_fy, target_fy=self.target_fy)
        self.assertEqual(fb.status, 'DRAFT')
        fb.status = 'PROPOSED'
        fb.save()
        self.assertEqual(fb.status, 'PROPOSED')

    def test_11_status_lifecycle_block_approved(self):
        # View level block
        fb = FutureBudget.objects.create(account=self.account, source_fy=self.source_fy, target_fy=self.target_fy)
        response = self.client.post(f'/future-budgets/{fb.id}/approve/')
        fb.refresh_from_db()
        self.assertNotEqual(fb.status, 'APPROVED')

    def test_12_historical_transactions_unchanged(self):
        fb = FutureBudget.objects.create(account=self.account, source_fy=self.source_fy, target_fy=self.target_fy)
        count_before = Transaction.objects.count()
        from core.future_budget_services import build_future_budget_lines
        build_future_budget_lines(fb)
        self.assertEqual(Transaction.objects.count(), count_before)

    def test_13_account_isolation(self):
        fb = FutureBudget.objects.create(account=self.account, source_fy=self.source_fy, target_fy=self.target_fy)
        from core.future_budget_services import build_future_budget_lines
        build_future_budget_lines(fb)
        for line in fb.lines.all():
            self.assertEqual(line.account_head.account, self.account)

    def test_14_personnel_baseline(self):
        from core.future_budget_services import get_salaries_baseline
        salaries = get_salaries_baseline(self.account, self.source_fy)
        self.assertTrue(salaries >= 0)

    def test_15_personnel_save_computes_revision(self):
        fb = FutureBudget.objects.create(account=self.account, source_fy=self.source_fy, target_fy=self.target_fy)
        p = FutureBudgetPersonnel.objects.create(future_budget=fb, category_label='Test', current_annual_cost=Decimal('1000'), revision_pct=Decimal('10'))
        self.assertEqual(p.revision_amount, Decimal('100.00'))

    def test_16_personnel_save_computes_projected(self):
        fb = FutureBudget.objects.create(account=self.account, source_fy=self.source_fy, target_fy=self.target_fy)
        p = FutureBudgetPersonnel.objects.create(future_budget=fb, category_label='Test', current_annual_cost=Decimal('1000'), revision_pct=Decimal('10'), new_personnel_cost=Decimal('200'))
        self.assertEqual(p.projected_cost, Decimal('1300.00'))

    def test_17_summary_totals(self):
        fb = FutureBudget.objects.create(account=self.account, source_fy=self.source_fy, target_fy=self.target_fy)
        FutureBudgetLine.objects.create(future_budget=fb, account_head=self.active_ah, previous_actual=Decimal('100'), system_suggested=Decimal('100'))
        summary = get_future_budget_summary(fb)
        self.assertEqual(summary['previous_actual_total'], Decimal('100'))

    def test_18_get_list(self):
        response = self.client.get('/future-budgets/')
        self.assertEqual(response.status_code, 200)

    def test_19_get_new(self):
        response = self.client.get('/future-budgets/new/')
        self.assertEqual(response.status_code, 200)

    def test_20_get_detail(self):
        fb = FutureBudget.objects.create(account=self.account, source_fy=self.source_fy, target_fy=self.target_fy)
        response = self.client.get(f'/future-budgets/{fb.id}/')
        self.assertEqual(response.status_code, 200)

    def test_21_pdf_export(self):
        fb = FutureBudget.objects.create(account=self.account, source_fy=self.source_fy, target_fy=self.target_fy)
        response = self.client.get(f'/future-budgets/{fb.id}/pdf/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

    def test_22_excel_export(self):
        fb = FutureBudget.objects.create(account=self.account, source_fy=self.source_fy, target_fy=self.target_fy)
        response = self.client.get(f'/future-budgets/{fb.id}/excel/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    def test_23_line_edit_saves(self):
        fb = FutureBudget.objects.create(account=self.account, source_fy=self.source_fy, target_fy=self.target_fy)
        line = FutureBudgetLine.objects.create(future_budget=fb, account_head=self.active_ah, system_suggested=Decimal('100'))
        response = self.client.post(f'/future-budgets/lines/{line.id}/edit/', {
            'user_proposed': '150.00', 'justification': 'test', 'remarks': ''
        })
        line.refresh_from_db()
        self.assertEqual(line.user_proposed, Decimal('150.00'))

    def test_24_approve_denied_clerk(self):
        self.client.force_login(self.clerk_user)
        fb = FutureBudget.objects.create(account=self.account, source_fy=self.source_fy, target_fy=self.target_fy, status='PROPOSED')
        response = self.client.post(f'/future-budgets/{fb.id}/approve/')
        self.assertEqual(response.status_code, 403)

    def test_25_unique_together(self):
        FutureBudget.objects.create(account=self.account, source_fy=self.source_fy, target_fy=self.target_fy)
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            FutureBudget.objects.create(account=self.account, source_fy=self.source_fy, target_fy=self.target_fy)

    def test_26_summary_keys(self):
        fb = FutureBudget.objects.create(account=self.account, source_fy=self.source_fy, target_fy=self.target_fy)
        summary = get_future_budget_summary(fb)
        self.assertIn('diff_from_prev_actual', summary)
