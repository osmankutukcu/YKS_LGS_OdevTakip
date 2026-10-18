from pathlib import Path
import sys
import shutil
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
install_live_v3 = pytest.importorskip("install_live_v3", reason="Tekil V3 yama kurucusu birleşik V12 kaynağında yer almaz.")
from install_live_v3 import install,rollback,sha,source_state,ORIGINAL_FORM,V2_FORM

BUNDLE=Path(__file__).resolve().parents[1]
ORIGINAL=Path('/mnt/data/homework_v2_audit')
V1=Path('/mnt/data/homework_context_v1_build')
V2=Path('/mnt/data/homework_context_v2_build')
pytestmark = pytest.mark.skipif(not ORIGINAL.is_dir(), reason="/mnt/data denetim klasörleri mevcut değil.")

@pytest.mark.parametrize('version',['original','v1','v2'])
def test_install_and_rollback_sources(tmp_path,version):
    base=tmp_path/'project'
    for d in ('ui','services'): (base/d).mkdir(parents=True,exist_ok=True)
    form = ORIGINAL if version=='original' else V1 if version=='v1' else V2
    names=['homework_form.py']
    if version!='original': names.extend(['homework_context_hub_v1.py','homework_context_logic_v1.py'])
    if version=='v2': names.append('homework_context_integrations_v2.py')
    for name in names: shutil.copy2(form/'ui'/name,base/'ui'/name)
    for name in ('student_workspace_panel_v21.py','homework_workspace_bridge_v21.py'):
        shutil.copy2(ORIGINAL/'ui'/name,base/'ui'/name)
    assert source_state(base)==version
    assert install(base,BUNDLE,check=True).startswith('UYGUN')
    assert sha(base/'ui/homework_form.py') == (ORIGINAL_FORM if version=='original' else V2_FORM if version=='v2' else sha(V1/'ui/homework_form.py'))
    assert 'V3 kuruldu' in install(base,BUNDLE)
    assert sha(base/'ui/homework_form.py') == V2_FORM
    assert (base/'services/live_student_summary_v3.py').is_file()
    with pytest.raises(ValueError):install(base,BUNDLE)
    assert 'geri alındı' in rollback(base)
    assert not (base/'services/live_student_summary_v3.py').exists()
    assert source_state(base)==version


def test_unexpected_edit_fails_closed(tmp_path):
    base=tmp_path/'project'
    (base/'ui').mkdir(parents=True)
    (base/'services').mkdir()
    for name in ('homework_form.py','student_workspace_panel_v21.py','homework_workspace_bridge_v21.py'):
        shutil.copy2(ORIGINAL/'ui'/name,base/'ui'/name)
    with (base/'ui/student_workspace_panel_v21.py').open('a') as f: f.write('\n# unrelated local change')
    with pytest.raises(ValueError):install(base,BUNDLE)
    assert not (base/'services/live_student_summary_v3.py').exists()
