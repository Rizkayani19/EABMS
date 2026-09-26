from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class Gate18TargetProfileTests(SimpleTestCase):
    def setUp(self):
        self.root = Path(settings.BASE_DIR).parent
        self.windows = self.root / "DEPLOYMENT" / "Windows"

    def test_target_hardware_profile_exists(self):
        profile = self.windows / "ABMS_Target_Hardware_Profile.md"
        text = profile.read_text(encoding="utf-8")
        self.assertIn("Windows 10 64-bit", text)
        self.assertIn("Intel Core i5, 2nd Generation", text)
        self.assertIn("4 GB RAM", text)
        self.assertIn("256 GB HDD", text)
        self.assertIn("Air-gapped / offline", text)

    def test_gate18_acceptance_document_exists(self):
        acceptance = self.root / "RELEASE" / "Gate_18_Low_Spec_Windows_Deployment.md"
        text = acceptance.read_text(encoding="utf-8")
        self.assertIn("Windows 10 64-bit", text)
        self.assertIn("Intel Core i5, 2nd Generation", text)
        self.assertIn("4 GB RAM", text)
        self.assertIn("256 GB HDD", text)
        self.assertIn("Internet access is not required", text)
        self.assertIn("Mass / Bulk Grid", text)
        self.assertIn("Transaction Date", text)

    def test_target_check_and_installer_are_connected(self):
        checker = (self.windows / "Check-ABMS-Target.ps1").read_text(encoding="utf-8")
        installer = (self.windows / "Install-ABMS.ps1").read_text(encoding="utf-8")
        self.assertIn("MinimumMemoryGB", checker)
        self.assertIn("MinimumFreeDiskGB", checker)
        self.assertIn("64-bit", checker)
        self.assertIn("-MinimumMemoryGB 4", installer)
        self.assertIn("-MinimumFreeDiskGB 10", installer)
        self.assertIn("Check-ABMS-Target.ps1", installer)
