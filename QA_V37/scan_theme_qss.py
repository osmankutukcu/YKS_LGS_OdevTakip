from pathlib import Path
import ast,re,json,collections
import sys
root=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parents[1]
COLOR_RE=re.compile(r'(?<![\w-])#(?:[0-9A-Fa-f]{6}|[0-9A-Fa-f]{3})(?![\w-])')
RULE_RE=re.compile(r'([^{}]+)\{([^{}]*)\}',re.S)
CSS_PROPERTY=re.compile(r'(?i)(?<![\w-])([\w-]+)\s*:\s*([^;}{]+)')
HEX_COLOR=re.compile(r'^#[0-9a-f]{3}(?:[0-9a-f]{3})?$',re.I)
def lum(h):
 h=h.lower().strip('#'); h=''.join(x*2 for x in h) if len(h)==3 else h
 c=[int(h[i:i+2],16)/255 for i in (0,2,4)]
 c=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in c]
 return .2126*c[0]+.7152*c[1]+.0722*c[2]
def contrast(x,y):
 a,b=lum(x),lum(y); return (max(a,b)+.05)/(min(a,b)+.05)
report=collections.defaultdict(lambda:dict(styles=0,hardcoded_colors=0,low_contrast=[],unpaired_bg=[],unpaired_fg=[],qss_root=[]))
for fp in [p for p in root.rglob('*.py') if not any(x in p.parts for x in ('.git', '.venv', 'build', 'dist', '__pycache__'))]:
 if 'QA_V' in str(fp) or '/tests/' in str(fp) or '/backups/' in str(fp):continue
 rel=str(fp.relative_to(root));src=fp.read_text(encoding='utf-8-sig',errors='replace'); rec=report[rel]; rec['hardcoded_colors']=len(COLOR_RE.findall(src))
 try: tree=ast.parse(src)
 except SyntaxError:continue
 for node in ast.walk(tree):
  if not (isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='setStyleSheet' and node.args): continue
  rec['styles']+=1
  arg=node.args[0]
  if isinstance(arg,ast.Constant) and isinstance(arg.value,str):s=arg.value
  elif isinstance(arg,ast.JoinedStr):s=''.join(v.value if isinstance(v,ast.Constant) and isinstance(v.value,str) else '__VALUE__' for v in arg.values)
  else:continue
  # handle plain 'color:' for standalone styles (no QSS selectors)
  rules=list(RULE_RE.finditer(s));
  if not rules:rules=[None]
  for m in rules:
   selector=m.group(1).strip() if m else '(widget local)'
   body=m.group(2) if m else s
   selector=re.sub(r'\s+',' ',selector)[-130:]
   props={k.strip().lower():v.strip().lower() for k,v in CSS_PROPERTY.findall(body)}
   bg=props.get('background-color') or props.get('background');fg=props.get('color')
   if bg and HEX_COLOR.fullmatch(bg) and fg and HEX_COLOR.fullmatch(fg):
    c=round(contrast(bg,fg),2)
    if c<4.5: rec['low_contrast'].append({'line':node.lineno,'selector':selector,'fg':fg,'bg':bg,'ratio':c})
   elif bg and (HEX_COLOR.fullmatch(bg) or bg in ('black','white')) and not fg:
    if re.search('QLineEdit|QComboBox|QTable|QTree|QList|QTextEdit|QSpinBox|QDateEdit|QTab|QPushButton|QToolButton|QLabel|QFrame|QWidget',selector) or selector=='(widget local)':
     rec['unpaired_bg'].append({'line':node.lineno,'selector':selector,'bg':bg})
   if fg and HEX_COLOR.fullmatch(fg) and not bg and selector=='(widget local)':rec['unpaired_fg'].append({'line':node.lineno,'selector':selector,'fg':fg})
   if re.search(r'(?:^|,)\s*QWidget\s*(?:,|$)',selector):rec['qss_root'].append(node.lineno)
rows=[]
for fp,r in report.items():
 if r['styles'] or r['hardcoded_colors']:
  score=5*len(r['low_contrast'])+2*len(r['unpaired_bg'])+r['styles']//5
  rows.append((score,fp,r))
rows.sort(reverse=True)
summary={key:sum(len(r[key]) if isinstance(r[key],list) else r[key] for _,_,r in rows) for key in ('styles','hardcoded_colors','low_contrast','unpaired_bg','unpaired_fg')}
summary['python_files_scanned']=len(report);summary['files_with_qss']=sum(r['styles']>0 for _,_,r in rows)
out={'summary':summary,'highest_risk':[{'file':fp,'score':score,**{k:(len(v) if isinstance(v,list) else v) for k,v in r.items() if k!='qss_root'}} for score,fp,r in rows[:50]],'files':dict(report)}
(root/'QA_V37').mkdir(exist_ok=True)
(root/'QA_V37'/'static_report.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
print(summary)
for score,fp,r in rows[:22]: print(f'{score:4} {fp:48} styles={r["styles"]:3} bad={len(r["low_contrast"]):2} unpairedbg={len(r["unpaired_bg"]):3} unpairedfg={len(r["unpaired_fg"]):3}')
print('sample low contrast:')
for score,fp,r in rows[:20]:
 for x in r['low_contrast'][:4]:print(fp,x)
