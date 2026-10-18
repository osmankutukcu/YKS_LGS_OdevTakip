"""Offline source-contract tests for Windows-only V25.5 PowerShell diagnostic.
These checks do not execute PowerShell or DPAPI. Actual Windows tests remain required.
"""
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'tools'/'windows_security_offline_v255.ps1'
BAT=ROOT/'tools'/'Windows_Tek_Tik_Guvenlik_Kontrolu_V255.bat'

def test_sources_exist():
    assert SCRIPT.is_file() and BAT.is_file()

def test_no_student_data_or_sending_code():
    code=SCRIPT.read_text(encoding='utf-8-sig').lower()
    assert 'currentuser' in code and 'protecteddata' in code
    assert 'start-process' not in code and 'invoke-webrequest' not in code
    assert 'sendmessage' not in code and 'whatsapp.com' not in code
    assert 'sqlite3' not in code and 'select * from' not in code
    assert 'readalltext($encfile' in code

def test_fail_closed_and_no_false_pass():
    code=SCRIPT.read_text(encoding='utf-8-sig')
    assert "'PASS_SYNTHETIC_DPAPI_ONLY'" in code
    assert "'FAIL_CLOSED'" in code
    for tag in ['DPAPI_CURRENT_USER_ROUNDTRIP', 'WRONG_PURPOSE_DENIED',
                'TAMPERED_CIPHERTEXT_DENIED', 'NO_PLAINTEXT_IN_TEST_FILE',
                'SAME_USER_SECOND_PROCESS_ROUNDTRIP']:
        assert tag in code
    assert '$checks.Count -eq 5' in code
    assert 'distinct_windows_users_verified = $false' in code
    assert 'python_v250_v254_modules_tested = $false' in code
    assert 'baileys_enabled = $false' in code

def test_batch_has_no_python_dependencies():
    data=BAT.read_text(encoding='ascii').lower()
    assert 'powershell.exe' in data
    assert ' -executionpolicy bypass ' in data
    assert 'py -3' not in data and 'pip install' not in data
    assert 'windows_security_offline_v255.ps1' in data
