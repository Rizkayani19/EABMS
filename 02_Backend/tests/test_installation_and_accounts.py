from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.db.models import ProtectedError
from django.urls import reverse
from core.models import (
    Installation, Account, FinancialYear, AccountHead,
    OpeningBalance, UserProfile, Unit, OutflowNature
)
from decimal import Decimal
from datetime import date


class InstallationAndAccountArchitectureTests(TestCase):
    """
    Tests for Gate 1.5 Tasks 1, 2, 3, 7, 8:
    1. Installation exists.
    2. Accounts belong to correct installation.
    3. Strict account isolation.
    4. QPF seed integrity (24 heads).
    5. PPF / AHF do not inherit QPF heads.
    6. Protected deletion of referenced masters.
    7. Account context middleware resolution.
    """

    def setUp(self):
        # Create installation
        self.inst = Installation.objects.create(
            installation_code='INST-01',
            installation_name='Main Installation'
        )

        # Create 3 official accounts
        self.qpf = Account.objects.create(
            installation=self.inst,
            code='QPF',
            name='Quaid Portrait Fund',
            display_order=1
        )
        self.ppf = Account.objects.create(
            installation=self.inst,
            code='PPF',
            name='PS Parade Fund',
            display_order=2
        )
        self.ahf = Account.objects.create(
            installation=self.inst,
            code='AHF',
            name='Army Haj and Umra Fund',
            display_order=3
        )

        # Create FY 2026-27
        self.fy = FinancialYear.objects.create(
            code='2026-27',
            name='FY 2026-27',
            start_date=date(2026, 7, 1),
            end_date=date(2027, 6, 30),
            status=FinancialYear.Status.OPEN
        )

        # Create 24 QPF heads
        self.qpf_head_names = [
            "B.B.F", "Sty", "IT", "Fin Asst Indls", "Cap Enhancement / Unit 45",
            "Fin Asst MP Unit", "Fin Asst Units", "Late Sitting", "Lunch Offrs",
            "Contract Salaries", "Standing Sanc", "Utility / Maint", "Loan",
            "Rent Charges", "Dte Misc Exp", "Monthly profit on running acct",
            "Received from SIB", "Received from AG Br", "Amount Tfr from PS-3",
            "Amount Tfr from PS-4", "Army Offrs Hand Book", "Received from ASM Atd",
            "Received from CMP Cen", "Bank Guarantee Off"
        ]

        for idx, name in enumerate(self.qpf_head_names, start=1):
            AccountHead.objects.create(
                account=self.qpf,
                code=f"QPF-{idx:02d}",
                name=name,
                display_order=idx
            )

        # Create users
        self.admin_user = User.objects.create_superuser('admin_test', 'admin@test.local', 'pass123')
        UserProfile.objects.create(user=self.admin_user, role=UserProfile.Role.ADMINISTRATOR, default_account=self.qpf)

        self.clerk_user = User.objects.create_user('clerk_test', 'clerk@test.local', 'pass123')
        UserProfile.objects.create(user=self.clerk_user, role=UserProfile.Role.CLERK, default_account=self.qpf)

        self.client = Client()

    def test_01_installation_exists(self):
        """Test 1: Installation exists and holds required attributes."""
        self.assertIsNotNone(self.inst.id)
        self.assertEqual(self.inst.installation_code, 'INST-01')
        self.assertTrue(self.inst.is_active)

    def test_02_accounts_belong_to_installation(self):
        """Test 2: All 3 accounts are properly linked to the installation."""
        accounts = Account.objects.filter(installation=self.inst)
        self.assertEqual(accounts.count(), 3)
        self.assertEqual(set(accounts.values_list('code', flat=True)), {'QPF', 'PPF', 'AHF'})

    def test_03_account_isolation(self):
        """Test 3: Operational records are strictly isolated by account FK."""
        # Create a head on PPF
        ppf_head = AccountHead.objects.create(
            account=self.ppf,
            code='PPF-01',
            name='Parade Uniforms'
        )

        qpf_heads = AccountHead.objects.filter(account=self.qpf)
        ppf_heads = AccountHead.objects.filter(account=self.ppf)

        self.assertNotIn(ppf_head, qpf_heads)
        self.assertIn(ppf_head, ppf_heads)
        self.assertEqual(ppf_heads.count(), 1)

    def test_04_qpf_seed_integrity(self):
        """Test 4: Exactly 24 Account Heads exist for QPF."""
        qpf_count = AccountHead.objects.filter(account=self.qpf).count()
        self.assertEqual(qpf_count, 24)

    def test_05_ppf_and_ahf_have_zero_qpf_heads(self):
        """Test 5: PPF and AHF do not inherit any of QPF's 24 heads."""
        ppf_count = AccountHead.objects.filter(account=self.ppf).count()
        ahf_count = AccountHead.objects.filter(account=self.ahf).count()
        self.assertEqual(ppf_count, 0)
        self.assertEqual(ahf_count, 0)

    def test_06_protected_deletion_of_referenced_masters(self):
        """Test 9: Account with dependent AccountHeads cannot be destructively deleted."""
        with self.assertRaises(ProtectedError):
            self.qpf.delete()

    def test_07_account_context_middleware_default(self):
        """Test 12: Account Context Middleware defaults to QPF."""
        self.client.login(username='clerk_test', password='pass123')
        response = self.client.get(reverse('core:home'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['current_account'].code, 'QPF')
        self.assertEqual(response.context['current_fy'].code, '2026-27')

    def test_08_account_context_switching(self):
        """Test 12: Switching account via session updates active context."""
        self.client.login(username='admin_test', password='pass123')
        switch_url = reverse('accounts:switch_account', args=[self.ppf.id])
        response = self.client.get(switch_url, HTTP_REFERER=reverse('core:home'), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['current_account'].code, 'PPF')
