# -*- coding: utf-8 -*-
"""V3.5.27: READ-ONLY homework form contracts and effective handler map.

Never imports PyQt6, touches student DBs or patches UI classes. It is a release
blocker, not evidence of actual Windows GUI correctness.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = 'tests/v3527_effective_behavior_baseline.json'
PROTECTED = 'tests/v42_protected_hashes.json'
HELPERS = 'tests/v3527_protected_helpers.json'

# Protect concrete existing behavior, including visuals, locked cells,
# debounce, event wiring, manual transfer and student ownership.
MANDATORY_SNIPPETS = {
    'ui/homework_form.py': {
        '_ders_tab_olustur': ['#FFF59D', '#A5D6A7', 'PendingCheckboxChanges',
                             'ic_timer.setInterval(0)', 'table.itemChanged.connect(_ic_proxy)',
                             'ItemIsUserCheckable', 'setAlternatingRowColors(True)',
                             'setItemDelegateForColumn'],
        '_kilitle_ve_boya': ['setBackground(renk)', '~Qt.ItemFlag.ItemIsUserCheckable'],
        '_tik_degisti': ['exact_task_key', 'insertRow(', 'removeRow(',
                         '_sync_verilen_rows_from_table'],
        '_kaydet_kume': ['_flush_checkbox_queues()', 'same_student(',
                         'INSERT OR IGNORE INTO odev', 'ogrenci_id=?'],
        '_odev_kontrol': ['OdevKontrolDialog(', '_kontrol_sync_timer',
                          '_senkronize_odev_durumlari'],
    },
    'ui/odev_kontrol.py': {
        '_kaydet': ['UPDATE odev SET durum=?, aciklama=?', 'con.commit()',
                    'sonuc_sinyal.emit'],
        '_hesapla_yuzde': ['_update_header_stats()'],
        '_chk_cell_click': ['_last_chk_time', '0.2', 'setCheckState(new_state)'],
        '_on_table_item_changed': ['_hesapla_yuzde()', '_refresh_right_table_styles()'],
        '_refresh_right_table_styles': ['#ecfdf5', '#065f46',
                                        'setBackground(', 'setForeground('],
        '_kume_ac_moved': ['#F3F4F6', 'ItemIsEnabled', 'aktarildi'],
    },
}
MANDATORY_WIRING = {
    'ui/homework_form.py': ['btnKaydet.clicked.connect(self._kaydet_kume)',
                             'btnKontrol.clicked.connect(self._odev_kontrol)'],
    'ui/odev_kontrol.py': ['btnKaydet.clicked.connect(self._kaydet)',
                           'tab.itemChanged.connect(self._on_table_item_changed)',
                           'tab.cellClicked.connect(self._chk_cell_click)'],
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def _methods(source: str, cls_name: str):
    tree = ast.parse(source)
    cls = next((x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == cls_name), None)
    if cls is None:
        return {}
    found = {}
    for x in cls.body:
        if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef)):
            found.setdefault(x.name, []).append(x)
    return found


def audit(root: Path = ROOT, *, baseline_file: Path | None = None) -> dict:
    root = Path(root)
    baseline_file = baseline_file or root/BASELINE
    baseline = json.loads(baseline_file.read_text(encoding='utf8'))
    protected = json.loads((root/PROTECTED).read_text(encoding='utf8'))
    helpers = json.loads((root/HELPERS).read_text(encoding='utf8'))
    errors, warnings, active = [], [], {}
    # Whole-file checks: ensures the complete existing layouts, colors, locks,
    # paint delegates and previously developed interactions remain byte-identical.
    for rel, expected in sorted(protected.items()):
        p = root/rel
        if not p.is_file() or _sha(p) != expected:
            errors.append('PROTECTED_SOURCE_CHANGED:' + rel)
    for rel, expected in sorted(helpers.items()):
        if not (root/rel).is_file() or _sha(root/rel) != expected:
            errors.append('PROTECTED_HELPER_CHANGED:' + rel)
    for rel, entry in baseline.items():
        p = root/rel
        if not p.is_file():
            errors.append('CORE_MISSING:' + rel)
            continue
        if _sha(p) != entry['file_sha256']:
            errors.append('CORE_SHA_MISMATCH:' + rel)
        source = p.read_text('utf8')
        try:
            methods = _methods(source, entry['class'])
        except SyntaxError:
            errors.append('CORE_SYNTAX_ERROR:' + rel)
            continue
        for name, expectation in entry['critical_methods'].items():
            defs = methods.get(name, [])
            if not defs:
                errors.append('HANDLER_MISSING:' + rel + ':' + name)
                continue
            effective = defs[-1]  # Python class semantics: later definition wins
            signature = hashlib.sha256(ast.dump(effective, include_attributes=False).encode()).hexdigest()
            allowed_sigs = expectation.get('effective_ast_sha256_alt', [expectation['effective_ast_sha256']])
            if signature not in allowed_sigs:
                errors.append('EFFECTIVE_HANDLER_CHANGED:' + rel + ':' + name)
            if len(defs) != expectation['total_definitions']:
                errors.append('HANDLER_SHADOWING_CHANGED:' + rel + ':' + name)
            active[f'{rel}:{name}'] = {
                'effective_line': effective.lineno,
                'definition_count': len(defs),
                'signature_ok': signature in allowed_sigs,
            }
            if len(defs) > 1:
                warnings.append('EXISTING_SHADOWED_METHOD:' + rel + ':' + name)
            text = ast.get_source_segment(source, effective) or ''
            for required in MANDATORY_SNIPPETS.get(rel, {}).get(name, []):
                if required not in text:
                    errors.append('BEHAVIOR_TOKEN_MISSING:' + rel + ':' + name + ':' + required)
        for expression in MANDATORY_WIRING.get(rel, []):
            if expression not in source:
                errors.append('SIGNAL_WIRING_MISSING:' + rel + ':' + expression)
    # Require the same set of connected, human-visible essential signals.
    return {
        'status': 'PASS' if not errors else 'BLOCK',
        'scope': 'static_source_contract_only',
        'protected_files': len(protected),
        'protected_helpers': len(helpers),
        'protected_behavior_handlers': len(active),
        'errors': sorted(set(errors)),
        'warnings': sorted(set(warnings)),
        'effective_handlers': active,
        'original_forms_modified': False if not errors else 'REVIEW_REQUIRED',
        'database_read_or_write': False,
        'runtime_monkey_patching': False,
        'windows_visual_and_interactive_uat': 'NOT_VERIFIED',
        'production_release_authorized': False,
    }


def main(argv=None):
    cli = argparse.ArgumentParser(description='V3.5.27 korunan formlar salt-okunur kaynak kapısı')
    cli.add_argument('--root', type=Path, default=ROOT)
    cli.add_argument('--output', type=Path, default=None)
    args = cli.parse_args(argv)
    report = audit(args.root)
    output = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(output+'\n', encoding='utf8')
    print(output)
    return 0 if report['status'] == 'PASS' else 2


if __name__ == '__main__':
    raise SystemExit(main())
