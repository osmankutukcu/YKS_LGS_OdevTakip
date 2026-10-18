import unittest
from dataclasses import dataclass
from services.survey_integrity_v8 import inspect_answers,complete_self_reports,safe_general_rows

@dataclass
class Question:
    key: str
@dataclass
class Definition:
    title: str
    questions: list

class SurveyV8Test(unittest.TestCase):
    def setUp(self):
        self.cat={
            'study_habits':Definition('Çalışma alışkanlığı',[Question('a'),Question('b')]),
            'exam_anxiety':Definition('Özel anket',[Question('x'),Question('y')]),
            'time_management':Definition('Zaman',[Question('t')]),
        }
    def test_all_valid(self):
        audit=inspect_answers(self.cat['study_habits'].questions,{'a':1,'b':5})
        self.assertTrue(audit.complete)
        self.assertEqual(audit.answered,2)
    def test_zero_missing(self):
        a=inspect_answers(self.cat['study_habits'].questions,{'a':1})
        self.assertFalse(a.complete);self.assertEqual(a.answered,1)
        self.assertEqual(a.valid_answers,{'a':1})
    def test_bool_invalid(self):
        a=inspect_answers(self.cat['study_habits'].questions,{'a':True,'b':4})
        self.assertFalse(a.complete);self.assertEqual(a.invalid_keys,('a',))
    def test_float_not_silently_coerced(self):
        self.assertEqual(inspect_answers(['x'],{'x':3.7}).invalid_keys,('x',))
    def test_old_json_string_digit(self):
        self.assertTrue(inspect_answers(['x'],{'x':'4'}).complete)
    def test_out_of_range(self):
        for value in (0,-1,6,99,'N/A',None,[],{}):
            with self.subTest(value=value):self.assertFalse(inspect_answers(['x'],{'x':value}).complete)
    def test_missing_payload(self):
        self.assertFalse(inspect_answers(['x'],None).complete)
    def test_unknown_answers_dont_impute(self):
        a=inspect_answers(['x','y'],{'x':5,'bad':1})
        self.assertEqual(a.answered,1)
    def test_only_complete_records(self):
        d={'study_habits':{'answers':{'a':5}},'exam_anxiety':{'answers':{'x':3,'y':4}}}
        self.assertEqual(set(complete_self_reports(self.cat,d)),{'exam_anxiety'})
    def test_sensitive_not_in_shared_rows(self):
        d={'study_habits':{'answers':{'a':1,'b':5}},'exam_anxiety':{'answers':{'x':4,'y':4}}}
        rows=safe_general_rows(self.cat,d)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['response_mean'],3)
    def test_do_not_mutate_responses(self):
        source={'study_habits':{'answers':{'a':5,'b':1}}}
        before=repr(source);safe_general_rows(self.cat,source);self.assertEqual(repr(source),before)
    def test_unknown_survey_not_scored(self):
        self.assertEqual(complete_self_reports(self.cat,{'unknown':{'answers':{'a':4}}}),{})
if __name__=='__main__':unittest.main()
