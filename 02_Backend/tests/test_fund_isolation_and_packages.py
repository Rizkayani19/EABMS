import pytest
from decimal import Decimal
from django.test import Client, TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from core.models import Account, FinancialYear, Transaction, MajorHead, SubHead, AccountHead
from masters.models import Contingent, ContingentPackage, Pilgrim, TourOperator, City, ParadeVenue, ParadeEvent


class FundIsolationAndPackageTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username='admin_test',
            password='testpassword123',
            email='admin@example.com'
        )
        self.client = Client()
        self.client.force_login(self.user)

        self.account_qpf, _ = Account.objects.get_or_create(code='QPF', defaults={'name': 'Quaid Portrait Fund'})
        self.account_ppf, _ = Account.objects.get_or_create(code='PPF', defaults={'name': 'Pakistan Parade Fund'})
        self.account_ahf, _ = Account.objects.get_or_create(code='AHF', defaults={'name': 'Army Haj & Umra Fund'})

        self.fy, _ = FinancialYear.objects.get_or_create(
            code='2025-26',
            defaults={'name': 'FY 2025-26', 'start_date': '2025-07-01', 'end_date': '2026-06-30', 'status': FinancialYear.Status.OPEN}
        )

        # Create Haj Contingent & Package
        self.contingent = Contingent.objects.create(
            account=self.account_ahf,
            contingent_type=Contingent.ContingentType.HAJ,
            code='AHC-2027',
            title='Army Haj Contingent 2027',
            cycle_label='2027'
        )
        self.package = ContingentPackage.objects.create(
            contingent=self.contingent,
            package_code='AHC-2027-ECO',
            package_name='Economy Package 2027',
            total_days=40,
            airline='Saudia',
            medina_days=8,
            medina_hotel_name='Leader Al Muna Kareem',
            makkah_p1_days=7,
            makkah_p1_hotel_name='Swissotel Al Maqam',
            makkah_p2_days=5,
            makkah_p2_building_name='Azizia Building A-3',
            mashair_days=5,
            mina_maktab='Maktab 12',
            mina_zone='Zone 1',
            rate_double_sharing=Decimal('1250000.00'),
            rate_triple_sharing=Decimal('1150000.00'),
            rate_quad_sharing=Decimal('1050000.00')
        )

    def test_package_detail_view_renders_200(self):
        url = reverse('masters:package_detail', kwargs={'pk': self.package.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Economy Package 2027')
        self.assertContains(response, 'AHC-2027-ECO')
        self.assertContains(response, 'Swissotel Al Maqam')
        self.assertContains(response, 'Azizia Building A-3')
        self.assertContains(response, 'Leader Al Muna Kareem')
        self.assertContains(response, 'Maktab 12')

    def test_package_rates_api_quad_sharing(self):
        url = reverse('masters:package_rates_api')
        response = self.client.get(url, {'package_id': self.package.pk, 'sharing_type': 'QUAD', 'persons': 2})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['package_code'], 'AHC-2027-ECO')
        self.assertEqual(data['selected_rate'], 1050000.0)
        self.assertEqual(data['calculated_total'], 2100000.0)

    def test_package_rates_api_double_sharing(self):
        url = reverse('masters:package_rates_api')
        response = self.client.get(url, {'package_id': self.package.pk, 'sharing_type': 'DOUBLE', 'persons': 1})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['selected_rate'], 1250000.0)
        self.assertEqual(data['calculated_total'], 1250000.0)

    def test_packages_for_contingent_htmx_endpoint(self):
        url = reverse('masters:packages_for_contingent')
        response = self.client.get(url, {'contingent': self.contingent.pk})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.package.package_code)
        self.assertContains(response, self.package.package_name)

    def test_pilgrim_auto_calculation_on_clean(self):
        from masters.forms import PilgrimForm
        form_data = {
            'account': self.account_ahf.pk,
            'contingent': self.contingent.pk,
            'package': self.package.pk,
            'sub_fund': 'HAJ',
            'sharing_type': 'TRIPLE',
            'family_members_count': 3,
            'army_no': 'PA-12345',
            'rank_and_name': 'Col Ahmed Khan',
            'cnic': '37405-1234567-1',
            'is_active': True,
        }
        form = PilgrimForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)
        pilgrim = form.save()
        expected_cost = Decimal('1150000.00') * 3
        self.assertEqual(pilgrim.total_package_cost, expected_cost)

    def test_pass_through_allowed_on_both_directions(self):
        major = MajorHead.objects.create(account=self.account_qpf, code='M-01', name='Admin')
        sub = SubHead.objects.create(account=self.account_qpf, major_head=major, code='S-01', name='General')
        ah = AccountHead.objects.create(account=self.account_qpf, sub_head=sub, code='AH-01', name='Transfers')

        # Outflow pass-through
        tx_out = Transaction(
            account=self.account_qpf,
            financial_year=self.fy,
            transaction_number='TX-PT-001',
            transaction_date='2025-08-01',
            direction='OUTFLOW',
            amount=Decimal('50000.00'),
            account_head=ah,
            pass_through=True,
            description='Test PT Outflow'
        )
        tx_out.full_clean()
        tx_out.save()
        self.assertTrue(tx_out.pass_through)

        # Inflow pass-through
        tx_in = Transaction(
            account=self.account_qpf,
            financial_year=self.fy,
            transaction_number='TX-PT-002',
            transaction_date='2025-08-02',
            direction='INFLOW',
            amount=Decimal('50000.00'),
            account_head=ah,
            pass_through=True,
            description='Test PT Inflow'
        )
        tx_in.full_clean()
        tx_in.save()
        self.assertTrue(tx_in.pass_through)

    def test_sidebar_fund_isolation(self):
        # QPF session
        session = self.client.session
        session['active_account_id'] = self.account_qpf.pk
        session.save()
        r_qpf = self.client.get(reverse('core:home'))
        self.assertEqual(r_qpf.status_code, 200)
        # Should not have Haj Pilgrims or Parade Venues in QPF
        self.assertNotContains(r_qpf, '/masters/pilgrims/')
        self.assertNotContains(r_qpf, '/masters/contingents/')
        self.assertNotContains(r_qpf, '/masters/parade-venues/')

        # AHF session
        session['active_account_id'] = self.account_ahf.pk
        session.save()
        r_ahf = self.client.get(reverse('core:home'))
        self.assertEqual(r_ahf.status_code, 200)
        self.assertContains(r_ahf, '/masters/contingents/')
        self.assertContains(r_ahf, '/masters/packages/')
        self.assertContains(r_ahf, '/masters/pilgrims/')
        self.assertNotContains(r_ahf, '/masters/parade-venues/')

        # PPF session
        session['active_account_id'] = self.account_ppf.pk
        session.save()
        r_ppf = self.client.get(reverse('core:home'))
        self.assertEqual(r_ppf.status_code, 200)
        self.assertContains(r_ppf, '/masters/parade-venues/')
        self.assertContains(r_ppf, '/masters/parade-events/')
        self.assertNotContains(r_ppf, '/masters/pilgrims/')

    def test_package_list_differentiates_umra_and_haj(self):
        # Create Umra Contingent & Package
        umra_contingent = Contingent.objects.create(
            account=self.account_ahf,
            contingent_type=Contingent.ContingentType.UMRA,
            code='AUC-01',
            title='Army Umra Contingent 01',
            cycle_label='2026'
        )
        umra_pkg = ContingentPackage.objects.create(
            contingent=umra_contingent,
            package_type=ContingentPackage.PackageType.UMRA,
            package_code='AUC-01-STD',
            package_name='Standard Umra Package 15D',
            total_days=15,
            medina_days=7,
            makkah_p1_days=8,
            mashair_days=0,
            rate_quad_sharing=Decimal('450000.00')
        )

        session = self.client.session
        session['active_account_id'] = self.account_ahf.pk
        session.save()

        # All packages
        r_all = self.client.get(reverse('masters:package_list'))
        self.assertEqual(r_all.status_code, 200)
        self.assertContains(r_all, 'AUC-01-STD')
        self.assertContains(r_all, 'AHC-2027-ECO')
        self.assertContains(r_all, 'UMRA PACKAGE')
        self.assertContains(r_all, 'HAJ PACKAGE')

        # Filter UMRA tab
        r_umra = self.client.get(reverse('masters:package_list') + '?package_type=UMRA')
        self.assertEqual(r_umra.status_code, 200)
        self.assertContains(r_umra, 'AUC-01-STD')
        self.assertNotContains(r_umra, 'AHC-2027-ECO')

        # Filter HAJ tab
        r_haj = self.client.get(reverse('masters:package_list') + '?package_type=HAJ')
        self.assertEqual(r_haj.status_code, 200)
        self.assertContains(r_haj, 'AHC-2027-ECO')
        self.assertNotContains(r_haj, 'AUC-01-STD')

    def test_package_copy_profile_creates_new_package(self):
        session = self.client.session
        session['active_account_id'] = self.account_ahf.pk
        session.save()

        copy_url = reverse('masters:package_copy', kwargs={'pk': self.package.pk})
        # GET should pre-populate
        r_get = self.client.get(copy_url)
        self.assertEqual(r_get.status_code, 200)
        self.assertContains(r_get, 'Cloning Package Profile')
        self.assertContains(r_get, 'AHC-2027-ECO-COPY')

        # POST should create new cloned package
        post_data = {
            'contingent': self.contingent.pk,
            'package_type': 'HAJ',
            'package_code': 'AHC-2027-CLONE-1',
            'package_name': 'Economy Package 2027 (Cloned)',
            'total_days': 40,
            'airline': 'Saudia',
            'flight_route': 'DIRECT',
            'flight_origin': 'Islamabad (ISB)',
            'flight_destination': 'Medina (MED) / Jeddah (JED)',
            'medina_order': 'BEFORE',
            'medina_days': 8,
            'medina_accn_type': 'HOTEL',
            'medina_hotel_name': 'Leader Al Muna Kareem',
            'medina_boarding': 'BB',
            'transfer_mode': 'TRAIN',
            'makkah_p1_days': 7,
            'makkah_p1_accn_type': 'HOTEL',
            'makkah_p1_hotel_name': 'Swissotel Al Maqam',
            'makkah_p1_boarding': 'BB',
            'makkah_p2_days': 5,
            'makkah_p2_accn_type': 'BUILDING',
            'makkah_p2_building_name': 'Azizia Building A-3',
            'makkah_p2_boarding': 'FB',
            'mashair_days': 5,
            'mina_maktab': 'Maktab 12',
            'mina_zone': 'Zone 1',
            'mashair_boarding': 'FB',
            'arafat_details': 'AC Marquees',
            'muzdalifah_details': 'Open air',
            'post_haj_days': 0,
            'rate_double_sharing': '1250000.00',
            'rate_triple_sharing': '1150000.00',
            'rate_quad_sharing': '1050000.00',
            'is_active': 'on'
        }
        r_post = self.client.post(copy_url, post_data)
        cloned_pkg = ContingentPackage.objects.filter(package_code='AHC-2027-CLONE-1').first()
        self.assertIsNotNone(cloned_pkg)
        self.assertEqual(cloned_pkg.package_name, 'Economy Package 2027 (Cloned)')
        self.assertEqual(cloned_pkg.rate_quad_sharing, Decimal('1050000.00'))
        self.assertRedirects(r_post, reverse('masters:package_detail', kwargs={'pk': cloned_pkg.pk}))
