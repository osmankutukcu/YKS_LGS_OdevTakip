import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tools import validate_release, publish_release

ROOT=Path(__file__).resolve().parents[1]


class PipelineTests(unittest.TestCase):
    def test_installer_preserves_app_identity(self):
        s=(ROOT/'setup.iss').read_text(encoding='utf-8')
        self.assertIn('AppId={{C7A9F521-8F3D-4A73-9C1D-8942A8C162DE}}',s)
        self.assertIn('*.db,',s)
        self.assertIn('license.json',s)
        self.assertNotIn('onlyifdoesntexist recursesubdirs',s)

    def test_updater_no_process_wide_kill_or_ssl_bypass(self):
        s=(ROOT/'utils/updater.py').read_text(encoding='utf-8')
        self.assertNotIn('taskkill',s.lower())
        self.assertNotIn('create_unverified_context',s)
        self.assertNotIn('extractall',s)

    def test_workflow_tags_and_checksum_publish(self):
        s=(ROOT/'.github/workflows/build_installer.yml').read_text(encoding='utf-8')
        self.assertIn('refs/tags/v',s)
        self.assertIn('OdevTakip_v2_Kurulum.exe.sha256',s)
        self.assertIn('tools/validate_release.py',s)

    def test_wrong_tag_fails_gate(self):
        with self.assertRaises(ValueError):
            if 'v4.0.0' != 'v'+validate_release.read_versions():
                raise ValueError('Wrong tag')

    def test_publisher_missing_installer_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            (folder/'version.py').write_text('APP_VERSION = "3.5.2"\n')
            (folder/'setup.iss').write_text('#define MyAppVersion "3.5.2"\n')
            with patch.object(publish_release,'ROOT',folder):
                with self.assertRaises(FileNotFoundError):publish_release.create_release_package('3.5.2')

    def test_publisher_valid_installer(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            (folder/'version.py').write_text('APP_VERSION = "3.5.2"\n')
            (folder/'setup.iss').write_text('#define MyAppVersion "3.5.2"\n')
            inst=folder/'dist/OdevTakip_v2_Kurulum.exe'
            inst.parent.mkdir();inst.write_bytes(b'MZtest installer')
            with patch.object(publish_release,'ROOT',folder):
                result=Path(publish_release.create_release_package('3.5.2'))
            self.assertTrue(result.is_file())
            self.assertEqual(b'MZtest installer',result.read_bytes())
            self.assertTrue(result.with_name(result.name+'.sha256').exists())
            self.assertFalse((folder/'dist_release'/'version.json').exists())

if __name__=='__main__':unittest.main()
