from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from core.models import Installation, Account, FinancialYear, Unit, AccountHead, UserProfile
from datetime import date


class MastersAndCRUDTests(TestCase):
    """Gate 1.5 master CRUD and lifecycle tests against the current URL contracts."""

    def setUp(self):
        self.inst = Installation.objects.create(installation_code='INST-01', installation_name='Main Installation')
        self.qpf = Account.objects.create(installation=self.inst, code='QPF', name='Quaid Portrait Fund', display_order=1)
        self.fy = FinancialYear.objects.create(
            code='2026-27', name='FY 2026-27', start_date=date(2026, 7, 1), end_date=date(2027, 6, 30), status=FinancialYear.Status.OPEN
        )
        self.head = AccountHead.objects.create(
            account=self.qpf, code='QPF-01', name='Utility / Maint', head_type=AccountHead.HeadType.OUTFLOW, is_active=True
        )
        self.unit = Unit.objects.create(code='TEST-UNIT-45', name='Test Unit 45', is_active=True)
        self.admin = User.objects.create_superuser('admin_user', 'admin@abms.test', 'pass123')
        UserProfile.objects.create(user=self.admin, role=UserProfile.Role.ADMINISTRATOR, default_account=self.qpf)
        self.clerk = User.objects.create_user('clerk_user', 'clerk@abms.test', 'pass123')
        UserProfile.objects.create(user=self.clerk, role=UserProfile.Role.CLERK, default_account=self.qpf)
        self.mgmt = User.objects.create_user('mgmt_user', 'mgmt@abms.test', 'pass123')
        UserProfile.objects.create(user=self.mgmt, role=UserProfile.Role.MANAGEMENT, default_account=self.qpf)
        self.client = Client()

    def test_01_master_creation_via_view(self):
        self.client.login(username='admin_user', password='pass123')
        response = self.client.post(reverse('masters:account_head_create'), {
            'account': self.qpf.id, 'code': 'QPF-99', 'name': 'Test New Head', 'head_type': 'OUTFLOW', 'display_order': 99, 'is_active': True,
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(AccountHead.objects.filter(code='QPF-99', name='Test New Head').exists())

    def test_02_master_editing_via_view(self):
        self.client.login(username='admin_user', password='pass123')
        response = self.client.post(reverse('masters:account_head_update', args=[self.head.id]), {
            'account': self.qpf.id, 'code': 'QPF-01', 'name': 'Utility / Maintenance Updated', 'head_type': 'OUTFLOW', 'display_order': 1, 'is_active': True,
        })
        self.assertEqual(response.status_code, 302)
        self.head.refresh_from_db()
        self.assertEqual(self.head.name, 'Utility / Maintenance Updated')

    def test_03_master_toggle_active_htmx(self):
        self.client.login(username='admin_user', password='pass123')
        response = self.client.post(reverse('masters:account_head_toggle_active', args=[self.head.id]))
        self.assertIn(response.status_code, (200, 302))
        self.head.refresh_from_db()
        self.assertFalse(self.head.is_active)

    def test_04_financial_year_lifecycle(self):
        self.client.login(username='admin_user', password='pass123')
        response = self.client.post(reverse('masters:fy_toggle', args=[self.fy.id]))
        self.assertIn(response.status_code, (200, 302))
        self.fy.refresh_from_db()
        self.assertNotEqual(self.fy.status, FinancialYear.Status.OPEN)

    def test_05_unit_master_crud(self):
        self.assertEqual(self.unit.name, 'Test Unit 45')
        self.unit.is_active = False
        self.unit.save(update_fields=['is_active'])
        self.unit.refresh_from_db()
        self.assertFalse(self.unit.is_active)

    def test_06_unauthenticated_redirects_to_login(self):
        response = self.client.get(reverse('masters:account_head_list'))
        self.assertIn(response.status_code, (301, 302))
