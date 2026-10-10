# -*- coding: utf-8 -*-
"""Ödev durumlarının tek noktada okunması ve normalizasyonu.

Mevcut veritabanı değerleri yerinde dönüştürülmez: eski sürümler korunur.
"""
COMPLETED = frozenset({'tamam', 'tamamlandi', 'tamamlandı', 'yapildi', 'yapıldı',
                      'bitti', 'tamamlanmis', 'tamamlanmış', 'completed'})

def is_completed(value):
    if value is None:
        return False
    if isinstance(value, (int, bool)):
        return bool(value)
    return str(value).strip().casefold() in COMPLETED

def mobile_status(value):
    return 'tamam' if is_completed(value) else 'devam'

def status_counts(statuses):
    total = 0
    done = 0
    for value in statuses:
        total += 1
        if is_completed(value):
            done += 1
    return {'total': total, 'completed': done, 'pending': total-done,
            'success_rate': round(done*100/total) if total else 0}
