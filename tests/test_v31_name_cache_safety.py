# -*- coding: utf-8 -*-
"""Bounded normalization cache must preserve 100% of old exact-key semantics."""
import random
import unittest
from utils.wizard_integrity_v8 import (
    normalized_name, exact_task_key, _normalized_string,
)


def old_normalized_name(value):
    return ' '.join(str(value or '').split()).casefold().replace('\u0307', '').replace('ı','i')


class NameCacheSafety(unittest.TestCase):
    def test_same_as_old_for_turkish_and_mixed_inputs(self):
        names = ['', None, 0, 8, True, False, ' FİZİK  ', 'İntegral',
                 '  Matematik \n Geometri', 'IŞIK', 'çÖzüm', 'AB', [], [1, 2],
                 {'ad': 'Fizik'}, 'é / é', 'σ Σ ς', 'a'*300]
        for name in names:
            with self.subTest(name=name):
                self.assertEqual(normalized_name(name), old_normalized_name(name))
        rnd = random.Random(31)
        for _ in range(300):
            name = ''.join(rnd.choices('İıIieĞğ Üü -/ abcXYZ9', k=rnd.randrange(0,45)))
            self.assertEqual(normalized_name(name), old_normalized_name(name))

    def test_exact_task_key_still_matching_original(self):
        for triplet in [('fizik','345 tyt fizik','Enerji'),
                        ('FİZİK','345   TYT  FİZİK','enerji'),
                        ('Türkçe','ÖRNEK','Sözcük  '),
                        (None, ['book'], True)]:
            self.assertEqual(exact_task_key(*triplet),
                             tuple(old_normalized_name(part) for part in triplet))

    def test_bounded_cache_and_repeated_names(self):
        _normalized_string.cache_clear()
        for i in range(4500):
            normalized_name(f'Konu {i}')
        self.assertLessEqual(_normalized_string.cache_info().currsize, 4096)
        _normalized_string.cache_clear()
        for _ in range(50):
            exact_task_key('fizik','345','enerji')
        self.assertGreater(_normalized_string.cache_info().hits, 0)

if __name__ == '__main__':
    unittest.main()
