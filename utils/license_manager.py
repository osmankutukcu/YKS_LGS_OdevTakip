import os
import sys
import json
import uuid
import hashlib
import base64
import platform
import subprocess
import datetime
import hmac
from pathlib import Path

# --- Configuration ---
# RSA Public Key (Embedded in App)
# 1024-bit Güçlü Anahtar Modulus (N)
RSA_N = 63596016435869199758595184650300680785102965001811426742530826267903030966068348475018147447679804548745840937391644961322478211825474436927570514904872183221096968649670640693766154323609305912491672225459870900893484653869132287389129929700182896257220340237660290286910826360144916404692757705278482529801
RSA_E = 65537
HIDDEN_CONFIG_FILE = Path.home() / ".yks_lgs_manager_config"

class MachineID:
    @staticmethod
    def get_id():
        """Generates a unique machine ID based on hardware properties."""
        meta = []
        try:
            # Platform specific hardware info
            if sys.platform == "darwin":
                cmd = "ioreg -l | grep IOPlatformSerialNumber"
                output = subprocess.check_output(cmd, shell=True).decode()
                meta.append(output.split('=')[-1].strip().replace('"', ''))
            elif sys.platform == "win32":
                import winreg
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography")
                val, _ = winreg.QueryValueEx(key, "MachineGuid")
                meta.append(str(val))
            else:
                with open("/etc/machine-id", "r") as f:
                    meta.append(f.read().strip())
        except Exception:
            meta.append(platform.node())
            meta.append(platform.machine())
            meta.append(platform.processor())

        raw_id = "_".join(meta)
        return hashlib.sha256(raw_id.encode()).hexdigest()[:16].upper()

class LicenseKey:
    @staticmethod
    def _hash_payload(payload_b64):
        """Returns secure integer hash of payload."""
        h = hashlib.sha256(payload_b64.encode()).hexdigest()
        # 256-bit hash, 1024-bit anahtara sığar. Kırpmaya gerek yok.
        return int(h, 16)

    @staticmethod
    def generate(machine_id, days_valid, private_d, modulus_n):
        """Generates a signed license key using Private Key (RSA)."""
        exp_date = datetime.date.today() + datetime.timedelta(days=days_valid)
        payload = {
            "mid": machine_id,
            "exp": exp_date.isoformat(),
            "nonce": os.urandom(4).hex()
        }
        payload_json = json.dumps(payload, sort_keys=True)
        payload_b64 = base64.b64encode(payload_json.encode()).decode()
        
        # Sign: pow(hash, d, n)
        h_int = LicenseKey._hash_payload(payload_b64)
        sig_int = pow(h_int, private_d, modulus_n)
        sig_hex = hex(sig_int)[2:]
        
        return f"{payload_b64}.{sig_hex}"

    @staticmethod
    def verify(key, machine_id):
        """Verifies license using Public Key (RSA)."""
        try:
            if "." not in key: return False, "Geçersiz format"
            payload_b64, sig_hex = key.split(".")
            
            # Verify Sig: pow(sig, e, n) == hash
            sig_int = int(sig_hex, 16)
            decrypted_hash = pow(sig_int, RSA_E, RSA_N)
            expected_hash = LicenseKey._hash_payload(payload_b64)
            
            if decrypted_hash != expected_hash:
                return False, "İmza geçersiz (Lisans anahtarı hatalı)"
            
            # Decode Payload
            data = json.loads(base64.b64decode(payload_b64).decode())
            
            if data["mid"] != machine_id:
                return False, "Bu lisans başka bir cihaza ait."
            
            exp_date = datetime.date.fromisoformat(data["exp"])
            if exp_date < datetime.date.today():
                return False, "Lisans süresi dolmuş."
                
            return True, f"Lisans Aktif! Bitiş: {data['exp']}"
            
        except Exception as e:
            return False, f"Lisans hatası: {e}"

class TrialManager:
    # Obfuscated keys
    K_START = "idx_s"
    K_LAST = "idx_l"
    K_LIC = "idx_k"
    
    def __init__(self, trial_days=15):
        self.trial_days = trial_days
        self._data = self._load()

    def _load(self):
        # Anti-Tampering: Check if file exists and is valid
        if not HIDDEN_CONFIG_FILE.exists():
            return {}
        try:
            content = HIDDEN_CONFIG_FILE.read_text().strip()
            if not content: return {}
            
            # Obfuscation: Base64 Reverse + Simple XOR/Salt effect (Logic shift)
            # Reversing the simple logic: 
            # 1. Reverse string
            # 2. Base64 decode
            reversed_content = content[::-1]
            decoded_bytes = base64.b64decode(reversed_content)
            decoded_str = decoded_bytes.decode('utf-8')
            
            return json.loads(decoded_str)
        except Exception:
            # File corrupted or tampered
            return {"corrupted": True}

    def _save(self):
        try:
            content = json.dumps(self._data)
            # Obfuscation: 
            # 1. Base64 encode
            # 2. Reverse string
            # This is simple but effective enough to stop casual editing
            encoded_bytes = base64.b64encode(content.encode('utf-8'))
            encoded_str = encoded_bytes.decode('utf-8')[::-1]
            
            HIDDEN_CONFIG_FILE.write_text(encoded_str)
        except:
            pass

    def check_status(self):
        """
        Returns dict:
        {
            "status": "valid" | "expired" | "tampered",
            "message": str,
            "days_left": int,
            "machine_id": str,
            "is_license": bool
        }
        """
        mid = MachineID.get_id()
        today = datetime.date.today().isoformat()
        
        # Geliştirici Modu (Bypass): Kaynak koddan çalışırken lisans kontrolünü atla
        is_frozen = getattr(sys, "frozen", False)
        force_lic = os.environ.get("YKS_FORCE_LICENSE", "0") == "1"
        if not is_frozen and not force_lic:
            return {
                "status": "valid",
                "message": "Geliştirici Modu Aktif (Süresiz)",
                "days_left": 9999,
                "machine_id": mid,
                "is_license": True
            }

        # 0. Check Corruption (File manual edit attempt)
        if self._data.get("corrupted"):
             return {"status": "tampered", "message": "Lisans dosyası bozulmuş/müdahale edilmiş!", "days_left": 0, "machine_id": mid, "is_license": False}
        
        # 1. Check if Full License exists
        lic_key = self._data.get(self.K_LIC)
        if lic_key:
            valid, msg = LicenseKey.verify(lic_key, mid)
            if valid:
                return {"status": "valid", "message": msg, "days_left": 999, "machine_id": mid, "is_license": True}
        
        # 2. Initialize Trial if empty
        if self.K_START not in self._data:
            self._data[self.K_START] = today
            self._data[self.K_LAST] = today
            self._save()
            
        # 3. Check Clock Tampering (Rollback)
        last_run = self._data.get(self.K_LAST, today)
        if today < last_run:
            return {"status": "tampered", "message": "Sistem saati geri alınmış! (Güvenlik İhlali)", "days_left": 0, "machine_id": mid, "is_license": False}
        
        # Update last run
        self._data[self.K_LAST] = today
        self._save()
        
        # 4. Check Trial Expiry
        start_date = datetime.date.fromisoformat(self._data[self.K_START])
        days_passed = (datetime.date.today() - start_date).days
        days_left = self.trial_days - days_passed
        
        if days_left < 0:
            return {"status": "expired", "message": "Deneme süresi doldu.", "days_left": 0, "machine_id": mid, "is_license": False}
            
        return {"status": "valid", "message": f"Deneme Sürümü ({days_left} gün kaldı)", "days_left": days_left, "machine_id": mid, "is_license": False}

    def activate_license(self, key):
        mid = MachineID.get_id()
        valid, msg = LicenseKey.verify(key, mid)
        if valid:
            self._data[self.K_LIC] = key
            self._save()
            return True, msg
        return False, msg

# Singleton instance
manager = TrialManager()
