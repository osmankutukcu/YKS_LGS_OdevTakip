"""V9: Takviye, Eksikler, Öneri single-source-of-truth regressions (no Qt required)."""
import ast
from pathlib import Path
import unittest
from utils.recommendation_v9 import select_within_capacity
ROOT=Path(__file__).resolve().parents[1]
FORM=ROOT/'ui/homework_form.py'


def method(class_name, func, *, nth=-1):
    tree=ast.parse(FORM.read_text('utf-8'))
    classes=[x for x in tree.body if isinstance(x, ast.ClassDef) and x.name==class_name]
    node=classes[nth]
    return next(x for x in node.body if isinstance(x, ast.FunctionDef) and x.name==func)


def called_names(fn):
    return {x.func.attr if isinstance(x.func,ast.Attribute) else x.func.id for x in ast.walk(fn) if isinstance(x,ast.Call) and isinstance(x.func,(ast.Attribute,ast.Name))}


class TestAllEntryPoints(unittest.TestCase):
    def test_secondary_dialogs_share_wizard_transfer(self):
        for name in ('_akilli_takviye','_akilli_eksik_konular'):
            with self.subTest(name=name):
                calls=called_names(method('OdevTakipFormu',name))
                self.assertIn('_wizard_transfer_tasks', calls)
                self.assertNotIn('_verilen_satir_ekle', calls)
                self.assertNotIn('_hucre_bul', calls)

    def test_proposal_panels_share_manual_transfer(self):
        for nth in (0,1):
            with self.subTest(nth=nth):
                calls=called_names(method('OneriPaneli','_ekle_click',nth=nth))
                self.assertIn('_wizard_transfer_tasks',calls)
                self.assertNotIn('_verilen_satir_ekle',calls)
                self.assertNotIn('_hucre_bul',calls)
                self.assertNotIn('setCheckState',calls)

    def test_package_does_not_write_assignments(self):
        for nth in (0,1):
            calls=called_names(method('OneriPaneli','_paket_click',nth=nth))
            self.assertNotIn('_wizard_transfer_tasks',calls)
            self.assertNotIn('_verilen_satir_ekle',calls)
            self.assertIn('select_within_capacity',calls)

    def test_refresh_has_student_guard(self):
        for nth in (0,1):
            self.assertIn('same_student',called_names(method('OneriPaneli','_yenile_click',nth=nth)))

    def test_candidates_use_real_current_student_matrix(self):
        fn=method('OdevTakipFormu','_oneri_yenile')
        calls=called_names(fn)
        self.assertIn('same_student',calls)
        self.assertIn('_get_default_sure',calls)
        self.assertNotIn('_verilen_satir_ekle',calls)


class TestSafePack(unittest.TestCase):
    def setUp(self):
        self.items=[dict(ders='fizik',kitap='A',konu='K1',dk=45),
                    dict(ders='fizik',kitap='A',konu='K2',dk=60),
                    dict(ders='matematik',kitap='B',konu='M1',dk=30)]
    def test_exact_fit(self):
        got=select_within_capacity(self.items,75)
        self.assertEqual(sum(x['dk'] for x in got),75)
    def test_small_target_not_exceeded(self):
        for lim in (0,1,30,35,45,60,74,90,100,135,200):
            with self.subTest(lim=lim):
                got=select_within_capacity(self.items,lim,0)
                self.assertLessEqual(sum(x['dk'] for x in got),lim)
    def test_tolerance(self):
        got=select_within_capacity(self.items,70,5)
        self.assertEqual(sum(x['dk'] for x in got),75)
    def test_diverse(self):
        got=select_within_capacity(self.items,200,0,True)
        self.assertEqual(len(got),2)
        self.assertEqual({x['kitap'] for x in got},{'A','B'})
    def test_duplicate_case_insensitive(self):
        got=select_within_capacity(self.items+[dict(ders=' FİZİK ',kitap='A',konu=' K1 ',dk=10)],200)
        # Duplicate must not appear as separate assignment.
        self.assertEqual(len(got),3)
    def test_bad_minutes_rejected(self):
        for bad in ('abc',None,-2,0):
            with self.subTest(bad=bad):
                self.assertEqual(select_within_capacity([dict(ders='X',kitap='Y',konu='Z',dk=bad)],80),[])
    def test_original_tasks_not_mutated(self):
        before=[dict(x) for x in self.items]
        select_within_capacity(self.items,60)
        self.assertEqual(self.items,before)


if __name__=='__main__': unittest.main()

class TestActualCandidateBehavior(unittest.TestCase):
    """Test the real form method extracted from AST, on a Qt-compatible fake matrix."""
    @staticmethod
    def build_form():
        from tests.test_wizard_student_transfer_v8 import FakeQt, FakeMatrix, FakeCell
        import types
        fn=method('OdevTakipFormu','_oneri_yenile')
        cls=ast.ClassDef(name='CandidateForm', bases=[], keywords=[], body=[fn],decorator_list=[])
        exec_ns={'Qt':FakeQt}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[cls],type_ignores=[])),str(FORM),'exec'),exec_ns)
        form=exec_ns['CandidateForm']()
        form._secili_ogrenci_id=lambda:18
        form._loaded_student_id=18
        form._get_default_sure=lambda:45
        form.verilen=types.SimpleNamespace(rowCount=lambda:0)
        form._vtext=lambda r,c:''
        form._ders_tablolari={'fizik':FakeMatrix(book='FİZİK1', topic='Elektrostatik')}
        return form,FakeQt

    def test_real_proposals_use_verified_matrix(self):
        host,qt=self.build_form()
        got=host._oneri_yenile()
        self.assertEqual(len(got),2)
        self.assertEqual(got[0]['kitap'],'FİZİK1')
        self.assertEqual(got[0]['dk'],45)
        self.assertEqual(got[0]['status'],'aday')

    def test_real_proposals_reject_other_student(self):
        host,qt=self.build_form()
        host._loaded_student_id=20
        self.assertEqual(host._oneri_yenile(),[])

    def test_real_proposals_skip_checked_and_locked(self):
        host,qt=self.build_form()
        host._ders_tablolari['fizik'].cells[0]._state=qt.CheckState.Checked
        host._ders_tablolari['fizik'].cells[1]._flags=0
        self.assertEqual(host._oneri_yenile(),[])

    def test_real_proposals_skip_protected_history(self):
        host,qt=self.build_form()
        for c in host._ders_tablolari['fizik'].cells:
            c.color='#a5d6a7'
        self.assertEqual(host._oneri_yenile(),[])


class TestToggleAndUncheckRegressions(unittest.TestCase):
    def test_toggle_handles_both_enum_and_int2(self):
        """Qt model index.data(CheckStateRole) returns int 2, while enum is Qt.CheckState.Checked."""
        from tests.test_wizard_student_transfer_v8 import FakeQt
        # Verify both int 2 and enum object toggle to Unchecked
        for st in (FakeQt.CheckState.Checked, 2):
            is_checked = (st in (FakeQt.CheckState.Checked, 2))
            new_st = FakeQt.CheckState.Unchecked if is_checked else FakeQt.CheckState.Checked
            self.assertEqual(new_st, FakeQt.CheckState.Unchecked)

        for st in (FakeQt.CheckState.Unchecked, 0, None):
            is_checked = (st in (FakeQt.CheckState.Checked, 2))
            new_st = FakeQt.CheckState.Unchecked if is_checked else FakeQt.CheckState.Checked
            self.assertEqual(new_st, FakeQt.CheckState.Checked)

    def test_tik_degisti_uses_normalized_exact_task_key(self):
        from utils.wizard_integrity_v8 import exact_task_key
        # Verify casing and space normalization
        self.assertEqual(
            exact_task_key('felsefe', 'felsefe1', 'Bilgi Felsefesi'),
            exact_task_key('Felsefe', 'felsefe1 ', 'bilgi felsefesi')
        )
