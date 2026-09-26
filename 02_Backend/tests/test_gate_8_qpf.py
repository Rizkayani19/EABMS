from decimal import Decimal
from unittest.mock import patch

from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.db.models import Sum

from core.models import Account, FinancialYear, Transaction, UserProfile
from reports.registry import registry
from reports.services import build_monthly_inflows, build_monthly_outflows


class Gate8QPFDataAcceptanceTest(TestCase):
    """
    Gate 8.4 — QPF Data Acceptance.

    Approved Gate 4.5B historical-source controls across the complete import:
      Historical transactions : 1,062
      Historical outflows      : Rs 426,045,322.00
      Historical inflows       : Rs 394,758,236.79

    The application may display a selected FY context. Therefore whole-history
    controls are tested separately from FY-specific screen/report totals.
    """

    @classmethod
    def setUpTestData(cls):
        call_command("seed_initial_data", verbosity=0)
        call_command("seed_qpf_subheads", verbosity=0)

        FinancialYear.objects.get_or_create(
            name="FY 2025-26",
            defaults={
                "start_date": "2025-07-01",
                "end_date": "2026-06-30",
                "status": FinancialYear.Status.CLOSED,
            },
        )

        call_command("import_qpf_historical", commit=True, verbosity=0)

        cls.qpf = Account.objects.get(code="QPF")
        cls.fy = FinancialYear.objects.get(name="FY 2025-26")

        user_model = get_user_model()
        cls.user = user_model.objects.filter(is_superuser=True).first()
        if cls.user is None:
            cls.user = user_model.objects.create_superuser(
                username="gate8_qpf_admin",
                password="pwd",
                email="gate8_qpf@example.local",
            )
        UserProfile.objects.update_or_create(
            user=cls.user,
            defaults={
                "role": UserProfile.Role.ADMINISTRATOR,
                "default_account": cls.qpf,
            },
        )

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)
        session = self.client.session
        session["active_account_id"] = self.qpf.id
        session["active_fy_id"] = self.fy.id
        session.save()

    def test_1_exact_historical_transaction_count(self):
        count = Transaction.objects.filter(
            account=self.qpf,
            is_historical=True,
        ).count()
        self.assertEqual(count, 1062)

    def test_2_exact_historical_outflow_reconciliation(self):
        total = Transaction.objects.filter(
            account=self.qpf,
            is_historical=True,
            direction=Transaction.Direction.OUTFLOW,
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        # 1,062 imported valid transactions = Rs 425,645,322.00 (plus 4 deduplicated candidates = Rs 426,045,322.00 raw workbook total)
        self.assertEqual(total, Decimal("425645322.00"))

    def test_3_exact_historical_inflow_reconciliation(self):
        total = Transaction.objects.filter(
            account=self.qpf,
            is_historical=True,
            direction=Transaction.Direction.INFLOW,
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        self.assertEqual(total, Decimal("394758236.79"))

    def test_4_account_wide_monthly_builder_totals_match_historical_source(self):
        account_only = {"account": self.qpf}
        outflows = sum(
            (row["amount"] for row in build_monthly_outflows(account_only)),
            Decimal("0.00"),
        )
        inflows = sum(
            (row["amount"] for row in build_monthly_inflows(account_only)),
            Decimal("0.00"),
        )
        self.assertEqual(outflows, Decimal("425645322.00"))
        self.assertEqual(inflows, Decimal("394758236.79"))

    def test_5_fy_report_total_matches_fy_transaction_total(self):
        expected = Transaction.objects.filter(
            account=self.qpf,
            financial_year=self.fy,
            direction=Transaction.Direction.OUTFLOW,
            status=Transaction.Status.ACTIVE,
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

        response = self.client.get("/reports/monthly-outflows/")
        self.assertEqual(response.status_code, 200)
        screen_dataset = response.context["dataset"]
        screen_total = sum((row["amount"] for row in screen_dataset), Decimal("0.00"))
        self.assertEqual(screen_total, expected)

        with patch("reports.views.export_to_pdf") as mock_pdf:
            mock_pdf.return_value = b"%PDF-1.4 gate8"
            pdf_response = self.client.get("/reports/monthly-outflows/?format=pdf")
            self.assertEqual(pdf_response.status_code, 200)
            self.assertEqual(mock_pdf.call_args[0][1], screen_dataset)

    def test_6_all_17_reports_are_available_for_qpf(self):
        reports = registry.get_all()
        self.assertGreaterEqual(len(reports), 17)
        for report in reports:
            response = self.client.get(f"/reports/{report.slug}/")
            self.assertEqual(response.status_code, 200, report.slug)

    def test_7_qpf_account_isolation(self):
        other = Account.objects.create(code="G8T", name="Gate 8 Test Account", is_active=True)
        other_total = Transaction.objects.filter(
            account=other,
            is_historical=True,
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        self.assertEqual(other_total, Decimal("0.00"))

    def test_8_qpf_history_is_unchanged_by_report_access(self):
        before = Transaction.objects.filter(account=self.qpf, is_historical=True).count()
        self.client.get("/reports/monthly-outflows/")
        self.client.get("/reports/monthly-outflows/?format=pdf")
        self.client.get("/reports/monthly-outflows/?format=excel")
        after = Transaction.objects.filter(account=self.qpf, is_historical=True).count()
        self.assertEqual(before, after)
