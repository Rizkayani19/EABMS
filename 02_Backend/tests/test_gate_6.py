from django.test import TestCase
from django.core.management import call_command
from django.urls import reverse
from core.models import Account, FinancialYear, UserProfile
from django.contrib.auth.models import User
from core.dashboard_services import get_dashboard_data
from reports.services import build_consolidated

class Gate6DashboardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_initial_data')
        # Create FY 2025-26 if it does not exist
        from datetime import date
        FinancialYear.objects.get_or_create(code='2025-26', defaults={
            'name': 'FY 2025-26', 'start_date': date(2025, 7, 1), 'end_date': date(2026, 6, 30), 'status': 'OPEN'
        })
        
        call_command('import_qpf_historical', commit=True)
        cls.account_qpf = Account.objects.get(code='QPF')
        cls.account_ahf = Account.objects.get(code='AHF')
        cls.fy_2025_26 = FinancialYear.objects.get(code='2025-26')
        
        cls.admin_user, _ = User.objects.get_or_create(username='admin', defaults={'password': 'password'})
        cls.admin_user.set_password('password')
        cls.admin_user.save()
        profile, _ = UserProfile.objects.get_or_create(user=cls.admin_user)
        profile.role = UserProfile.Role.ADMINISTRATOR
        profile.save()
            
        cls.clerk_user, _ = User.objects.get_or_create(username='clerk', defaults={'password': 'password'})
        cls.clerk_user.set_password('password')
        cls.clerk_user.save()
        profile, _ = UserProfile.objects.get_or_create(user=cls.clerk_user)
        profile.role = UserProfile.Role.CLERK
        profile.save()

    def test_dashboard_service_qpf(self):
        """Test get_dashboard_data returns correct schema and values for QPF."""
        data = get_dashboard_data(self.account_qpf, self.fy_2025_26)
        
        self.assertIn('opening_balance', data)
        self.assertIn('total_inflows', data)
        self.assertIn('total_outflows', data)
        self.assertIn('balance_available', data)
        
        self.assertTrue(data['opening_balance'] >= 0)
        self.assertTrue(data['total_inflows'] > 0)
        self.assertTrue(data['total_outflows'] > 0)
        
        expected_balance = data['opening_balance'] + data['total_inflows'] - data['total_outflows']
        self.assertEqual(data['balance_available'], expected_balance)
        
        if data['approved_budget']:
            expected_util = (data['budget_consumed'] / data['approved_budget']) * 100
            self.assertAlmostEqual(data['budget_utilisation'], expected_util, places=2)
            
        self.assertIsInstance(data['alerts'], list)
        self.assertIsInstance(data['monthly_trend'], list)
        self.assertIsInstance(data['top_budget_heads'], list)

    def test_dashboard_service_ahf_zero(self):
        """Test zero-data accounts."""
        data = get_dashboard_data(self.account_ahf, self.fy_2025_26)
        self.assertEqual(data['total_inflows'], 0)
        self.assertEqual(data['total_outflows'], 0)
        self.assertEqual(data['budget_consumed'], 0)
        self.assertEqual(data['this_month_inflows'], 0)
        self.assertEqual(data['this_month_outflows'], 0)

    def test_consolidated_service(self):
        filters = {'financial_year': self.fy_2025_26}
        res = build_consolidated(filters)
        self.assertTrue(len(res) >= 3)
        codes = [r['account'] for r in res]
        self.assertIn('Quaid Portrait Fund', codes)

    def test_dashboard_view_qpf(self):
        """Test the home view renders dashboard data for QPF."""
        self.client.login(username='admin', password='password')
        response = self.client.get(reverse('core:home') + f'?account=QPF&fy={self.fy_2025_26.code}')
        self.assertEqual(response.status_code, 200)
        
        self.assertIn('opening_balance', response.context)
        self.assertIn('total_inflows', response.context)
        self.assertIn('total_outflows', response.context)
        
        self.assertContains(response, 'Total Inflows')
        self.assertContains(response, 'Balance Available')
        self.assertNotContains(response, 'Consolidated Management Overview')

    def test_dashboard_view_all_accounts_admin(self):
        """Test admin can see all accounts view."""
        self.client.login(username='admin', password='password')
        response = self.client.get(reverse('core:home') + f'?all_accounts=1&fy={self.fy_2025_26.code}')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context.get('all_accounts_view'))
        self.assertIn('consolidated_data', response.context)
        self.assertContains(response, 'Consolidated Management Overview')
        self.assertContains(response, 'Grand Total')

    def test_dashboard_view_all_accounts_clerk(self):
        """Test clerk cannot see all accounts view, fallback to normal."""
        self.client.login(username='clerk', password='password')
        response = self.client.get(reverse('core:home') + f'?all_accounts=1&fy={self.fy_2025_26.code}')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context.get('all_accounts_view'))
        self.assertNotIn('consolidated_data', response.context)
        self.assertNotContains(response, 'Consolidated Management Overview')
