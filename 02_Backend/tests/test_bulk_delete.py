from datetime import date
from decimal import Decimal
import pytest
from django.test import Client, TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.management import call_command
from core.models import (
    Transaction,
    Reimbursement,
    ReimbursementType,
    Budget,
    BudgetLine,
    BudgetType,
    Account,
    FinancialYear,
    AccountHead,
    AuditLog,
    Unit,
    UserProfile,
)

User = get_user_model()


class BulkDeleteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_initial_data')
        FinancialYear.objects.get_or_create(code='2025-26', defaults={
            'name': 'FY 2025-26', 'start_date': date(2025, 7, 1), 'end_date': date(2026, 6, 30), 'status': 'OPEN'
        })
        call_command('import_qpf_historical', commit=True)
        cls.account = Account.objects.get(code='QPF')
        cls.fy = FinancialYear.objects.get(code='2025-26')
        
        cls.admin_user, _ = User.objects.get_or_create(username='admin_bulk', defaults={'password': 'password'})
        cls.admin_user.set_password('password')
        cls.admin_user.save()
        profile, _ = UserProfile.objects.get_or_create(user=cls.admin_user)
        profile.role = UserProfile.Role.ADMINISTRATOR
        profile.save()

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.admin_user)
        session = self.client.session
        session['active_account_id'] = self.account.id
        session['active_fy_id'] = self.fy.id
        session.save()

    def test_transaction_bulk_delete_non_historical(self):
        head = AccountHead.objects.filter(account=self.account).first()
        t1 = Transaction.objects.create(
            account=self.account,
            financial_year=self.fy,
            account_head=head,
            direction='OUTFLOW',
            amount=Decimal('500.00'),
            transaction_date='2025-10-01',
            is_historical=False,
        )
        t2 = Transaction.objects.create(
            account=self.account,
            financial_year=self.fy,
            account_head=head,
            direction='OUTFLOW',
            amount=Decimal('750.00'),
            transaction_date='2025-10-02',
            is_historical=False,
        )

        response = self.client.post(
            reverse('core:transaction_bulk_delete'),
            {'selected_ids': [str(t1.id), str(t2.id)]},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Transaction.objects.filter(id=t1.id).exists())
        self.assertFalse(Transaction.objects.filter(id=t2.id).exists())
        self.assertTrue(
            AuditLog.objects.filter(record_id=str(t1.id)).exists()
        )

    def test_historical_transaction_protected_from_bulk_delete(self):
        hist_tx = Transaction.objects.filter(account=self.account, is_historical=True).first()
        self.assertIsNotNone(hist_tx)
        hist_id = hist_tx.id

        response = self.client.post(
            reverse('core:transaction_bulk_delete'),
            {'selected_ids': [str(hist_id)]},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Transaction.objects.filter(id=hist_id).exists())

    def test_reimbursement_bulk_delete(self):
        rtype = ReimbursementType.objects.first()
        r1 = Reimbursement.objects.create(
            reimbursement_type=rtype,
            expected_amount=Decimal('1000.00'),
            received_amount=Decimal('0.00'),
            expected_date='2025-11-01',
            source='Test Source',
            status='EXPECTED',
        )
        r2 = Reimbursement.objects.create(
            reimbursement_type=rtype,
            expected_amount=Decimal('2000.00'),
            received_amount=Decimal('0.00'),
            expected_date='2025-11-02',
            source='Test Source 2',
            status='EXPECTED',
        )

        response = self.client.post(
            reverse('core:reimbursement_bulk_delete'),
            {'selected_ids': [str(r1.id), str(r2.id)]},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Reimbursement.objects.filter(id=r1.id).exists())
        self.assertFalse(Reimbursement.objects.filter(id=r2.id).exists())

    def test_budget_lines_bulk_delete(self):
        budget = Budget.objects.create(
            account=self.account,
            financial_year=self.fy,
        )
        head = AccountHead.objects.filter(account=self.account).first()
        btype = BudgetType.objects.first()
        bl1 = BudgetLine.objects.create(
            budget=budget,
            account_head=head,
            budget_type=btype,
            amount=Decimal('10000.00'),
        )

        response = self.client.post(
            reverse('core:budgetline_bulk_delete', kwargs={'budget_id': budget.id}),
            {'selected_ids': [str(bl1.id)]},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(BudgetLine.objects.filter(id=bl1.id).exists())

    def test_unit_master_bulk_delete(self):
        free_unit = Unit.objects.create(name='Unused Test Unit', code='UTU')
        response = self.client.post(
            reverse('masters:unit_bulk_delete'),
            {'selected_ids': [str(free_unit.id)]},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Unit.objects.filter(id=free_unit.id).exists())

    def test_user_bulk_delete_and_self_protection(self):
        u1 = User.objects.create_user(username='testclerk1', password='password123')
        u2 = User.objects.create_user(username='testclerk2', password='password123')

        response = self.client.post(
            reverse('accounts:user_bulk_delete'),
            {'selected_ids': [str(u1.id), str(u2.id), str(self.admin_user.id)]},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(id=u1.id).exists())
        self.assertFalse(User.objects.filter(id=u2.id).exists())
        self.assertTrue(User.objects.filter(id=self.admin_user.id).exists())
