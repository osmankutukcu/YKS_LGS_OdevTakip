"""Offline Baileys installer tests: do not download, install or send messages."""
from __future__ import annotations

import ast
from pathlib import Path
import subprocess

from services.whatsapp_queue.baileys_runtime_v3576 import (
    detect_runtime, enriched_path, RuntimeStatus, setup_failure_message,
)

ROOT = Path(__file__).resolve().parents[1]


def fake_run(command, **kwargs):
    program, argument = command
    if argument == '--version':
        if program.endswith('node.exe'):
            return subprocess.CompletedProcess(command, 0, 'v22.14.0\n', '')
        if program.endswith('npm.cmd'):
            return subprocess.CompletedProcess(command, 0, '10.9.0\n', '')
    raise AssertionError(f'Unexpected test command {command}')


def test_missing_node_yields_error_with_winget():
    status = detect_runtime(platform='win32', environ={},
                            which=lambda key: 'C:/Win/winget.exe' if 'winget' in key else None,
                            run=lambda *a, **kw: (_ for _ in ()).throw(AssertionError('should not execute')),
                            is_file=lambda x: False)
    assert not status.ready and 'Node.js' in status.reason
    assert status.winget.endswith('winget.exe')


def test_node_and_npm_after_install_not_on_path():
    status = detect_runtime(
        platform='win32', environ={'ProgramFiles': 'C:/Program Files'},
        which=lambda _: None,
        run=fake_run,
        is_file=lambda x: x in ('C:/Program Files/nodejs/node.exe', 'C:/Program Files/nodejs/npm.cmd'))
    assert status.ready and status.node_version == 'v22.14.0'
    assert status.npm.endswith('/npm.cmd')


def test_outdated_runtime_fails_closed():
    def old_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, 'v18.19.0', '')
    status = detect_runtime(platform='win32', environ={},
        which=lambda n: 'C:/bin/node.exe' if n.startswith('node') else None,
        run=old_run, is_file=lambda _: True)
    assert not status.ready and 'eski' in status.reason


def test_missing_npm_fails_closed():
    status = detect_runtime(platform='win32', environ={},
        which=lambda n: 'C:/bin/node.exe' if n.startswith('node') else None,
        run=fake_run, is_file=lambda x: x.endswith('node.exe'))
    assert not status.ready and 'npm' in status.reason


def test_corrupt_version_rejected():
    status = detect_runtime(platform='win32', environ={},
        which=lambda n: 'C:/bin/node.exe' if n.startswith('node') else None,
        run=lambda command, **kw: subprocess.CompletedProcess(command, 0, 'not-node', ''),
        is_file=lambda _: True)
    assert not status.ready


def test_os_other_than_windows_does_nothing():
    status = detect_runtime(platform='linux', which=lambda _: (_ for _ in ()).throw(AssertionError()))
    assert not status.ready and 'Windows' in status.reason


def test_runtime_path_extension_is_non_destructive():
    status = RuntimeStatus(True, 'ok', node='C:/nodejs/node.exe', npm='C:/nodejs/npm.cmd')
    assert enriched_path(status, 'C:/Windows') == 'C:/nodejs;C:/Windows'
    assert enriched_path(status, 'C:/nodejs;C:/Windows').count('C:/nodejs') == 1


def test_installer_batch_has_explicit_consent_checks_and_exit_codes():
    cmd = (ROOT/'services/whatsapp_queue/baileys_node_v257/Windows_Hazirla_V258.cmd').read_text()
    assert 'BAILEYS_SETUP_APPROVED' in cmd
    assert 'choice /M' in cmd
    assert 'if %NODE_MAJOR% LSS 20' in cmd
    assert '--ignore-scripts' in cmd
    assert 'exit /b 0' in cmd
    assert 'pause' not in cmd.lower()


def test_ui_is_async_and_guarded():
    source = (ROOT/'ui/baileys_bulk_v258.py').read_text(encoding='utf-8')
    ast.parse(source)
    assert 'self._setup_process' in source
    assert 'proc.finished.connect(self._setup_finished)' in source
    assert "phase == 'node'" in source
    assert 'QProcessEnvironment.systemEnvironment()' in source
    assert "'--accept-package-agreements'" in source
    assert 'self.q.claim_next(self._batch)' in source
    assert 'os.startfile' not in source


def test_original_web_and_homework_files_not_ininstaller():
    source=(ROOT/'ui/baileys_bulk_v258.py').read_text()
    assert 'ui/homework_form.py' not in source
    assert 'ui/odev_kontrol.py' not in source



def test_failure_explanations_are_specific_and_do_not_claim_sent():
    assert 'npm' in setup_failure_message('deps', 11)
    assert 'protokol' in setup_failure_message('deps', 23)
    assert 'Windows' in setup_failure_message('node', 1)
    assert 'QR' in setup_failure_message('deps', 23)

