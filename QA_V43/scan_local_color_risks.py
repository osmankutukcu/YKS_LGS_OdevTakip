# -*- coding: utf-8 -*-
"""Informational source audit. Candidate counts are NOT verified visual defects."""
from __future__ import annotations
import ast
import json
import re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
records=[]
for file in (ROOT/'ui').rglob('*.py'):
    tree=ast.parse(file.read_text(encoding='utf-8-sig'),filename=str(file))
    local_count=0
    literal_count=0
    bg_no_fg=0
    direct_qt_draw=0
    for node in ast.walk(tree):
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute):
            if node.func.attr=='setStyleSheet':
                local_count+=1
                if node.args:
                    try:
                        chunks=[]
                        for sub in ast.walk(node.args[0]):
                            if isinstance(sub, ast.Constant) and isinstance(sub.value,str):
                                chunks.append(sub.value)
                        literal='\n'.join(chunks)
                        if literal:
                            literal_count+=1
                            blocks=re.findall(r'\{([^{}]*)\}',literal,re.S)
                            bg_no_fg+=sum(bool(re.search(r'\bbackground(?:-color)?\s*:',b)) and not bool(re.search(r'(?<!-)\bcolor\s*:',b)) for b in blocks)
                    except Exception:
                        pass
            if node.func.attr in ('setPen','setBrush'):
                direct_qt_draw+=1
    if local_count or direct_qt_draw:
        records.append({'path':file.relative_to(ROOT).as_posix(),
                        'local_style_calls':local_count,
                        'css_literal_calls':literal_count,
                        'css_background_without_same_block_foreground_candidates':bg_no_fg,
                        'qt_painter_color_calls':direct_qt_draw})
records.sort(key=lambda r:(r['css_background_without_same_block_foreground_candidates'],r['local_style_calls']),reverse=True)
report={'warning':'Source heuristics only; background-only :hover rules are normal; a candidate is not a proven defect',
        'ui_files_scanned':len(list((ROOT/'ui').rglob('*.py'))),
        'with_local_style_or_painter_calls':len(records),
        'total_local_styles':sum(r['local_style_calls'] for r in records),
        'total_background_only_candidates':sum(r['css_background_without_same_block_foreground_candidates'] for r in records),
        'highest_attention_files':records[:25]}
(ROOT/'QA_V43'/'local_style_risk_scan.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print('UI modules:',report['ui_files_scanned'])
print('Local setStyleSheet calls:',report['total_local_styles'])
print('Potential background-only CSS blocks:',report['total_background_only_candidates'])
print('These counts are not proven visual failures. Manual or runtime review is necessary.')
