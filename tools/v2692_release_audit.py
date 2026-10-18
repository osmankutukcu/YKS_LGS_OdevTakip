# -*- coding: utf-8 -*-
"""Static, safe, read-only release audit. No application imports or student DB access."""
from __future__ import annotations
import argparse
from pathlib import Path
import hashlib, json, platform

ROOT = Path(__file__).resolve().parents[1]
PROVENANCE = ROOT/'V26_8_MANIFEST.json'
ORIGINAL = ROOT/'tests/v2691_original_source_manifest.json'


def audit(root: Path = ROOT) -> dict:
    sources = json.loads((root/'tests/v2691_original_source_manifest.json').read_text('utf8'))['protected_sha256']
    checks = {name: (root/name).is_file() and hashlib.sha256((root/name).read_bytes()).hexdigest()==expected for name,expected in sources.items()}
    delta = json.loads((root/'V26_8_MANIFEST.json').read_text('utf8'))
    panel = 'ui/student_workspace_panel_v21.py'
    expected_panel = 'd98b2403e7f7ee147e1e7a6b6a1098117efaad0fc466eeafac44314678eff432'
    prior_panel = '89bbbc6ef0ed74b4f068a6644a7d0e9b5cc900368178d3ad68a9daf05ac260a2'
    panel_check = (delta['files'].get(panel)==expected_panel
        and delta['previous_source_sha256'].get(panel)==prior_panel
        and hashlib.sha256((root/panel).read_bytes()).hexdigest()==expected_panel)
    workflow = root/'.github/workflows/build_installer.yml'
    # Workflow is absent from the user's original source archive. Do not fabricate it.
    report = {
        'qa_version': 'V26.9.2',
        'os': platform.system(),
        'original_six_protected_files': checks,
        'v268_student360_panel_verified': panel_check,
        'github_workflow_present': workflow.is_file(),
        'chromium_smoke': 'NOT_VERIFIED',
        'qt_ui_tests': 'NOT_VERIFIED',
        'real_desktop_acceptance': 'NOT_VERIFIED',
        'release_status': 'BLOCKED',
        'release_blockers': ([] if all(checks.values()) and panel_check else ['Source provenance check failed']) +
                            ([] if workflow.is_file() else ['Missing original .github/workflows/build_installer.yml']) +
                            ['Real Windows/macOS acceptance pending','Chromium and PyQt6 integration tests pending']
    }
    return report


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument('--report',type=Path)
    args=parser.parse_args()
    rep=audit()
    if args.report:
        args.report.write_text(json.dumps(rep,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(rep,ensure_ascii=False,indent=2))
    # This audit is a verification utility, it does not certify a release.
    return 0 if all(rep['original_six_protected_files'].values()) and rep['v268_student360_panel_verified'] else 2

if __name__=='__main__':
    raise SystemExit(main())
