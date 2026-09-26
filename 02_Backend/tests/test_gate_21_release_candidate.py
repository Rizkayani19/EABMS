from pathlib import Path

from django.test import SimpleTestCase


class Gate21ReleaseCandidateTests(SimpleTestCase):
    def setUp(self):
        self.repo_root = Path(__file__).resolve().parents[2]

    def test_release_manifest_exists_and_identifies_target(self):
        path = self.repo_root / "RELEASE" / "ABMS_RELEASE_CANDIDATE_MANIFEST_V1.0.0.md"
        self.assertTrue(path.exists())
        text = path.read_text(encoding="utf-8")
        self.assertIn("Offline Windows operational release candidate", text)
        self.assertIn("Windows 10 64-bit", text)
        self.assertIn("Intel Core i5, 2nd Generation", text)
        self.assertIn("4 GB RAM", text)
        self.assertIn("256 GB HDD", text)
        self.assertIn("Air-gapped / offline", text)

    def test_handover_checklist_exists_and_covers_core_acceptance(self):
        path = self.repo_root / "RELEASE" / "ABMS_OPERATIONAL_HANDOVER_CHECKLIST_V1.0.md"
        self.assertTrue(path.exists())
        text = path.read_text(encoding="utf-8")
        for required in (
            "First Installation",
            "Administrator Acceptance",
            "Clerk Acceptance",
            "Management Acceptance",
            "Backup Acceptance",
            "Restore Acceptance",
            "Final Handover Record",
        ):
            self.assertIn(required, text)
