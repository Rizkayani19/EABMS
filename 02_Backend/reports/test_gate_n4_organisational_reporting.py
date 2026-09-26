from decimal import Decimal

from django.test import TestCase

from core.models import Account, AccountHead, FinancialYear, Transaction, Unit
from masters.models import InternalSection, TransactionOrganisationAllocation
from reports.organisational import build_organisational_transactions, build_unit_section_summary, build_unit_summary, build_internal_section_summary


class GateN4OrganisationalReportingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.account = Account.objects.create(code="N4", name="N4 Test Account")
        cls.fy = FinancialYear.objects.create(code="N4-2026", name="FY N4 2026", start_date="2026-07-01", end_date="2027-06-30", status=FinancialYear.Status.OPEN)
        cls.head = AccountHead.objects.create(account=cls.account, code="N4-H", name="N4 Test Head", head_type=AccountHead.HeadType.OUTFLOW)
        cls.asm = Unit.objects.get_or_create(name="ASM", defaults={"code": "N4-ASM"})[0]
        cls.unit45 = Unit.objects.get_or_create(name="Unit 45", defaults={"code": "N4-U45"})[0]
        cls.ps3 = InternalSection.objects.get_or_create(name="PS-3", defaults={"code": "N4-PS3"})[0]
        cls.hqpm = InternalSection.objects.get_or_create(name="HQ PM", defaults={"code": "N4-HQPM"})[0]

    def make_tx(self, number, amount):
        return Transaction.objects.create(transaction_number=number, account=self.account, financial_year=self.fy, account_head=self.head, transaction_date="2026-08-01", direction=Transaction.Direction.OUTFLOW, amount=amount, status=Transaction.Status.ACTIVE)

    def test_unit_summary_uses_allocated_amount_not_transaction_amount(self):
        tx = self.make_tx("N4-001", Decimal("1000.00")); TransactionOrganisationAllocation.objects.create(transaction=tx, unit=self.asm, internal_section=self.ps3, allocated_amount=Decimal("600.00")); TransactionOrganisationAllocation.objects.create(transaction=tx, unit=self.unit45, internal_section=self.ps3, allocated_amount=Decimal("400.00"))
        rows = build_unit_summary({"account": self.account, "financial_year": self.fy}); amounts = {r["unit"]: r["amount"] for r in rows}
        self.assertEqual(amounts["ASM"], Decimal("600.00")); self.assertEqual(amounts["Unit 45"], Decimal("400.00")); self.assertEqual(sum(amounts.values()), Decimal("1000.00"))

    def test_combined_unit_section_is_explicit_and_does_not_double_count(self):
        tx = self.make_tx("N4-002", Decimal("1000.00"));
        for unit, section, amount in [(self.asm, self.ps3, Decimal("600.00")), (self.unit45, self.ps3, Decimal("250.00")), (self.unit45, self.hqpm, Decimal("150.00"))]: TransactionOrganisationAllocation.objects.create(transaction=tx, unit=unit, internal_section=section, allocated_amount=amount)
        rows = build_unit_section_summary({"account": self.account, "financial_year": self.fy}); lookup = {(r["unit"], r["internal_section"]): r["amount"] for r in rows}
        self.assertEqual(lookup[("ASM", "PS-3")], Decimal("600.00")); self.assertEqual(lookup[("Unit 45", "PS-3")], Decimal("250.00")); self.assertEqual(lookup[("Unit 45", "HQ PM")], Decimal("150.00")); self.assertEqual(sum(r["amount"] for r in rows), Decimal("1000.00"))

    def test_section_filter_selects_allocations_even_when_transaction_has_multiple_units(self):
        tx = self.make_tx("N4-003", Decimal("1000.00")); TransactionOrganisationAllocation.objects.create(transaction=tx, unit=self.asm, internal_section=self.ps3, allocated_amount=Decimal("700.00")); TransactionOrganisationAllocation.objects.create(transaction=tx, unit=self.unit45, internal_section=self.hqpm, allocated_amount=Decimal("300.00"))
        rows = build_organisational_transactions({"account": self.account, "financial_year": self.fy, "internal_section_ids": [self.ps3.pk]}); self.assertEqual(len(rows), 1); self.assertEqual(rows[0]["amount"], Decimal("700.00")); self.assertEqual(rows[0]["internal_section"], "PS-3")

    def test_unit_filter_selects_only_requested_units(self):
        tx = self.make_tx("N4-004", Decimal("1000.00")); TransactionOrganisationAllocation.objects.create(transaction=tx, unit=self.asm, internal_section=self.ps3, allocated_amount=Decimal("700.00")); TransactionOrganisationAllocation.objects.create(transaction=tx, unit=self.unit45, internal_section=self.ps3, allocated_amount=Decimal("300.00"))
        rows = build_organisational_transactions({"account": self.account, "financial_year": self.fy, "unit_ids": [self.asm.pk]}); self.assertEqual(len(rows), 1); self.assertEqual(rows[0]["unit"], "ASM"); self.assertEqual(rows[0]["amount"], Decimal("700.00"))

    def test_section_summary_uses_allocation_grain(self):
        tx = self.make_tx("N4-005", Decimal("1000.00")); TransactionOrganisationAllocation.objects.create(transaction=tx, unit=self.asm, internal_section=self.ps3, allocated_amount=Decimal("800.00")); TransactionOrganisationAllocation.objects.create(transaction=tx, unit=self.unit45, internal_section=self.hqpm, allocated_amount=Decimal("200.00"))
        rows = build_internal_section_summary({"account": self.account, "financial_year": self.fy}); amounts = {r["internal_section"]: r["amount"] for r in rows}
        self.assertEqual(amounts["PS-3"], Decimal("800.00")); self.assertEqual(amounts["HQ PM"], Decimal("200.00"))
