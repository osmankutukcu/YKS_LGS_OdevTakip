from pathlib import Path
import ast, hashlib, json
ROOT = Path(__file__).resolve().parents[1]
base = Path('/mnt/data/v242_full_source')
full = ROOT if not Path('/mnt/data/v243_full_source').exists() else Path('/mnt/data/v243_full_source')
work = Path('/mnt/data/v243_safe_patch')
def test_no_core_changes_and_exact_manifest():
    if base.exists():
        for rel in ('ui/homework_form.py','ui/odev_kontrol.py','db.py','ui/topic_map_dialog.py',
                    'ui/student360_panel_v16.py','services/live_change_probe_v241.py'):
            assert (base/rel).read_bytes()==(full/rel).read_bytes()
        if work.exists():
            for rel,meta in json.loads((work/'checksums.json').read_text())['files'].items():
                src=base/rel
                assert (hashlib.sha256(src.read_bytes()).hexdigest() if src.exists() else None)==meta['before']
                assert hashlib.sha256((full/rel).read_bytes()).hexdigest()==meta['after']
                assert (full/rel).read_bytes()==(work/'payload'/rel).read_bytes()
    else:
        assert hashlib.sha256((ROOT/'ui/homework_form.py').read_bytes()).hexdigest() == '53e6b12db96cf81fd622947e7d343b4130a1a8e42a0e30d5c5ec58e64e456314'
        assert hashlib.sha256((ROOT/'db.py').read_bytes()).hexdigest() == '8b295f375a18b41bdb92f120170bafb9a2cb93863be9e98b789241ceb32c4d6b'

def test_gui_refresh_scope_and_existing_writes_unchanged():
    cm=(full/'ui/coaching_manager.py').read_text()
    assert 'course_attr="_live_course_v243"' in cm
    assert '_shared_topic_timer_v1.start()' in cm
    br=(full/'ui/live_change_bridge_v241.py').read_text()
    assert 'decision.refresh' in br and 'if not decision.refresh:continue' in br
    assert 'student_attr=None, course_attr=None' in br
    for rel in ('ui/live_change_bridge_v241.py','ui/coaching_manager.py'):
        ast.parse((full/rel).read_text())

def test_count_explanation_is_user_facing_and_source_specific():
    from services.coach_shared_topic_v1 import SharedTopicSummary
    snap=SharedTopicSummary(1,'Öğrenci','LGS Matematik',1,1,2,3,4,0,0,0,0,0,0,())
    assert 'Sayılar neden farklı' in snap.note()
    assert 'Konu Haritası' in snap.note()
    assert 'öğrenildiğini kanıtlamaz' in snap.note()
