
from db import get_conn
from utils.notify import hatirlat_wp
import json

def due_tomorrow_for_student(ogrenci_id):
    con = get_conn()
    q = """
    SELECT os.ders, os.kitap, os.konu, ok.bitis_tarihi
    FROM odev_satir os
    JOIN odev_kume ok ON ok.id = os.kume_id
    WHERE os.ogrenci_id=? AND ok.bitis_tarihi = date('now','+1 day')
    """
    return [{'ders':d,'kitap':k,'konu':ko,'bitis':bt} for d,k,ko,bt in con.execute(q,(ogrenci_id,))]

def collect_numbers(ogrenci_id):
    con = get_conn()
    row = con.execute("SELECT veli_tel1, veli_tel2, ogr_tel FROM ogrenci WHERE id=?", (ogrenci_id,)).fetchone()
    nums = []
    if row:
        from utils import settings as appset
        allow_dup = (appset.ayar_get('reminder_allow_duplicate_nums', '1') == '1')
        for i in range(3):
            v = row[i]
            if v and str(v).strip():
                s = str(v).strip()
                if allow_dup or s not in nums:
                    nums.append(s)
    return nums

def build_message(sablon, ozet_list):
    parts = []
    for x in ozet_list:
        ders = (x.get('ders') or '').strip()
        kitap = (x.get('kitap') or '').strip()
        konu = (x.get('konu') or '').strip()
        has_kitap = kitap and kitap.lower() != 'none'
        has_konu = konu and konu.lower() != 'none'
        if has_kitap and has_konu:
            parts.append(f"{ders}/{kitap} – {konu}")
        elif has_konu:
            parts.append(f"{ders} – {konu}")
        elif has_kitap:
            parts.append(f"{ders}/{kitap}")
        elif ders:
            parts.append(ders)
    ozet = "; ".join(p for p in parts if p)
    return (sablon or 'Merhaba: {ozet}').replace('{ozet}', ozet)

def send_for_due_tomorrow(ogrenci_id, sablon):
    items = due_tomorrow_for_student(ogrenci_id)
    if not items: return {'sent':0,'empty':True}
    msg = build_message(sablon, items)
    nums = collect_numbers(ogrenci_id)
    if not nums: return {'sent':0,'nonum':True}
    res = hatirlat_wp(nums, msg)
    return {'sent':res.get('gonderilen',0), 'fail':res.get('fail',[])}


def overdue_for_student(ogrenci_id):
    con = get_conn()
    q = """
    SELECT os.ders, os.kitap, os.konu, ok.bitis_tarihi
    FROM odev_satir os
    JOIN odev_kume ok ON ok.id = os.kume_id
    WHERE os.ogrenci_id=? AND ok.bitis_tarihi < date('now') AND os.durum!='tamam'
    """
    return [{'ders':d,'kitap':k,'konu':ko,'bitis':bt} for d,k,ko,bt in con.execute(q,(ogrenci_id,))]

def send_for_overdue(ogrenci_id, sablon):
    items = overdue_for_student(ogrenci_id)
    if not items: return {'sent':0,'empty':True}
    msg = build_message(sablon, items)
    nums = collect_numbers(ogrenci_id)
    if not nums: return {'sent':0,'nonum':True}
    res = hatirlat_wp(nums, msg)
    return {'sent':res.get('gonderilen',0), 'fail':res.get('fail',[])}
