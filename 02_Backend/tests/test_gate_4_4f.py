from django.test import TestCase
from django.core.management import call_command
from core.models import Account, MajorHead, SubHead, AccountHead

class Gate4_4f_Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_initial_data', verbosity=0)
        call_command('seed_qpf_subheads', verbosity=0)

    def test_exactly_59_qpf_subheads(self):
        qpf = Account.objects.get(code='QPF')
        count = SubHead.objects.filter(account=qpf).count()
        self.assertEqual(count, 59, "Exactly 59 Sub Heads should exist for QPF.")

    def test_ppf_has_zero_subheads(self):
        ppf = Account.objects.get(code='PPF')
        count = SubHead.objects.filter(account=ppf).count()
        self.assertEqual(count, 0, "PPF should have zero Sub Heads.")

    def test_ahf_has_zero_subheads(self):
        ahf = Account.objects.get(code='AHF')
        count = SubHead.objects.filter(account=ahf).count()
        self.assertEqual(count, 0, "AHF should have zero Sub Heads.")

    def test_every_subhead_has_one_major_head(self):
        qpf = Account.objects.get(code='QPF')
        subheads = SubHead.objects.filter(account=qpf)
        for sh in subheads:
            self.assertIsNotNone(sh.major_head, f"SubHead {sh.name} missing MajorHead.")
            self.assertEqual(sh.major_head.account, qpf, f"SubHead {sh.name} has wrong account on its MajorHead.")

    def test_no_duplicate_subhead_names(self):
        qpf = Account.objects.get(code='QPF')
        names = list(SubHead.objects.filter(account=qpf).values_list('name', flat=True))
        self.assertEqual(len(names), len(set(names)), "Duplicate Sub Head names found.")

    def test_non_subhead_concepts_absent(self):
        qpf = Account.objects.get(code='QPF')
        names = list(SubHead.objects.filter(account=qpf).values_list('name', flat=True))
        forbidden = [
            'Pass Through', 'Unit 45', '29 MP', 'Receipt from SIB',
            'Reimbursement', 'Routine', 'Addl', 'Misc-Unit 45 Expenditure'
        ]
        for f in forbidden:
            self.assertNotIn(f, names, f"Forbidden non-sub-head concept '{f}' found in Sub Heads.")

    def test_seeder_is_idempotent(self):
        qpf = Account.objects.get(code='QPF')
        initial_count = SubHead.objects.filter(account=qpf).count()
        call_command('seed_qpf_subheads', verbosity=0)
        final_count = SubHead.objects.filter(account=qpf).count()
        self.assertEqual(initial_count, final_count, "Seeder is not idempotent.")
