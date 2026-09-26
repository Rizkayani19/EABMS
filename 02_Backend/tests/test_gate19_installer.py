from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class Gate19InstallerContractTests(SimpleTestCase):
    def setUp(self):
        self.root = Path(settings.BASE_DIR).parent
        self.windows = self.root / "DEPLOYMENT" / "Windows"

    def test_inno_setup_definition_exists(self):
        iss = (self.windows / "ABMS_Setup.iss").read_text(encoding="utf-8")
        self.assertIn('#define AppName "ABMS"', iss)
        self.assertIn("AppName={#AppName}", iss)
        self.assertIn("OutputBaseFilename=ABMS_Setup_v", iss)
        self.assertIn("python-3.13.15-amd64.exe", iss)
        self.assertIn("postgresql-17.11-1-windows-x64.exe", iss)
        self.assertIn("Start-ABMS.cmd", iss)
        self.assertIn("Initialize-ABMS.cmd", iss)

    def test_first_run_setup_is_offline_and_database_driven(self):
        script = (self.windows / "Initialize-ABMS.ps1").read_text(encoding="utf-8")
        self.assertIn("--no-index", script)
        self.assertIn("abms_app", script)
        self.assertIn("abms_db", script)
        self.assertIn("DJANGO_SECRET_KEY", script)
        self.assertIn("abms_preflight", script)
        self.assertIn("abms_uat_preflight", script)

    def test_build_workflow_contains_windows_installer_steps(self):
        workflow = (self.root / ".github" / "workflows" / "build-windows-installer.yml").read_text(encoding="utf-8")
        self.assertIn("windows-latest", workflow)
        self.assertIn("3.13.15", workflow)
        self.assertIn("postgresql-17.11-1-windows-x64.exe", workflow)
        self.assertIn("innosetup", workflow.lower())
        self.assertIn("SHA256SUMS.txt", workflow)
        # Installer delivery is intentionally via GitHub Release assets because
        # Actions artifact storage is quota-exhausted in the current repository.
        self.assertIn("softprops/action-gh-release", workflow)
        self.assertIn("RELEASE/Installer/*.exe", workflow)

    def test_gate19_acceptance_document_exists(self):
        doc = (self.root / "RELEASE" / "Gate_19_One_Click_Windows_Installer.md").read_text(encoding="utf-8")
        self.assertIn("Windows 10 64-bit", doc)
        self.assertIn("4 GB RAM", doc)
        self.assertIn("ABMS_Setup_v1.0.0.exe", doc)
        self.assertIn("network disconnected", doc)
        self.assertIn("Transaction Date", doc)
