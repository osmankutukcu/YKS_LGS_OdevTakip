# -*- coding: utf-8 -*-
"""Saf kaynak kontrolleri: veri, Qt veya ağ erişimi gerektirmez."""
import ast
import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def method_names(source_path, class_name):
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return {it.name for it in node.body if isinstance(it, (ast.FunctionDef, ast.AsyncFunctionDef))}
    return set()


class ReportCenterV3581SourceTests(unittest.TestCase):
    def setUp(self):
        self.code = (ROOT / "ui/report_center_v3581.py").read_text(encoding="utf-8")
        self.dashboard = (ROOT / "ui/report_dashboard.py").read_text(encoding="utf-8")
        tree = ast.parse(self.code)
        self.routes = None
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "REPORT_ROUTES" for t in node.targets):
                self.routes = ast.literal_eval(node.value)
                break

    def test_six_goals_are_connected_to_existing_methods(self):
        self.assertEqual(len(self.routes), 6)
        main_methods = method_names(ROOT / "main_window.py", "AnaPencere")
        self.assertTrue(main_methods, "MainWindow class missing")
        for r in self.routes:
            self.assertTrue(
                r["method"] in main_methods or r["method"] == "_open_advanced_from_center"
            )
            self.assertIn("destination", r)
        self.assertIn("_open_legacy_reports", self.code)

    def test_uses_no_database_or_file_writes(self):
        self.assertNotIn("import db", self.code)
        self.assertNotIn("sqlite3", self.code)
        self.assertNotIn(".execute(", self.code)
        self.assertNotIn(".commit(", self.code)
        self.assertNotIn(".write_", self.code)
        self.assertNotIn("QFileDialog", self.code)

    def test_dashboard_has_entry_point_and_signal(self):
        self.assertIn('self.btn_report_center = QPushButton("📑 Rapor Merkezi")', self.dashboard)
        self.assertIn('self.btn_report_center.clicked.connect(self._open_report_center)', self.dashboard)
        self.assertIn('def _open_report_center(self):', self.dashboard)

    def test_pinned_core_sources_are_unmodified(self):
        expected = json.loads((ROOT / "tests/v42_protected_hashes.json").read_text(encoding="utf-8"))
        for rel, digest in expected.items():
            with self.subTest(file=rel):
                self.assertEqual(hashlib.sha256((ROOT / rel).read_bytes()).hexdigest(), digest)


if __name__ == "__main__":
    unittest.main()
