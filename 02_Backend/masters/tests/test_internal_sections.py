from django.test import TestCase

from core.models import Unit
from masters.models import InternalSection, UnitSectionResponsibility


class InternalSectionMasterTests(TestCase):
    def test_seeded_sections_exist_after_migration(self):
        self.assertEqual(InternalSection.objects.count(), 11)
        self.assertTrue(InternalSection.objects.filter(code='PS-COORD', name='PS Coord').exists())
        self.assertTrue(InternalSection.objects.filter(code='PS-6').exists())
        self.assertTrue(InternalSection.objects.filter(code='CMTF').exists())
        self.assertTrue(InternalSection.objects.filter(code='DMC').exists())

    def test_unit_can_have_multiple_responsible_sections(self):
        unit = Unit.objects.create(code='TEST-UNIT', name='Test Unit')
        ps3 = InternalSection.objects.get(code='PS-3')
        pscoord = InternalSection.objects.get(code='PS-COORD')

        UnitSectionResponsibility.objects.create(unit=unit, section=ps3, is_primary=True)
        UnitSectionResponsibility.objects.create(unit=unit, section=pscoord, is_primary=False)

        self.assertEqual(unit.section_responsibilities.count(), 2)
        # Other seeded Units may already be managed by these Sections; scope the
        # assertion to the Unit created by this test.
        self.assertEqual(ps3.unit_responsibilities.filter(unit=unit).count(), 1)
        self.assertEqual(pscoord.unit_responsibilities.filter(unit=unit).count(), 1)

    def test_unit_without_responsible_section_is_allowed(self):
        unit = Unit.objects.create(code='UNASSIGNED', name='Unassigned Unit')
        self.assertEqual(unit.section_responsibilities.count(), 0)
