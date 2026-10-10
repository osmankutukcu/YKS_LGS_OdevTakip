# -*- coding: utf-8 -*-
"""Ödev başlık ve alt-satırlarının tek işlemde güncellenmesi."""
from datetime import datetime
from utils.homework_status import is_completed

def has_column(con,table,name):
    return name in {r[1] for r in con.execute(f'PRAGMA table_info("{table}")')}

def _normalize_lesson(value):
    """Yalnızca kesin ders eşleşmeleri için kullanıcıya görünen boşluk farkını yok say."""
    return ' '.join(str(value or '').replace('_', ' ').casefold().split())


def _linked_header_id(con, row):
    # ogrenci_id,kume_id,ders,konu,kitap,odev_id
    if row[5] is not None:
        # Bozuk eski bağlantılarda başka bir öğrencinin ödevi değiştirilmesin.
        linked = con.execute('SELECT ogrenci_id,kume_id FROM odev WHERE id=?', (row[5],)).fetchone()
        return row[5] if linked and linked[0] == row[0] and linked[1] == row[1] else None
    # Eski kayıtlar başlık bağlantısı içermeyebilir; ders, konu ve kitap eşleşmeli.
    # Birden fazla olasılık varsa tahminle ilişki kurmayız.
    matches = con.execute('SELECT id,ders FROM odev WHERE ogrenci_id=? AND kume_id=? AND konu_ad=? AND kitap_ad=?', (row[0], row[1], row[3], row[4])).fetchall()
    exact = [r[0] for r in matches if _normalize_lesson(r[1]) == _normalize_lesson(row[2])]
    return exact[0] if len(exact) == 1 else None


def _unlinked_children(con, header_id, header_row):
    """Eski bağlantısız alt satırlar: tek bir başlığa kesin bağlanabilenler.

    header_row: (ogrenci_id,kume_id,konu_ad,kitap_ad,ders)
    Belirsizlikte eşleştirme yapılmaz. Dönen ikinci değer, ilgisiz
    başlıklar nedeniyle ilişkilendirilemeyen satırların varlığıdır.
    """
    same = con.execute('''SELECT id,ders FROM odev_satir WHERE odev_id IS NULL
        AND ogrenci_id=? AND kume_id=? AND konu=? AND kitap=?''', header_row[:4]).fetchall()
    matching = [r[0] for r in same if _normalize_lesson(r[1]) == _normalize_lesson(header_row[4])]
    if not matching:
        return [], False
    headers = con.execute('''SELECT id,ders FROM odev WHERE ogrenci_id=? AND kume_id=?
        AND konu_ad=? AND kitap_ad=?''', header_row[:4]).fetchall()
    valid = [r[0] for r in headers if _normalize_lesson(r[1]) == _normalize_lesson(header_row[4])]
    if len(valid) == 1 and valid[0] == header_id:
        return matching, False
    return [], True


def set_single_line_done(con, line_id, done):
    columns = 'ogrenci_id,kume_id,ders,konu,kitap' + (',odev_id' if has_column(con, 'odev_satir', 'odev_id') else '')
    row = con.execute(f'SELECT {columns} FROM odev_satir WHERE id=?', (line_id,)).fetchone()
    if not row:
        return 0
    row = tuple(row) if len(row) == 6 else tuple(row) + (None,)
    status = 'tamam' if done else 'devam'
    now = datetime.now().isoformat(timespec='seconds') if done else None
    existing = con.execute('SELECT durum,tamamlanma_tarihi FROM odev_satir WHERE id=?', (line_id,)).fetchone()
    # Ağ isteğinin tekrarlanması kayıtlı tamamlanma zamanını değiştirmemeli.
    line_date = existing[1] if done and is_completed(existing[0]) and existing[1] else now
    con.execute('UPDATE odev_satir SET durum=?, tamamlanma_tarihi=? WHERE id=?',
                (status, line_date, line_id))
    header = _linked_header_id(con, row)
    if header is not None:
        if row[5] is None and has_column(con, 'odev_satir', 'odev_id'):
            con.execute('UPDATE odev_satir SET odev_id=? WHERE id=?', (header, line_id))
        # Başlık, yalnızca bütün bağlantılı satırlar tamamlanmışsa tamamdır.
        if has_column(con, 'odev_satir', 'odev_id'):
            header_row = con.execute('SELECT ogrenci_id,kume_id,konu_ad,kitap_ad,ders FROM odev WHERE id=?', (header,)).fetchone()
            unlinked, uncertain = _unlinked_children(con, header, header_row)
            for orphan_id in unlinked:
                con.execute('UPDATE odev_satir SET odev_id=? WHERE id=? AND odev_id IS NULL',
                            (header, orphan_id))
            statuses = [r[0] for r in con.execute('''SELECT durum FROM odev_satir
                WHERE odev_id=? AND ogrenci_id=? AND kume_id=?''',
                (header, row[0], row[1]))]
        else:
            # Eski şema: satırdaki ders adı da eşleşirse hesapla; başka
            # derslerin aynı adlı ödevlerini tek başlığa birleştirme.
            old_rows = con.execute("""SELECT ders,durum FROM odev_satir WHERE ogrenci_id=? AND kume_id=?
                AND konu=? AND kitap=?""", row[:2] + row[3:5]).fetchall()
            statuses = [r[1] for r in old_rows if _normalize_lesson(r[0]) == _normalize_lesson(row[2])]
        if statuses:
            complete = all(is_completed(value) for value in statuses)
            if has_column(con, 'odev_satir', 'odev_id') and uncertain:
                complete = False  # Tahmine dayalı tamamlama yok.
            old_header = con.execute('SELECT durum,tamamlanma_tarihi FROM odev WHERE id=?',(header,)).fetchone()
            completed_at = (old_header[1] if complete and old_header and is_completed(old_header[0])
                            and old_header[1] else datetime.now().isoformat(timespec='seconds') if complete else None)
            con.execute('UPDATE odev SET durum=?, tamamlanma_tarihi=? WHERE id=?',
                        ('yapildi' if complete else 'devam', completed_at, header))
    return 1

def set_headers_done(con,ids,done):
    ids=list(dict.fromkeys(i for i in ids if isinstance(i,int) and i>0))
    if not ids: return 0
    ph=','.join('?' for _ in ids)
    current=[tuple(r) for r in con.execute(f'SELECT id,durum,tamamlanma_tarihi FROM odev WHERE id IN ({ph})',ids)]
    found=[r[0] for r in current]
    if not found: return 0
    ph=','.join('?' for _ in found)
    now=datetime.now().isoformat(timespec='seconds') if done else None
    # Eski tamamlanma zamanını korur; butona tekrar basıldığında başarı
    # tarihi ileri kaymaz. Yeniden açılıp tamamlanırsa yeni tarih oluşur.
    con.executemany('UPDATE odev SET durum=?,tamamlanma_tarihi=? WHERE id=?',
                    [('yapildi' if done else 'devam',
                      old_date if done and is_completed(old_status) and old_date else now,
                      oid) for oid,old_status,old_date in current])
    if has_column(con,'odev_satir','odev_id'):
        # Bozulmuş ilişki başka öğrencinin ödevini değiştiremez.
        valid_lines=[tuple(r) for r in con.execute(f'''
            SELECT s.id,s.durum,s.tamamlanma_tarihi FROM odev_satir s
            JOIN odev h ON h.id=s.odev_id
            WHERE s.odev_id IN ({ph}) AND s.ogrenci_id=h.ogrenci_id
              AND s.kume_id=h.kume_id''',found)]
        con.executemany('UPDATE odev_satir SET durum=?,tamamlanma_tarihi=? WHERE id=?',
                        [('tamam' if done else 'devam',
                          old_date if done and is_completed(old_status) and old_date else now,
                          lid) for lid,old_status,old_date in valid_lines])
        # Eski satırlar odev_id içermiyor. Tek başlığa kesin bağlanabilen
        # birden fazla alt satır birlikte onarılır; başlık belirsizse atlanır.
        for oid in found:
            header=con.execute('SELECT ogrenci_id,kume_id,konu_ad,kitap_ad,ders FROM odev WHERE id=?',(oid,)).fetchone()
            rows, uncertain = _unlinked_children(con, oid, header)
            for orphan_id in rows:
                old_status, old_date = con.execute('SELECT durum,tamamlanma_tarihi FROM odev_satir WHERE id=?',
                                                   (orphan_id,)).fetchone()
                stamp = old_date if done and is_completed(old_status) and old_date else now
                con.execute('''UPDATE odev_satir SET odev_id=?,durum=?,tamamlanma_tarihi=?
                    WHERE id=? AND odev_id IS NULL''',
                    (oid,'tamam' if done else 'devam',stamp,orphan_id))
    else:
        # Mevcut kullanıcı şemasında odev_id olmayan eski kurulumlara uyum.
        for oid in found:
            header=con.execute('SELECT ogrenci_id,kume_id,konu_ad,kitap_ad,ders FROM odev WHERE id=?',(oid,)).fetchone()
            same_headers=con.execute("""SELECT id,ders FROM odev WHERE ogrenci_id=? AND kume_id=?
                AND konu_ad=? AND kitap_ad=?""",header[:4]).fetchall()
            same_headers=[r for r in same_headers if _normalize_lesson(r[1]) == _normalize_lesson(header[4])]
            if len(same_headers)!=1:
                continue
            lines=con.execute("""SELECT id,ders FROM odev_satir WHERE ogrenci_id=? AND kume_id=?
                AND konu=? AND kitap=?""",header[:4]).fetchall()
            for line in lines:
                if _normalize_lesson(line[1]) == _normalize_lesson(header[4]):
                    con.execute('UPDATE odev_satir SET durum=?,tamamlanma_tarihi=? WHERE id=?',
                                ('tamam' if done else 'devam',now,line[0]))
    return len(found)
