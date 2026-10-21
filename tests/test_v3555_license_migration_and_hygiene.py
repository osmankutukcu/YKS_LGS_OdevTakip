# -*- coding: utf-8 -*-
"""V3.5.55: Lisans Geçişi (Dual-Key Migration), Özel Anahtar İzolasyonu ve Dağıtım Hijyeni Testleri.

Bu test modülü:
1. V2 (2048-bit RSA) yeni birincil lisans anahtarı üretim ve doğrulamasını,
2. V1 (1024-bit RSA) eski lisans anahtarlarıyla geriye dönük tam uyumluluğu (mevcut müşterilerin lisanslarının geçerli kalmasını),
3. Tahrif edilmiş / geçersiz anahtarların güvenle reddedilmesini,
4. Git deposunda ve dağıtım paketinde _admin_tools_private, keygen ve özel anahtar bulunmadığını (dağıtım hijyeni)
kesin olarak doğrular.
"""

import unittest
import datetime
from pathlib import Path

from utils.license_manager import LicenseKey, MachineID, RSA_N_V2, RSA_N_V1
try:
    from _admin_tools_private.admin_keygen import generate_license_key, RSA_D_V2, RSA_D_V1
except ImportError:
    # Dağıtılan kaynak paketi güvenlik gereği özel imza anahtarlarını İÇERMEZ.
    generate_license_key = None
from tools.validate_release import check_tracked_databases, check_distribution_hygiene

ROOT = Path(__file__).resolve().parents[1]


class TestV3555LicenseMigrationAndHygiene(unittest.TestCase):
    def setUp(self):
        self.mid = MachineID.get_id()

    @unittest.skipIf(generate_license_key is None, "Özel lisans imzalama anahtarı kaynak paketinde dağıtılmaz")
    def test_01_v2_primary_license_generation_and_verification(self):
        """V2 (2048-bit RSA) lisans anahtarı üretilmeli ve başarıyla doğrulanmalıdır."""
        key = generate_license_key(self.mid, days_valid=365, version="v2")
        valid, msg = LicenseKey.verify(key, self.mid)
        self.assertTrue(valid, f"V2 lisans doğrulaması başarısız: {msg}")
        self.assertIn("V2 Güvenli", msg)
        expected_year = (datetime.date.today() + datetime.timedelta(days=365)).isoformat()
        self.assertIn(expected_year, msg)

    @unittest.skipIf(generate_license_key is None, "Özel lisans imzalama anahtarı kaynak paketinde dağıtılmaz")
    def test_02_v1_legacy_license_backwards_compatibility(self):
        """Mevcut müşterilerin mağdur olmaması için eski V1 (1024-bit RSA) anahtarları geçerli kalmalıdır."""
        key = generate_license_key(self.mid, days_valid=60, version="v1")
        valid, msg = LicenseKey.verify(key, self.mid)
        self.assertTrue(valid, f"V1 eski lisans doğrulaması başarısız: {msg}")
        self.assertIn("V1 Geçiş Lisansı", msg)

    @unittest.skipIf(generate_license_key is None, "Özel lisans imzalama anahtarı kaynak paketinde dağıtılmaz")
    def test_03_tampered_and_invalid_licenses_fail_closed(self):
        """Tahrif edilmiş imza veya geçersiz format lisanslar kesinlikle reddedilmelidir."""
        key = generate_license_key(self.mid, days_valid=30, version="v2")
        
        # İmza tahrifatı
        bad_sig_key = key[:-4] + "ffff"
        valid, msg = LicenseKey.verify(bad_sig_key, self.mid)
        self.assertFalse(valid)
        self.assertIn("İmza geçersiz", msg)

        # Farklı makine kimliği
        valid_other_mid, msg_other = LicenseKey.verify(key, "OTHER_MACHINE_123")
        self.assertFalse(valid_other_mid)
        self.assertIn("başka bir cihaza ait", msg_other)

        # Bozuk format
        valid_bad_fmt, msg_fmt = LicenseKey.verify("gecersiz_anahtar", self.mid)
        self.assertFalse(valid_bad_fmt)

    def test_04_tracked_repository_hygiene(self):
        """Git deposunda takip edilen hiçbir dosyada private key veya admin keygen bulunmamalıdır."""
        if not (ROOT / '.git').exists():
            self.skipTest('Git deposu yok: tracked-file denetimi gerçek GitHub checkout aşamasında yapılmalı')
        try:
            check_tracked_databases(ROOT)
        except ValueError as exc:
            self.fail(f"Depo hijyen denetimi başarısız oldu: {exc}")

    def test_05_distribution_hygiene(self):
        """Dağıtım klasörü hassas dosyalardan arındırılmış olmalıdır."""
        try:
            check_distribution_hygiene(ROOT / 'dist')
        except ValueError as exc:
            self.fail(f"Dağıtım hijyeni hatası: {exc}")


if __name__ == '__main__':
    unittest.main()
