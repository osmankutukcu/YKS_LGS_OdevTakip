# -*- coding: utf-8 -*-
from pathlib import Path
import pandas as pd
from openpyxl import load_workbook
from openpyxl.workbook import Workbook

# Şablon sütunları (DB ile birebir)
KOLONLAR = [
    "ad","soyad","ogr_no","ana_grup","alt_grup","veli_ad","veli_yakinlik",
    "veli_tel1","veli_tel2","ogr_tel","ogr_mail","veli_mail","dogum_tarihi","kisisel_bilgiler"
]

TEL_KOLONLARI = ["veli_tel1","veli_tel2","ogr_tel"]

def _tel_temizle(x: str) -> str:
    """
    Telefonu metin olarak normalize et (Türkiye GSM için).
    Kabul edilen örnekler:
      0546 446 1905
      5464461905
      +90 546 446 1905
      90 546 446 1905
      0905464461905
    Çıkış: 05XXXXXXXXX (11 hane) ya da "" (boş/geçersiz).
    """
    if x is None:
        return ""

    s = str(x).strip()
    if s == "" or s.lower() in {"nan", "none", "null"}:
        return ""

    # Excel'in float kalıntısı: "5464461905.0"
    if s.endswith(".0"):
        try:
            s = str(int(float(s)))
        except Exception:
            pass

    # Rakam dışını temizle: boşluk, nokta, tire, parantez vs.
    digits = "".join(ch for ch in s if ch.isdigit())

    if digits == "":
        return ""

    # Ülke kodu varyasyonları -> yerel numara
    # +90 / 90 / 090 / 0090 … gibi durumlarda baştaki 90'ı kes
    if digits.startswith("0090"):
        digits = digits[4:]
    elif digits.startswith("090"):
        digits = digits[3:]
    elif digits.startswith("90"):
        digits = digits[2:]

    # Yaygın senaryolar
    if len(digits) == 11 and digits.startswith("0"):
        # 05xxxxxxxxx -> zaten doğru
        pass
    elif len(digits) == 10 and digits.startswith("5"):
        # 5xxxxxxxxx -> başına 0 ekle
        digits = "0" + digits
    elif len(digits) >= 12 and "5" in digits:
        # +90 5xxxxxxxxx gibi uzun formlar: sondaki GSM 10 haneyi al
        # (ülke kodu ve olası baştaki 0'lar atılır)
        last10 = digits[-10:]
        if last10.startswith("5"):
            digits = "0" + last10
        # aksi halde düşecek ve geçersiz sayılacak
    else:
        # Diğer kombinasyonlar (sabit hat vb.) bu uygulamada kullanılmıyorsa boş bırak
        return ""

    # Son doğrulama: 11 hane ve 0 ile başlamalı
    if len(digits) == 11 and digits.startswith("0"):
        return digits

    # Geçersizse boş döndür (hata yerine)
    return ""


def ogrenci_sablon_olustur(dosya_yolu: Path) -> Path:
    """Telefon sütunları METİN olacak şekilde Excel şablonu üretir."""
    # Örnek/boş veri çerçevesi
    df = pd.DataFrame(columns=KOLONLAR)

    # Birkaç örnek satır (kullanıcı görsün) – hepsi string
    ornekler = []
    for i in range(1, 6):
        ornekler.append({
            "ad": f"Ad{i}",
            "soyad": f"Soyad{i}",
            "ogr_no": f"{1000+i}",
            "ana_grup": "YKS",
            "alt_grup": "mezun-say",
            "veli_ad": "",
            "veli_yakinlik": "Diğer",
            "veli_tel1": "05XXXXXXXXX",
            "veli_tel2": "",
            "ogr_tel": "05XXXXXXXXX",
            "ogr_mail": "",
            "veli_mail": "",
            "dogum_tarihi": "2008-01-01",
            "kisisel_bilgiler": ""
        })
    df = pd.concat([df, pd.DataFrame(ornekler)], ignore_index=True)

    # Önce yaz
    df.to_excel(dosya_yolu, index=False)

    # Sonra telefon sütunlarının numara biçimini '@' (Text) yap
    wb = load_workbook(dosya_yolu)
    ws = wb.active
    header = {cell.value: cell.column for cell in ws[1]}  # isim -> index

    for kol in TEL_KOLONLARI:
        if kol in header:
            col_idx = header[kol]
            for row in ws.iter_rows(min_row=2, min_col=col_idx, max_col=col_idx):
                for cell in row:
                    cell.number_format = "@"  # Text

    # Doğum tarihi için de metin formatı (yyyy-mm-dd metin girilsin)
    if "dogum_tarihi" in header:
        col_idx = header["dogum_tarihi"]
        for row in ws.iter_rows(min_row=2, min_col=col_idx, max_col=col_idx):
            for cell in row:
                cell.number_format = "@"

    wb.save(dosya_yolu)
    return dosya_yolu


def ogrenci_excel_oku(dosya_yolu: Path) -> pd.DataFrame:
    """Excel'i TÜM SÜTUNLAR STRING olarak okuyup temizler."""
    # Tüm sütunları string al; NA boş kalsın
    df = pd.read_excel(
        dosya_yolu,
        dtype=str,
        keep_default_na=False
    )

    # Eksik/yanlış başlıklar varsa tamamla ve sırala
    for k in KOLONLAR:
        if k not in df.columns:
            df[k] = ""

    df = df[KOLONLAR]  # sıralama

    # Telefonları normalize et
    for k in TEL_KOLONLARI:
        df[k] = df[k].map(_tel_temizle)

    # Doğum tarihi: Excel tarih objesi gelmiş olabilir; hepsini yyyy-mm-dd metnine çevir
    def _date_norm(x: str) -> str:
        if x is None:
            return ""
        s = str(x).strip()
        if s == "" or s.lower() in {"nan", "none", "nat"}:
            return ""
        # pandas Timestamp ya da '2025-01-02' / '01.02.2025'
        try:
            return pd.to_datetime(s).strftime("%Y-%m-%d")
        except Exception:
            return s  # bozmadan bırak
    df["dogum_tarihi"] = df["dogum_tarihi"].map(_date_norm)

    # Tüm alanları strip()
    for k in KOLONLAR:
        df[k] = df[k].astype(str).map(lambda s: s.strip() if s is not None else "")

    return df