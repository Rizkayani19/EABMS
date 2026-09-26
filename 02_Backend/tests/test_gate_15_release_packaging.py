from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class Gate15ReleasePackagingTests(SimpleTestCase):
    def setUp(self):
        self.root = Path(settings.BASE_DIR).parent

    def test_runtime_and_dev_manifests_exist(self):
        runtime = Path(settings.BASE_DIR) / "requirements-runtime.txt"
        dev = Path(settings.BASE_DIR) / "requirements-dev.txt"
        self.assertTrue(runtime.is_file())
        self.assertTrue(dev.is_file())
        runtime_text = runtime.read_text(encoding="utf-8")
        self.assertIn("Django==6.0.2", runtime_text)
        self.assertIn("psycopg2-binary==2.9.11", runtime_text)
        self.assertIn("waitress==3.0.2", runtime_text)
        self.assertNotIn("weasyprint", runtime_text.lower())

    def test_offline_windows_package_files_exist(self):
        paths = [
            self.root / "DEPLOYMENT" / "Windows" / "Install-ABMS.ps1",
            self.root / "DEPLOYMENT" / "Windows" / "Start-ABMS.ps1",
            self.root / "DEPLOYMENT" / "Windows" / "Prepare-ABMS-OfflineBundle.ps1",
            self.root / "DEPLOYMENT" / "Windows" / "New-ABMS-SHA256Manifest.ps1",
            self.root / "DEPLOYMENT" / "Windows" / "ABMS_Offline_Deployment.md",
            self.root / "RELEASE" / "ABMS_Release_Checklist.md",
            Path(settings.BASE_DIR) / ".env.example",
        ]
        for path in paths:
            self.assertTrue(path.is_file(), f"Missing release file: {path}")

    def test_install_script_is_offline(self):
        script = (self.root / "DEPLOYMENT" / "Windows" / "Install-ABMS.ps1").read_text(encoding="utf-8")
        self.assertIn("--no-index", script)
        self.assertIn("--find-links", script)
        self.assertIn("abms_uat_preflight", script)

    def test_env_template_is_safe(self):
        env = (Path(settings.BASE_DIR) / ".env.example").read_text(encoding="utf-8")
        self.assertIn("DJANGO_DEBUG=False", env)
        self.assertIn("DJANGO_ALLOWED_HOSTS=", env)
        self.assertIn("REPLACE_WITH_A_LONG_RANDOM_SECRET", env)
        self.assertIn("REPLACE_WITH_DATABASE_PASSWORD", env)
