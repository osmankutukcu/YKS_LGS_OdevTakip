# -*- coding: utf-8 -*-
"""
services/web_service.py (PRO)

- YKS/LGS/MSÜ sayaçları (cache + fallback)
- Resmî duyurular: ÖSYM + MEB (çift regex fallback)
- Google News RSS
- Offline cache
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import sqlite3
import ssl
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple

try:
    import certifi
except ImportError:
    certifi = None
from PyQt6.QtCore import QThread, pyqtSignal


@dataclass
class FeedItem:
    source: str
    title: str
    url: str
    published: str = ""
    score: int = 0
    tags: str = ""


# -----------------------------
# 60+ Kapsamlı Çevrimdışı Pedagojik Bilgi Bankası
# (İnternetsiz ortamda zengin, profesyonel koçluk ve sınav taktikleri)
# -----------------------------
OFFLINE_KNOWLEDGE_BASE: List[FeedItem] = [
    # 1. PDR & Rehberlik & Zihin Yönetimi
    FeedItem(source="REHBERLİK", title="Turlama Tekniği: İlk turda bildiğin ve hızlı çözdüğün soruları yap, vakit alanları işaretleyip 2. tura bırak.", url="", tags="REHBERLİK,SINAV", score=80),
    FeedItem(source="PDR", title="Soru Kökü Kuralı: Soruyu okumadan önce altı çizili veya olumsuz ('değildir', 'ulaşılamaz') ifadeleri daire içine al.", url="", tags="REHBERLİK,DİKKAT", score=78),
    FeedItem(source="KOÇ", title="Biyolojik Saat: Sınava 90 gün kala her gün 07:00'de uyanarak beynini saat 10:15'teki sınav zirvesine hazırla.", url="", tags="REHBERLİK,BİYOLOJİ", score=76),
    FeedItem(source="PDR", title="Sınav Kaygısı Yönetimi: Kaygılandığında 4 saniye burnundan nefes al, 4 saniye tut ve 8 saniyede yavaşça ver (4-7-8 kuralı).", url="", tags="REHBERLİK,KAYGI", score=75),
    FeedItem(source="KOÇ", title="İç Disiplin: Motivasyon başlamanı sağlar, ancak hedeflediğin dereceye sadece 'sürdürülebilir alışkanlıklar' ulaştırır.", url="", tags="REHBERLİK,MOTİVASYON", score=74),
    FeedItem(source="PDR", title="Optik Kodlama Ritmi: Kodlamayı sona bırakmak kaydırma riskini %80 artırır; sayfa sayfa veya soru soru kodla.", url="", tags="REHBERLİK,TAKTIK", score=73),
    FeedItem(source="KOÇ", title="Zor Soru Efsanesi: Sınavda en zor soru ile en kolay sorunun standart sapma hariç puan değeri aynıdır; inatlaşma!", url="", tags="REHBERLİK,STRATEJİ", score=72),
    FeedItem(source="PDR", title="Kıyaslama Tuzağı: Kendini başkalarının netleriyle değil, dünkü kendi performansınla kıyasla; gelişim kişiseldir.", url="", tags="REHBERLİK,MOTİVASYON", score=70),

    # 2. YKS / TYT / AYT Taktikleri
    FeedItem(source="YKS", title="TYT Paragraf Çözme Formülü: Günde sabah aç karna çözülen 20-25 paragraf sorusu, 3 ayda netlerini 6-8 net yukarı taşır.", url="", tags="YKS,TYT,TÜRKÇE", score=85),
    FeedItem(source="YKS", title="TYT Matematik Problem Çözümü: Problemleri okurken verilenleri ve isteneni kenara mini sembollerle not ederek oku.", url="", tags="YKS,TYT,MATEMATİK", score=84),
    FeedItem(source="YKS", title="AYT Matematik Derinliği: AYT'de formül ezberi değil, formülün 'nereden çıktığı' sorulur; ispatları gözden geçir.", url="", tags="YKS,AYT,MATEMATİK", score=83),
    FeedItem(source="YKS", title="TYT Fen Hızlandırma: Fizik, Kimya ve Biyoloji TYT'de 20 netlik büyük bir fırsattır; temel kavramları ihmal etme.", url="", tags="YKS,TYT,FEN", score=82),
    FeedItem(source="YKS", title="AYT Fizik Vektör ve Kuvvet: Mekanik konularını sağlamlaştırmadan elektrik ve manyetizmaya geçmek kavram yanılgısı yaratır.", url="", tags="YKS,AYT,FİZİK", score=81),
    FeedItem(source="YKS", title="AYT Edebiyat Hafıza Sarayı: Dönem yazarlarını ve eserlerini kronolojik haritalar ve anahtar kavram kartlarıyla kodla.", url="", tags="YKS,AYT,EDEBİYAT", score=80),
    FeedItem(source="YKS", title="TYT Sosyal Netleri: Tarih ve Coğrafya'da son 10 yılın çıkmış sorularını taramak net artışının en hızlı yoludur.", url="", tags="YKS,TYT,SOSYAL", score=79),
    FeedItem(source="YKS", title="AYT Biyoloji Şema Çizimi: Hücresel solunum, fotosentez ve protein sentezini beyaz bir kağıda bakmadan çizerek çalış.", url="", tags="YKS,AYT,BİYOLOJİ", score=78),
    FeedItem(source="YKS", title="AYT Kimya Hesaplamaları: Mol, gazlar ve denge ünitelerinde birim dönüşümlerine dikkat etmek işlem hatasını önler.", url="", tags="YKS,AYT,KİMYA", score=77),
    FeedItem(source="YKS", title="Geometri Görme Sanatı: Soruda verilen tüm ek bilgileri (paralellik, açıortay, kenarortay) şeklin üzerine aktar.", url="", tags="YKS,GEOMETRİ", score=76),

    # 3. LGS Taktikleri & Sözel Mantık
    FeedItem(source="LGS", title="LGS Sözel Mantık: Şifre, sıralama ve tablo sorularında metni okurken mutlaka eşzamanlı bir tablo kur.", url="", tags="LGS,TÜRKÇE,MANTIK", score=85),
    FeedItem(source="LGS", title="LGS Matematik Yeni Nesil: Soru kökünü ve verilen şekli önce incele; uzun metin seni korkutmasın, ipucu şekildedir.", url="", tags="LGS,MATEMATİK", score=84),
    FeedItem(source="LGS", title="LGS Fen Bağımsız Değişken: Deney sorularında senin değiştirdiğin 'bağımsız değişken', sonucu etkilenen 'bağımlı değişken'dir.", url="", tags="LGS,FEN", score=83),
    FeedItem(source="LGS", title="LGS İnkılap Tarihi: Mustafa Kemal'in kişilik özelliklerini (ileri görüşlülük, teşkilatçılık, vatanseverlik) olaylarla eşleştir.", url="", tags="LGS,İNKILAP", score=80),
    FeedItem(source="LGS", title="LGS İngilizce Kelime Defteri: Ünite kelimelerini sadece Türkçe anlamıyla değil, cümle içindeki eşanlamlılarıyla öğren.", url="", tags="LGS,İNGİLİZCE", score=78),
    FeedItem(source="LGS", title="LGS Din Kültürü Kavramları: Kader, tevekkül, sadaka-i cariye ve zekat oranlarını zihin haritası üzerinde görselleştir.", url="", tags="LGS,DİN", score=77),
    FeedItem(source="LGS", title="LGS Süre Yönetimi: Sayısal bölümde soru başına 2 dakika kuralını aşma; 3 dakikayı geçen soruya işaret koyup geç.", url="", tags="LGS,ZAMAN", score=81),

    # 4. Odaklanma & Zaman Yönetimi (Pomodoro & Deep Work)
    FeedItem(source="ODAK", title="Pomodoro 25/5 Metodu: 25 dakika kesintisiz tek derse odaklan, 5 dakika ekrandan uzak mola ver; 4 set sonra 30 dk dinlen.", url="", tags="ODAK,POMODORO", score=79),
    FeedItem(source="ODAK", title="Ultradian Ritim (50/10): İleri düzey deneme çözümlerinde 50 dakika derin odaklanma + 10 dakika göz dinlendirme uygula.", url="", tags="ODAK,ZAMAN", score=78),
    FeedItem(source="ODAK", title="Dijital Detoks Kuralı: Çalışma masasında telefon bulundurmak, dokunmasan bile bilişsel kapasiteyi %20 azaltır; telefonu başka odaya bırak.", url="", tags="ODAK,DİJİTAL", score=82),
    FeedItem(source="ODAK", title="Günün En Zor Dersi Kuralı: İrade gücü sabah en yüksektir; en çok zorlandığın dersi ilk çalışma seansına koy.", url="", tags="ODAK,PLAN", score=76),
    FeedItem(source="ODAK", title="Masa Düzeni: Masanda yalnızca o an çalıştığın kitap, defter ve kalem olsun; diğer kitapların kalabalığı dikkat dağıtır.", url="", tags="ODAK,ORTAM", score=74),

    # 5. Akıllı Tekrar (Spaced Repetition) & Öğrenme Teknikleri
    FeedItem(source="TEKRAR", title="1-7-30 Gün Kuralı: Öğrenilen bilginin %70'i ilk 24 saatte unutulur; 1 gün, 7 gün ve 30 gün sonra yapılan 15 dk'lık tekrarlar kalıcılığı sağlar.", url="", tags="TEKRAR,HAFIZA", score=85),
    FeedItem(source="METOT", title="Feynman Öğrenme Tekniği: Bir konuyu tam anladığını test etmek için konuyu 10 yaşındaki bir çocuğa anlatır gibi sade bir dille anlat.", url="", tags="TEKRAR,FEYNMAN", score=82),
    FeedItem(source="TEKRAR", title="Hata Defteri Mucizesi: Denemelerde yanlış yaptığın soruları kesip yapıştır; haftada bir bu defteri sıfırdan çöz, netlerin zıplasın.", url="", tags="TEKRAR,ANALİZ", score=84),
    FeedItem(source="METOT", title="Aktif Hatırlama (Active Recall): Kitabı okuyup altını çizmek pasiftir; sayfayı kapatıp 'Ben az önce ne öğrendim?' diye kendine sor.", url="", tags="TEKRAR,ÖĞRENME", score=81),
    FeedItem(source="METOT", title="Leitner Flashcard Sistemi: Bilgi kartlarını 3 kutuya ayır; bildiklerini haftada 1, zorlandıklarını her gün tekrar et.", url="", tags="TEKRAR,FLASHCARD", score=77),

    # 6. Deneme Sınavı Analizi & Net Artırma Stratejisi
    FeedItem(source="ANALİZ", title="Deneme Otopsisi: Deneme bittikten sonra harcanan 1 saat, sınav anındaki 2 saatten daha değerlidir; her yanlışı tek tek incele.", url="", tags="ANALİZ,DENEME", score=85),
    FeedItem(source="ANALİZ", title="3 Hata Kategorisi: Yanlışını sınıflandır: A) Bilgi eksikliği mi? B) İşlem/Dikkat hatası mı? C) Süre yetersizliği mi?", url="", tags="ANALİZ,NET", score=83),
    FeedItem(source="ANALİZ", title="Boş Bırakma Cesareti: Emin olmadığın sorularda şansını denemek yerine boş bırakmak 4 yanlışın 1 doğruyu götürmesini engeller.", url="", tags="ANALİZ,STRATEJİ", score=82),
    FeedItem(source="ANALİZ", title="Branş Denemesi Köprüsü: Genel denemelerden önce haftada 2 branş denemesi (ör. Türkçe, Matematik) çözerek kondisyon kazan.", url="", tags="ANALİZ,BRANŞ", score=80),
    FeedItem(source="ANALİZ", title="Sınav Sıralama Stratejisi: Denemelerde hangi dersten başlayacağını ve ders sıranı sabitle; gerçek sınavda asla yeni taktik deneme.", url="", tags="ANALİZ,RUTİN", score=81),

    # 7. Sağlık, Bilişsel Performans & Beslenme
    FeedItem(source="SAĞLIK", title="Beyin ve Su: Beynin %75'i sudur; çalışma masanda su bulundur ve her 45 dakikada bir yarım bardak su içerek odaklanmayı koru.", url="", tags="SAĞLIK,BEYİN", score=75),
    FeedItem(source="SAĞLIK", title="Uyku ve Bellek Konsolidasyonu: Gün içinde çalışılan bilgiler REM uykusunda uzun süreli hafızaya kaydedilir; en az 7 saat uyu.", url="", tags="SAĞLIK,UYKU", score=78),
    FeedItem(source="SAĞLIK", title="Kan Şekeri Dengesi: Çalışırken şekerli abur cuburlar ani kan şekeri dalgalanmasıyla uyku yapar; kuruyemiş ve meyve tercih et.", url="", tags="SAĞLIK,BESLENME", score=73),
    FeedItem(source="SAĞLIK", title="Masabaşı Göz Dinlendirme (20-20-20): Her 20 dakikada bir, 20 saniye boyunca 20 feet (6 metre) uzağa bakarak göz kaslarını gevşet.", url="", tags="SAĞLIK,GÖZ", score=71),
    FeedItem(source="SAĞLIK", title="Kısa Yürüyüş Terapisi: 4 saatlik yoğun masabaşı çalışmasından sonra 15 dakikalık tempolu açık hava yürüyüşü zihni sıfırlar.", url="", tags="SAĞLIK,HAREKET", score=72),

    # 8. Takvim & Dönemsel Koçluk Yol Haritası
    FeedItem(source="KOÇ", title="Güz Dönemi Kuralı (İlk Aylar): Konu eksiklerini kapatma dönemidir; deneme netlerine takılmadan konu hakimiyetini tamamla.", url="", tags="TAKVİM,STRATEJİ", score=79),
    FeedItem(source="KOÇ", title="Kış Dönemi (Sömestr Kampı): Eksik konuları eritme ve branş denemeleriyle hız kazanma evresidir; günde 2 seans soru çöz.", url="", tags="TAKVİM,KAMP", score=80),
    FeedItem(source="KOÇ", title="Bahar Dönemi (Son 3 Ay): Genel deneme maratonu başlar; haftada en az 3 genel deneme çözüp eksik konulardan nokta atışı yap.", url="", tags="TAKVİM,SONDÖNEM", score=82),
    FeedItem(source="KOÇ", title="Son Ay Çıkmış Sorular: Son 7 yılın MEB ve ÖSYM çıkmış sınav sorularını tıpkı gerçek sınav saatinde masa başında süreyle çöz.", url="", tags="TAKVİM,ÇIKMIŞ", score=84),
    FeedItem(source="KOÇ", title="Son Hafta Sakinliği: Ağır yeni konu öğrenilmez; sadece formül kağıtları, özet notlar incelenir ve biyolojik ritim oturtturulur.", url="", tags="TAKVİM,SONHAFTA", score=81),

    # 9. Maarif Modeli & Yeni Nesil Soru Stratejileri
    FeedItem(source="MÜFREDAT", title="Türkiye Yüzyılı Maarif Modeli: Ezber yerine beceri temelli, eleştirel düşünme ve problem çözme odaklı sorular ön plandadır.", url="", tags="MÜFREDAT,BECERİ", score=83),
    FeedItem(source="MÜFREDAT", title="Disiplinlerarası Sorular: Fen ve Matematik kesişimindeki grafik modellemeleri ile Türkçe ve Sosyal metin analizlerine ağırlık ver.", url="", tags="MÜFREDAT,ANALİZ", score=82),
    FeedItem(source="MÜFREDAT", title="Kavramsal Derinlik: Tanımları ezberlemek yerine 'Bu kural günlük hayatta nerede karşımıza çıkar?' sorusuyla derinleş.", url="", tags="MÜFREDAT,KAVRAM", score=79),
    FeedItem(source="MÜFREDAT", title="Görsel ve Grafik Okuryazarlığı: Tablo, pasta grafik, infografik ve akış şemalarını doğru yorumlama becerisini geliştir.", url="", tags="MÜFREDAT,GRAFİK", score=80),

    # 10. Motivasyon & Zihinsel Dayanıklılık (Resilience)
    FeedItem(source="MOTİVASYON", title="Net Düşüşü Doğaldır: Konu çalışırken geçici olarak deneme netleri dalgalanabilir; yeni bilgi oturana kadar sabırlı ol.", url="", tags="MOTİVASYON,DİRENÇ", score=77),
    FeedItem(source="MOTİVASYON", title="Kazananların Farkı: Başarılı öğrencilerin sırrı üstün zeka değil; yorulduğunda dahi o masaya oturabilme disiplinidir.", url="", tags="MOTİVASYON,DİSİPLİN", score=80),
    FeedItem(source="MOTİVASYON", title="Kendi Hikayeni Yaz: Bugün harcadığın her ter damlası, yarın gururla anlatacağın başarı hikayenin birer cümlesidir.", url="", tags="MOTİVASYON,İNANÇ", score=78),
    FeedItem(source="MOTİVASYON", title="Tükenmişlik Hissi (Burnout): Yorulduğunda pes etme, dinlenmeyi öğren; haftada yarım günü mutlaka kendine ve sevdiklerine ayır.", url="", tags="MOTİVASYON,DENGE", score=76),
    FeedItem(source="MOTİVASYON", title="Görselleştirme Tekniği: Her gece uyumadan önce kendini hedeflediğin üniversite veya lisenin kapısından içeri girerken hayal et.", url="", tags="MOTİVASYON,HEDEF", score=75),
    FeedItem(source="REHBERLİK", title="Aktif Hatırlama (Active Recall): Kitabı kapatıp aklında kalanı boş kağıda yazmak, pasif okumadan 3 kat daha kalıcı öğrenme sağlar.", url="", tags="REHBERLİK,ÖĞRENME", score=88),
    FeedItem(source="KOÇ", title="Gerçek Sınav Simülasyonu: Hafta sonu denemelerini sabah 10:15'te, optik form ve kurşun kalemle gerçek sınav şartlarında çöz.", url="", tags="KOÇ,DENEME", score=86),
    FeedItem(source="PDR", title="Sınav Stresi ve Nefes Kontrolü: 4 saniye burundan derin nefes al, 4 saniye tut, 6 saniye yavaşça ver (4-4-6 tekniği nabzı dengeler).", url="", tags="PDR,SAĞLIK", score=84)
]


# -----------------------------
# DB Cache
# -----------------------------
def _try_get_main_db_conn() -> Optional[sqlite3.Connection]:
    try:
        import db  # type: ignore
        if hasattr(db, "get_conn"):
            return db.get_conn()  # type: ignore
    except Exception:
        pass
    return None


def _fallback_cache_path() -> str:
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "web_cache.db")


def _get_cache_conn() -> sqlite3.Connection:
    con = _try_get_main_db_conn()
    if con is not None:
        return con
    return sqlite3.connect(_fallback_cache_path())


def _ensure_tables(con: sqlite3.Connection) -> None:
    try:
        con.execute("""
            CREATE TABLE IF NOT EXISTS web_note_cache (
                cache_key TEXT PRIMARY KEY,
                json_data TEXT NOT NULL,
                fetched_at TEXT NOT NULL
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS exam_date_cache (
                exam_key TEXT PRIMARY KEY,
                iso_date TEXT NOT NULL,
                source TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        con.commit()
    except Exception:
        pass


def _cache_set(con: sqlite3.Connection, key: str, data: dict) -> None:
    _ensure_tables(con)
    try:
        con.execute(
            "INSERT OR REPLACE INTO web_note_cache (cache_key, json_data, fetched_at) VALUES (?, ?, ?)",
            (key, json.dumps(data, ensure_ascii=False), dt.datetime.now().isoformat(timespec="seconds"))
        )
        con.commit()
    except Exception:
        pass


def _cache_get(con: sqlite3.Connection, key: str) -> Optional[dict]:
    try:
        _ensure_tables(con)
        row = con.execute("SELECT json_data FROM web_note_cache WHERE cache_key=?", (key,)).fetchone()
        if not row:
            return None
        return json.loads(row[0])
    except Exception:
        return None


def _exam_cache_set(con: sqlite3.Connection, exam_key: str, iso_date: str, source: str) -> None:
    _ensure_tables(con)
    try:
        con.execute(
            "INSERT OR REPLACE INTO exam_date_cache (exam_key, iso_date, source, updated_at) VALUES (?, ?, ?, ?)",
            (exam_key, iso_date, source, dt.datetime.now().isoformat(timespec="seconds"))
        )
        con.commit()
    except Exception:
        pass


def _exam_cache_get(con: sqlite3.Connection, exam_key: str) -> Optional[Tuple[str, str]]:
    try:
        _ensure_tables(con)
        row = con.execute("SELECT iso_date, source FROM exam_date_cache WHERE exam_key=?", (exam_key,)).fetchone()
        if not row:
            return None
        return str(row[0]), str(row[1])
    except Exception:
        return None


# -----------------------------
# HTTP/RSS
# -----------------------------
def _urlopen(url: str, timeout: int = 6) -> bytes:
    if certifi:
        context = ssl.create_default_context(cafile=certifi.where())
    else:
        # Fallback if certifi is missing: use unverified context or default
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (YKS-LGS-OdevTakip/PRO)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(req, context=context, timeout=timeout) as resp:
        return resp.read()


def _safe_text(x: Any) -> str:
    return "" if x is None else str(x).strip()


def _clean_news_title(title: str) -> str:
    title = re.sub(r"\s+", " ", title).strip()
    if " - " in title:
        title = title.rsplit(" - ", 1)[0].strip()
    return title


def _parse_google_news_rss(xml_bytes: bytes, limit: int = 8) -> List[FeedItem]:
    items: List[FeedItem] = []
    try:
        root = ET.fromstring(xml_bytes)
    except Exception:
        return items

    count = 0
    for it in root.findall(".//item"):
        title = _clean_news_title(_safe_text(it.findtext("title")))
        link = _safe_text(it.findtext("link"))
        pub = _safe_text(it.findtext("pubDate"))
        if not title or not link:
            continue
        items.append(FeedItem(source="NEWS", title=title, url=link, published=pub, tags=""))
        count += 1
        if count >= limit:
            break
    return items


def _html_strip_tags(s: str) -> str:
    s = re.sub(r"<script.*?>.*?</script>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<style.*?>.*?</style>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# -----------------------------
# Resmî Kaynaklar (Çift Regex Fallback)
# -----------------------------
def _fetch_osym_duyuru_titles(limit: int = 10) -> List[FeedItem]:
    items: List[FeedItem] = []
    try:
        html = _urlopen("https://www.osym.gov.tr/tr%2C10188/duyurular.html", timeout=8).decode("utf-8", "ignore")
    except Exception:
        return items

    seen = set()

    # 1) Eski/klasik desen
    rx1 = re.compile(r'href="([^"]+TR%2C\d+\/[^"]+\.html)"[^>]*>([^<]{6,220})</a>', re.I)

    # 2) Fallback desen (sayfa şablonu değişirse)
    rx2 = re.compile(
        r'<a[^>]+href="([^"]+\.html)"[^>]*>\s*([^<]{6,240})\s*</a>',
        re.I
    )

    def add(url: str, title: str):
        title = _html_strip_tags(title)
        title = re.sub(r"\s+", " ", title).strip()
        if not title:
            return
        if not url.startswith("http"):
            url = "https://www.osym.gov.tr/" + url.lstrip("/")
        key = (title, url)
        if key in seen:
            return
        seen.add(key)
        items.append(FeedItem(source="ÖSYM", title=title, url=url, tags=""))

    # rx1
    for m in rx1.finditer(html):
        add(m.group(1).strip(), m.group(2).strip())
        if len(items) >= limit:
            return items

    # rx2 (sadece ÖSYM içeriklerini filtreleyelim)
    for m in rx2.finditer(html):
        href = m.group(1).strip()
        title = m.group(2).strip()
        # duyuru sayfasındaki linkleri tercih
        if "tr%2C" in href.lower() or "duyuru" in href.lower() or "TR%2C" in href:
            add(href, title)
        if len(items) >= limit:
            break

    return items


def _fetch_meb_duyuru_titles(limit: int = 10) -> List[FeedItem]:
    items: List[FeedItem] = []
    try:
        html = _urlopen("https://www.meb.gov.tr/meb_duyuruindex.php", timeout=8).decode("utf-8", "ignore")
    except Exception:
        return items

    seen = set()

    # 1) tarih + link + başlık
    rx1 = re.compile(
        r"(\d{2}/\d{2}/\d{4}).{0,260}?href=['\"]([^'\"]+)['\"].{0,260}?>([^<]{6,260})<",
        re.I | re.S
    )

    # 2) fallback: sadece link+başlık
    rx2 = re.compile(
        r'href=[\'"]([^\'"]+)[\'"][^>]*>\s*([^<]{6,260})\s*</a>',
        re.I
    )

    def add(date_text: str, url: str, title: str):
        title = _html_strip_tags(title)
        title = re.sub(r"\s+", " ", title).strip()
        if not title:
            return
            
        # --- BLACKLIST FİLTRESİ ---
        # MEB sayfalarında footer/menu linklerini yanlışlıkla duyuru sanmaması için
        ignored = [
            "erişilebilirlik", "site haritası", "iletişim", "english", 
            "basın müşavirliği", "bakanlık", "kurumsal", 
            "meb bilişim sistemleri", "tüm hakları saklıdır",
            "gizlilik", "yasal uyarı"
        ]
        t_lower = title.lower()
        if any(ign in t_lower for ign in ignored):
            return
        # --------------------------

        if not url.startswith("http"):
            url = "https://www.meb.gov.tr/" + url.lstrip("/")
        full_title = f"{date_text} — {title}" if date_text else title
        key = (full_title, url)
        if key in seen:
            return
        seen.add(key)
        items.append(FeedItem(source="MEB", title=full_title, url=url, tags=""))

    # rx1
    for m in rx1.finditer(html):
        add(m.group(1).strip(), m.group(2).strip(), m.group(3).strip())
        if len(items) >= limit:
            return items

    # rx2 (meb duyuru linklerini filtrele)
    for m in rx2.finditer(html):
        href = m.group(1).strip()
        title = m.group(2).strip()
        if "meb.gov.tr" in href or "duyuru" in href.lower() or "meb_duyuru" in href.lower() or "duyuru" in title.lower():
            add("", href, title)
        if len(items) >= limit:
            break

    return items


def _fetch_meb_haberler_titles(limit: int = 8) -> List[FeedItem]:
    items: List[FeedItem] = []
    try:
        html = _urlopen("https://www.meb.gov.tr/meb_haberindex.php", timeout=7).decode("utf-8", "ignore")
    except Exception:
        return items

    seen = set()
    rx = re.compile(r'href=[\'"]([^\'"]*haber[^\'"]*)[\'"][^>]*>\s*([^<]{8,260})\s*</a>', re.I)
    for m in rx.finditer(html):
        href = m.group(1).strip()
        title = _html_strip_tags(m.group(2).strip())
        title = re.sub(r"\s+", " ", title).strip()
        if not title or len(title) < 10:
            continue
        if any(x in title.lower() for x in ["site haritası", "iletişim", "bakanlık", "kurumsal", "tüm hakları"]):
            continue
        if not href.startswith("http"):
            href = "https://www.meb.gov.tr/" + href.lstrip("/")
        key = (title, href)
        if key not in seen:
            seen.add(key)
            items.append(FeedItem(source="MEB", title=title, url=href, tags="MEB,HABER"))
        if len(items) >= limit:
            break
    return items


# -----------------------------
# Scoring / Tagging
# -----------------------------
def _exam_relevance_score(title: str) -> int:
    t = title.lower()
    score = 0
    if ("yks" in t) or ("tyt" in t) or ("ayt" in t) or ("yükseköğretim kurumları sınavı" in t):
        score += 10
    if ("lgs" in t) or ("liselere geçiş" in t):
        score += 10
    if ("msü" in t) or ("milli savunma üniversitesi" in t):
        score += 10

    for kw, w in [
        ("başvuru", 4), ("kılavuz", 4), ("takvim", 4), ("son gün", 4),
        ("giriş belgesi", 4), ("sonuç", 4), ("tercih", 4), ("yerleştirme", 4),
        ("değişiklik", 5), ("duyuru", 2), ("sınav", 2),
        ("rehberlik", 3), ("tavsiye", 3), ("uzman", 3), ("psikolog", 3),
        ("analiz", 5), ("değerlendirme", 5), ("maarif", 5), ("müfredat", 5),
        ("strateji", 4), ("taktik", 4), ("yeni model", 5),
        ("yeni sınav sistemi", 6), ("sistem değişikliği", 6),
    ]:
        if kw in t:
            score += w

    return score


def _source_weight(src: str) -> int:
    if src == "ÖSYM":
        return 40
    if src == "MEB":
        return 35
    return 15


def _infer_item_tags(title: str) -> str:
    t = title.lower()
    tags: List[str] = []
    if any(k in t for k in ["başvuru", "kılavuz", "takvim", "son gün", "tarih", "giriş belgesi"]):
        tags.append("TAKVİM")
    if any(k in t for k in ["sonuç", "yerleştirme", "tercih"]):
        tags.append("SÜREÇ")
    if any(k in t for k in ["uzman", "rehberlik", "psikolog", "tavsiye", "öneri"]):
        tags.append("UZMAN")
    if any(k in t for k in ["analiz", "değerlendirme", "yorum", "zorluk", "dağılım"]):
        tags.append("ANALİZ")
    if any(k in t for k in ["maarif", "müfredat", "yeni model", "değişiklik", "sistem"]):
        tags.append("MÜFREDAT")
    if any(k in t for k in ["yks", "tyt", "ayt"]):
        tags.append("YKS")
    if "lgs" in t:
        tags.append("LGS")
    if "msü" in t:
        tags.append("MSÜ")
    if any(k in t for k in ["duyuru", "kılavuz", "takvim"]):
        tags.append("RESMÎ")
    return ",".join(dict.fromkeys(tags))


def _rank_items(items: List[FeedItem]) -> List[FeedItem]:
    ranked: List[FeedItem] = []
    seen = set()
    for it in items:
        if not it.url:
            continue
        if it.url in seen:
            continue
        seen.add(it.url)
        it.tags = _infer_item_tags(it.title)
        it.score = _source_weight(it.source) + _exam_relevance_score(it.title)
        ranked.append(it)
    ranked.sort(key=lambda x: x.score, reverse=True)
    return ranked


# -----------------------------
# Çevrimdışı Pedagojik Bülten Üretici
# -----------------------------
def _build_offline_content(countdown: Dict[str, int]) -> Tuple[str, str, List[FeedItem]]:
    top_items = list(OFFLINE_KNOWLEDGE_BASE)
    yks_days = countdown.get("YKS", 180)
    lgs_days = countdown.get("LGS", 180)
    msu_days = countdown.get("MSÜ", 90)

    lines: List[str] = [
        "🎯 Çevrimdışı Koçluk & Sınav Stratejisi Bilgi Bankası (Aktif)",
        "",
        f"⏱️ Sınav Sayaçları: YKS'ye {yks_days} gün | LGS'ye {lgs_days} gün | MSÜ'ye {msu_days} gün",
        "",
        "🧠 Günün Öne Çıkan Pedagojik Stratejileri:",
        "• Turlama Tekniği: Sınavda ilk turda sadece emin olduğun ve hızlı çözülen soruları yap; zor sorularla inatlaşma.",
        "• 1-7-30 Kuralı: Öğrenilen konunun %70'i ilk 24 saatte unutulur; 1 gün, 7 gün ve 30 gün sonra soru çözerek kalıcılaştır.",
        "• Deneme Otopsisi: Yanlışlarını bilgi eksikliği, dikkat hatası ve süre yetersizliği olarak 3 kategoriye ayırıp analiz et.",
        "• Pomodoro / Derin Odak: 25 dk tek bir derse tam odaklanma + 5 dk mola ile zihinsel verimini %40 artır.",
        "• Hata Defteri: Denemelerde yanlış yaptığın veya boş bıraktığın soruları kesip yapıştır; pazar günleri yeniden çöz.",
        "• Biyolojik Saat: Sınava son aylarda her sabah 07:00'de uyanarak zihnini 10:15 sınav saatine alıştır.",
        "",
        "ℹ️ Not: İnternet bağlantısı olmasa dahi 60'tan fazla uzman koçluk kartı kesintisiz dönüşümlü sunulmaktadır.",
        "📌 Kaynak: Yerel Pedagojik & Bilişsel Eğitim Rehberi."
    ]

    return ("\n".join(lines), "REHBERLİK", top_items)


# -----------------------------
# Analysis Builder (Çevrimiçi / Hibrit)
# -----------------------------
def _build_professional_analysis(ranked: List[FeedItem], countdown: Dict[str, int] | None = None) -> Tuple[str, str, List[FeedItem]]:
    if not ranked:
        return _build_offline_content(countdown or {})

    top = ranked[:14]
    
    # --- Akıllı Manşet Seçimi (Hero Headline) ---
    hero_title = ""
    crit_keywords = ["açıklandı", "yayınlandı", "başvuru", "son gün", "sınav giriş", "tercih", "yerleştirme", "tarihleri"]
    officials = [x for x in top if x.source in ["ÖSYM", "MEB"]]
    news = [x for x in top if x.source == "NEWS"]

    best_official = officials[0] if officials else None
    
    if best_official and any(k in best_official.title.lower() for k in crit_keywords):
        hero_title = f"⚡ {best_official.source}: {best_official.title}"
    elif best_official:
        hero_title = f"📢 {best_official.source}: {best_official.title}"
    elif news:
        hero_title = f"🔥 Gündem: {news[0].title}"
    else:
        hero_title = "📌 Güncel Eğitim & Koçluk Gündemi"

    blob = " ".join([it.title.lower() for it in top])

    tag = "BİLGİ"
    if any(k in blob for k in ["başvuru", "kılavuz", "takvim", "son gün", "giriş belgesi", "tarih"]):
        tag = "TAKVİM"
    elif any(k in blob for k in ["sonuç", "tercih", "yerleştirme"]):
        tag = "SÜREÇ"
    elif any(k in blob for k in ["duyuru", "kılavuz"]):
        tag = "DUYURU"
    elif any(k in blob for k in ["rehberlik", "taktik", "pomodoro", "analiz"]):
        tag = "REHBERLİK"

    lines: List[str] = []
    lines.append(hero_title)
    lines.append("")

    osym = [x for x in top if x.source == "ÖSYM"][:4]
    meb = [x for x in top if x.source == "MEB"][:4]
    news = [x for x in top if x.source == "NEWS"][:6]

    if osym:
        lines.append("✅ ÖSYM (Resmî):")
        for it in osym:
            lines.append(f"• {it.title}")
        lines.append("")

    if meb:
        lines.append("✅ MEB (Resmî):")
        for it in meb:
            lines.append(f"• {it.title}")
        lines.append("")

    if news:
        lines.append("📰 Güncel Haber Başlıkları:")
        for it in news:
            lines.append(f"• {it.title}")
        lines.append("")

    tips: List[str] = [
        "Turlama Tekniği: Soruyla inatlaşma; ilk turda bildiklerini yap, zor olanları 2. tura işaretle.",
        "1-7-30 Tekrarı: 24 saat, 7 gün ve 30 gün aralıklı tekrarlarla unutma eğrisini kır.",
        "Deneme Otopsisi: Her deneme sonrası yanlışlarını bilgi, dikkat veya zaman hatası olarak sınıflandır."
    ]

    if tag == "TAKVİM":
        tips += [
            "Takvim/başvuru duyurusu: 'Son gün' ve 'resmî ekran' detaylarını teyit et.",
            "Planlama: Sınav/başvuru tarihini değil, 'son günün bir gün öncesini' takvime işaretle.",
        ]
    if tag == "SÜREÇ":
        tips += [
            "Sonuç/tercih: Ekranda gördüğün resmi veriyi kaydet; sosyal medyadaki söylentilere takılma.",
            "Belge: Kayıt/başvuru evraklarını son dakikaya bırakma.",
        ]

    if any("YKS" in (it.tags or "") for it in top):
        tips.append("YKS: Deneme analizinde 'yanlış' kadar 'boş' da altın değerindedir.")
    if any("LGS" in (it.tags or "") for it in top):
        tips.append("LGS: Paragraf hızını artırmak için her gün 20 dk süreli okuma yap.")
    if any("MSÜ" in (it.tags or "") for it in top):
        tips.append("MSÜ: Hız yönetimi için turlama tekniğini denemelerde uygula.")
    
    if any("MÜFREDAT" in (it.tags or "") for it in top):
        tips.append("📢 Müfredat/Sistem: Değişiklik haberlerini dikkatle incele, çalışma planını buna göre güncelle.")
    
    if any("ANALİZ" in (it.tags or "") for it in top):
        tips.append("📊 Sınav Analizi: Uzmanların 'zorluk' ve 'soru dağılımı' yorumlarını dikkate al.")

    if any("UZMAN" in (it.tags or "") for it in top):
        tips.append("Uzman Notu: Tavsiyeleri kendi haftalık planına 'eylem' olarak ekle.")

    if tips:
        lines.append("🧠 Kısa Analiz & Tavsiyeler:")
        for t in tips[:6]:
            lines.append(f"• {t}")
        lines.append("")

    lines.append("ℹ️ Kaynak: Resmî kurumlar, haber servisleri ve pedagojik bilgi bankası.")

    return ("\n".join(lines), tag, top)


# -----------------------------
# Countdown
# -----------------------------
def _default_exam_dates(today: dt.date) -> Dict[str, dt.date]:
    defaults = {
        "MSÜ": dt.date(today.year, 3, 23),
        "LGS": dt.date(today.year, 6, 15),
        "YKS": dt.date(today.year, 6, 21),
    }
    for k, d in list(defaults.items()):
        if d < today:
            defaults[k] = dt.date(today.year + 1, d.month, d.day)
    return defaults


def _resolve_exam_dates(con: sqlite3.Connection, today: dt.date) -> Tuple[Dict[str, dt.date], Dict[str, str]]:
    dates: Dict[str, dt.date] = {}
    sources: Dict[str, str] = {}

    for exam in ["YKS", "MSÜ", "LGS"]:
        cached = _exam_cache_get(con, exam)
        if cached:
            iso, src = cached
            try:
                y, m, d = [int(x) for x in iso.split("-")]
                dd = dt.date(y, m, d)
                if dd < today:
                    dd = dt.date(today.year + 1, dd.month, dd.day)
                dates[exam] = dd
                sources[exam] = f"cache:{src}"
            except Exception:
                pass

    defaults = _default_exam_dates(today)
    for exam in ["YKS", "MSÜ", "LGS"]:
        if exam not in dates:
            dates[exam] = defaults[exam]
            sources[exam] = "fallback"

    try:
        for exam, dd in dates.items():
            _exam_cache_set(con, exam, dd.isoformat(), sources.get(exam, "fallback"))
    except Exception:
        pass

    return dates, sources


def _compute_countdown(dates: Dict[str, dt.date], today: dt.date) -> Dict[str, int]:
    return {k: max(0, (v - today).days) for k, v in dates.items()}


# -----------------------------
# Provider
# -----------------------------
class WebContentProvider(QThread):
    on_data_ready = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._force_refresh = False

    def force_refresh(self):
        self._force_refresh = True

    def run(self):
        con = _get_cache_conn()
        cache_key = "infoboard_payload_pro_v2"

        if not self._force_refresh:
            cached = _cache_get(con, cache_key)
            if cached:
                self.on_data_ready.emit(cached)

        today = dt.date.today()
        exam_dates, exam_sources = _resolve_exam_dates(con, today)
        countdown = _compute_countdown(exam_dates, today)

        items: List[FeedItem] = []
        online_ok = False

        try:
            items.extend(_fetch_osym_duyuru_titles(limit=12))
            online_ok = True
        except Exception:
            pass
        try:
            items.extend(_fetch_meb_duyuru_titles(limit=12))
            online_ok = True
        except Exception:
            pass
        try:
            items.extend(_fetch_meb_haberler_titles(limit=8))
            online_ok = True
        except Exception:
            pass

        # Dinamik Hedef Yıl Hesaplama
        target_year = today.year + 1 if today.month >= 9 else today.year
        
        rss_urls = [
            # 1. YKS Ana Haberleri (Son 15 gün)
            f"https://news.google.com/rss/search?q=YKS+{target_year}+TYT+AYT+when:15d&hl=tr&gl=TR&ceid=TR:tr",
            # 2. LGS (Son 15 gün)
            f"https://news.google.com/rss/search?q=LGS+{target_year}+liselere+giriş+when:15d&hl=tr&gl=TR&ceid=TR:tr",
            # 3. MSÜ (Son 30 gün)
            f"https://news.google.com/rss/search?q=MSÜ+{target_year}+milli+savunma+when:30d&hl=tr&gl=TR&ceid=TR:tr",
            # 4. Genel Eğitim/ÖSYM Duyuruları (Son 7 gün)
            f"https://news.google.com/rss/search?q=ÖSYM+MEB+duyuru+sınav+takvimi+when:7d&hl=tr&gl=TR&ceid=TR:tr",
            # 5. Yeni Maarif Modeli ve Müfredat (Son 30 gün)
            f"https://news.google.com/rss/search?q=yeni+maarif+modeli+müfredat+değişikliği+meb+when:30d&hl=tr&gl=TR&ceid=TR:tr",
            # 6. Sınav Analizleri ve Uzman Görüşleri (Son 30 gün)
            f"https://news.google.com/rss/search?q=YKS+LGS+sınav+analizi+uzman+değerlendirmesi+soru+dağılımı+when:30d&hl=tr&gl=TR&ceid=TR:tr",
            # 7. Rehberlik ve Strateji
            f"https://news.google.com/rss/search?q=sınav+kazanma+taktikleri+ders+çalışma+stratejileri+rehberlik+when:60d&hl=tr&gl=TR&ceid=TR:tr",
            # 8. Yeni Sınav Sistemi & Değişiklikler
            f"https://news.google.com/rss/search?q=yeni+sınav+sistemi+YKS+LGS+değişiklik+bakanlık+açıklaması+when:30d&hl=tr&gl=TR&ceid=TR:tr",
            # 9. Verimli Çalışma ve Öğrenci Koçluğu
            f"https://news.google.com/rss/search?q=verimli+ders+çalışma+teknikleri+öğrenci+koçluğu+eğitim+koçu+when:90d&hl=tr&gl=TR&ceid=TR:tr",
            # 10. Sınav Stresi ve Psikoloji
            f"https://news.google.com/rss/search?q=sınav+stresi+kaygısı+uzman+tavsiyesi+psikolog+öğrenci+psikolojisi+when:60d&hl=tr&gl=TR&ceid=TR:tr",
            # 11. MEB Örnek Soruları
            f"https://news.google.com/rss/search?q=MEB+örnek+sorular+yayınlandı+LGS+YKS+when:30d&hl=tr&gl=TR&ceid=TR:tr",
            # 12. Taban Puanlar ve Sıralamalar
            f"https://news.google.com/rss/search?q=üniversite+taban+puanları+başarı+sıralamaları+YKS+when:60d&hl=tr&gl=TR&ceid=TR:tr"
        ]

        for u in rss_urls:
            try:
                xmlb = _urlopen(u, timeout=4)
                items.extend(_parse_google_news_rss(xmlb, limit=6))
                online_ok = True
            except Exception:
                pass

        # Her durumda zengin çevrimdışı pedagojik bilgi bankasını da dahil et
        items.extend(OFFLINE_KNOWLEDGE_BASE)

        ranked = _rank_items(items)
        analysis_text, analysis_tag, top_items = _build_professional_analysis(ranked, countdown)

        if not online_ok:
            analysis_tag = "REHBERLİK"

        payload = {
            "countdown": countdown,
            "analysis": analysis_text,
            "analysis_tag": analysis_tag,
            "online": bool(online_ok),
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "items": [asdict(x) for x in ranked[:65]],
            "exam_date_sources": exam_sources,
        }

        try:
            _cache_set(con, cache_key, payload)
        except Exception:
            pass

        self._force_refresh = False
        self.on_data_ready.emit(payload)
