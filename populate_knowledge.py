# -*- coding: utf-8 -*-
"""
Curriculum Enricher (Coach Mode + Smart Insights)
- Mevcut yapıyı bozmadan curriculum.json içindeki topics alanını zenginleştirir.
- Eşleşmeyen konuları raporlar.
- Her konuya "koç gibi" pratik çalışma planları, checklist, tekrar takvimi ve akıllı yorumlar ekler.
"""

from __future__ import annotations

import argparse
import copy
import difflib
import json
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Tuple, Optional, List, Set

# -------------------------------
# Paths
# -------------------------------
JSON_PATH = "assets/curriculum.json"
EXAM_STATS_PATH = "assets/exam_stats.json"
UNMATCHED_OUT_PATH = "assets/unmatched_topics.json"
DB_PATH = "YKS_LGS_HomeworkManager_v2.db"

# -----------------------------
# DB TABLES CONTEXT
# -----------------------------
# Her tabloyu sınav/ders bağlamına etiketliyoruz.
TABLE_CONTEXT = {
    "tyt_matematik": ("TYT", "Matematik"),
    "ayt_matematik": ("AYT", "Matematik"),
    "problemler": ("TYT", "Matematik"),
    "geometri": ("TYT", "Geometri"),
    "fizik": ("TYT/AYT", "Fizik"),
    "kimya": ("TYT/AYT", "Kimya"),
    "biyoloji": ("TYT/AYT", "Biyoloji"),
    "turkce": ("TYT", "Türkçe"),
    "paragraf": ("TYT", "Türkçe"),
    "tarih": ("TYT", "Tarih"),
    "cografya": ("TYT", "Coğrafya"),
    "felsefe": ("TYT", "Felsefe"),
    "edebiyat": ("AYT", "Edebiyat"),
    "lgs_matematik": ("LGS", "Matematik"),
    "lgs_fen": ("LGS", "Fen"),
    "lgs_turkce": ("LGS", "Türkçe"),
    "lgs_inkilap": ("LGS", "İnkılap"),
    "lgs_ingilizce": ("LGS", "İngilizce"),
    "lgs_din": ("LGS", "Din"),
    "lgs_dinkulturu": ("LGS", "Din"),
}

# -------------------------------
# SUBJECT TEMPLATES (Smart Tips)
# -------------------------------
SUBJECT_COACH_TEMPLATES = {
    "Matematik": {
        "default_tip": "İşlem hatasını azaltmak için: her sorudan sonra 5 sn 'kontrol molası' ver.",
        "study_style": ["Kısa konu özeti", "Örnek çözüm", "Süreli test", "Hata defteri"],
        "review": "1-3-7 kuralı: bugün → 3 gün sonra → 7 gün sonra mini tekrar."
    },
    "Geometri": {
        "default_tip": "Çizim = yarı çözüm. Her soruda en az 2 yardımcı çizgi dene.",
        "study_style": ["Şekil analizi", "Teorem kartı", "Kısa süreli mini test", "Yanlışın şekline not düş"],
        "review": "Şekil hafızası için: her gün 10 dk 'şekil kütüphanesi' tekrar."
    },
    "Fizik": {
        "default_tip": "Formül ezberi değil: önce 'hangi büyüklük değişiyor?' diye sor.",
        "study_style": ["Kavram", "Serbest cisim diyagramı", "Birim analizi", "Çıkmış soru"],
        "review": "Yanlışları 'neden yanlış' diye sınıflandır: kavram mı, işlem mi, yorum mu?"
    },
    "Kimya": {
        "default_tip": "Birim/denge/yorum: 3'lü kontrol. Özellikle Kc-Kp ve pH sorularında şart.",
        "study_style": ["Konu haritası", "Tanım kartları", "Soru tipleri", "Karışık tekrar testleri"],
        "review": "Tepkime-şart-yorum: her yanlışta bu 3 başlığa işaret koy."
    },
    "Biyoloji": {
        "default_tip": "Biyoloji = doğru cümle kurma. Kısa not + çok tekrar.",
        "study_style": ["Kavram fişi", "Tablo", "Şema", "Kısa test"],
        "review": "48 saat içinde tekrar yapılmazsa unutma çok hızlanır."
    },
    "Türkçe": {
        "default_tip": "Paragrafta hız: önce soru kökü → sonra metin. Şıkları en sona bırak.",
        "study_style": ["Günlük süreli paragraf", "Yanlış analiz", "Dil bilgisi mini tekrar"],
        "review": "Her gün 1 mini deneme: 15 paragraf (20 dk)."
    },
    "Tarih": {
        "default_tip": "Tarih = sebep-sonuç zinciri. Ezber değil bağlantı kur.",
        "study_style": ["Kronoloji", "Kavram fişi", "Çıkmış soru", "Kısa tekrar"],
        "review": "Haftalık tekrar: 1 sayfalık özet + 20 soru."
    },
    "Coğrafya": {
        "default_tip": "Harita + yorum. Her konuyu bir harita/şema ile eşleştir.",
        "study_style": ["Harita okuma", "Şema", "Soru tipi", "Tekrar"],
        "review": "Görsel tekrar: 10 dk harita + 10 soru."
    },
    "Felsefe": {
        "default_tip": "Felsefe = kavram/akım/filozof eşleştirme. 3’lü kart sistemi kur.",
        "study_style": ["Kavram kartı", "Mini test", "Eşleştirme soruları"],
        "review": "Haftada 2 gün 20 dk kart + 20 soru."
    },
    "Edebiyat": {
        "default_tip": "Edebiyat = dönem-özellik-yazar-eser. Tablo şart.",
        "study_style": ["Dönem tabloları", "Eser-yazar kartı", "Çıkmış soru"],
        "review": "Dönem tekrarını 3 günde bir döndür."
    },
    "Fen": { 
        "default_tip": "LGS fen: okuduğunu yorumlama + grafik. Soru kökü çok belirleyici.",
        "study_style": ["Kavram", "Deney-yorum", "Grafik", "Süreli test"],
        "review": "Kısa ama sık: günde 20 dk fen."
    },
    "İnkılap": {
        "default_tip": "LGS inkılap: olay-akış-harf devrimleri gibi başlıklarda kronoloji kur.",
        "study_style": ["Zaman çizgisi", "Kavram", "Test"],
        "review": "Her hafta 1 genel tekrar testi."
    },
    "İngilizce": {
        "default_tip": "LGS ingilizce: kelime + bağlam. Her gün 10 kelime 5 cümle.",
        "study_style": ["Kelime", "Kısa okuma", "Test"],
        "review": "SRS kelime tekrarı kullan."
    },
    "Din": {
        "default_tip": "LGS din: kavramları günlük örnekle bağla; metin soruları çok çıkar.",
        "study_style": ["Kavram", "Metin-yorum", "Test"],
        "review": "Haftalık 1 tekrar testi."
    },
}

# -------------------------------
# KNOWLEDGE BASE
# Format: (importance, questions, tip, prerequisites, common_mistakes, mini_formulas, estimated_minutes)
# -------------------------------
KNOWLEDGE: Dict[str, Tuple[Any, ...]] = {
    # --- MATEMATİK ---
    "Asal Çarpanlara Ayırma": (
        "Yüksek (4/5)", "1 Soru", "EBOB-EKOK temeli. Bölme algoritmasını öğrenin.",
        ["Bölünebilme"],
        ["1'i asal sanmak", "Üslü gösterimi yanlış yazmak"],
        ["n = p1^a * p2^b"], 35
    ),
    "OBEB-OKEK": ("Orta (3/5)", "0-1 Soru", "Periyodik problemler ve nöbet soruları.", ["Asal Çarpanlara Ayırma"], ["OBEB/OKEK karıştırmak"], ["OKEK:üs=max"], 40),
    "Ondalık Sayılar": ("Orta (3/5)", "1 Soru", "Virgül kaydırma ve devirli sayılar.", [], [], [], 25),
    "Faktöriyel": ("Orta (3/5)", "0-1 Soru", "Sadeleşmeye dikkat.", [], [], [], 20),
    "Doğal Sayılar": ("Temel (2/5)", "0-1 Soru", "Basamak kavramı önemli.", [], [], [], 15),
    "Tam Sayılar": ("Temel (2/5)", "1 Soru", "İşaret incelemesi.", [], [], [], 15),
    "Tek-Çift Sayılar": ("Yüksek (4/5)", "1 Soru", "Değer verme, mantığı kavra (parity).", ["Tam Sayılar"], ["Tek+tek=çift hatası"], ["tek*tek=tek"], 30),
    "Ardışık Sayılar": ("Orta (3/5)", "1 Soru", "Terim sayısı formülü şart.", [], [], ["Son-İlk/Artış+1"], 30),
    "Mutlak Değer": ("Yüksek (4/5)", "1 Soru", "Uzaklık kavramı olarak düşünün.", [], [], ["|x|=a -> x=a v x=-a"], 35),
    "Üslü Sayılar": ("Yüksek (4/5)", "1-2 Soru", "Taban ve üs özelliklerini karıştırmayın.", [], [], ["a^n * a^m = a^(n+m)"], 40),
    "Köklü Sayılar": ("Yüksek (4/5)", "1-2 Soru", "Eşlenik alma ve kök dışına çıkarma.", [], [], [], 40),
    "Çarpanlara Ayırma": ("Yüksek (4/5)", "1 Soru", "Özdeşlikleri (iki kare farkı, küp) ezberleyin.", [], [], ["a^2-b^2=(a-b)(a+b)"], 45),
    "Oran-Orantı": ("Yüksek (4/5)", "1 Soru", "Problemlerin temel taşıdır. k sabiti kullanın.", [], [], ["a/b=k"], 35),
    "Problemler": ("KRİTİK (5/5)", "10-12 Soru", "Sayı, Kesir, Yaş, Hareket, Yüzde. Her gün çözülmeli.", [], ["Denklem kuramama"], [], 70),
    "Kümeler": ("Orta (3/5)", "1 Soru", "Venn şeması çizin, formüle boğulmayın.", [], [], [], 30),
    "Fonksiyonlar": ("KRİTİK (5/5)", "2 Soru", "Tanım kümesi ve grafik yorumlama çok önemli.", [], ["Bileşke sırası hatası"], ["(fog)(x)=f(g(x))"], 60),
    "Polinomlar": ("Yüksek (4/5)", "1 Soru", "Kalan bulma ve P(x) oluşturma.", [], [], ["P(x)=(x-a)Q(x)+K"], 45),
    "2. Dereceden Denklemler": ("Yüksek (4/5)", "1 Soru", "Delta ve kök-katsayı bağıntıları.", [], [], ["x1+x2=-b/a"], 40),
    "Karmaşık Sayılar": ("Orta (3/5)", "1 Soru", "i^n kuvvetleri ve eşlenik.", [], [], ["i^2=-1"], 30),
    "Parabol": ("Yüksek (4/5)", "1 Soru", "Tepe noktası ve grafik çizimi.", [], [], ["r=-b/2a"], 45),

    # --- GEOMETRİ ---
    "Doğruda Açı": ("Temel (2/5)", "0-1 Soru", "Z, U, M kuralları (Muz).", [], ["Paralelliği görmemek"], ["a+b=x"], 20),
    "Üçgende Açı": ("Yüksek (4/5)", "1 Soru", "İkizkenar/Eşkenar gizlenir, dikkat.", [], ["Dış açıyı yanlış hesaplamak"], ["İç açılar top = 180"], 30),
    "Üçgende Benzerlik": ("KRİTİK (5/5)", "1-2 Soru", "Benzerlik = oran. Geometrinin kalbi.", ["Üçgende Açı"], ["Oranı ters yazmak"], ["k -> k^2 (Alan)"], 60),
    "Dik Üçgen": ("Çok Yüksek (5/5)", "2-3 Soru", "Pisagor+Öklid her yerde.", [], ["Hipotenüs hatası"], ["a^2+b^2=c^2"], 45),
    "Çokgenler": ("Yüksek (4/5)", "1 Soru", "Düzgün altıgen (6 eşkenar üçgen).", [], [], [], 35),
    "Dörtgenler": ("Orta (3/5)", "0-1 Soru", "Köşegen özellikleri.", [], [], [], 30),
    "Yamuk": ("Yüksek (4/5)", "1 Soru", "Paralelkenara tamamlama veya dik indirme.", [], [], [], 40),
    "Paralelkenar": ("Yüksek (4/5)", "1 Soru", "Alan taşıma kuralı.", [], [], [], 35),
    "Eşkenar Dörtgen": ("Orta (3/5)", "1 Soru", "Köşegenler dik kesişir.", [], [], [], 30),
    "Dikdörtgen": ("Yüksek (4/5)", "1 Soru", "Köşegenler eşittir.", [], [], [], 30),
    "Kare": ("Yüksek (4/5)", "1 Soru", "45-45-90 üçgeni oluşur.", [], [], [], 30),
    "Çemberde Açı": ("Yüksek (4/5)", "1 Soru", "Çevre açı ve merkez açı ilişkisi.", [], [], [], 40),
    "Çemberde Uzunluk": ("Yüksek (4/5)", "1 Soru", "Yarıçap çizmek hayat kurtarır.", [], [], [], 45),
    "Dairede Alan": ("Yüksek (4/5)", "1-2 Soru", "Dilim alanı formülü.", [], [], ["pi*r^2"], 35),
    "Katı Cisimler": ("KRİTİK (5/5)", "2 Soru", "Prizma, Silindir, Küp. Hacim/Alan.", [], ["Yanal alan hatası"], ["V=Taban*h"], 55),
    "Analitik Geometri": ("KRİTİK (5/5)", "2 Soru", "Eğim, İki nokta arası uzaklık.", [], ["y2-y1/x2-x1 sırası"], ["y-y1=m(x-x1)"], 60),
    "Dönüşüm Geometrisi": ("Orta (3/5)", "0-1 Soru", "Öteleme, Dönme, Simetri.", [], [], [], 25),

    # --- FİZİK ---
    "Newton Hareket Yasaları": ("KRİTİK (5/5)", "1-2 Soru", "F=ma. Serbest cisim diyagramı çiz.", ["Vektörler"], ["Sürtünme yönü"], ["Fnet=m*a"], 50),
    "Atışlar": ("Yüksek (4/5)", "1 Soru", "5-15-25 kuralı (pratik).", [], [], ["h=1/2gt^2"], 40),
    "İş, Güç, Enerji": ("KRİTİK (5/5)", "1 Soru", "Enerji korunumu.", [], [], ["E_ilk=E_son"], 45),
    "Elektrik Akımı": ("Yüksek (4/5)", "1 Soru", "V=I*R, Seri-Paralel bağlama.", [], [], ["V=IR"], 40),
    "Manyetizma": ("KRİTİK (5/5)", "1-2 Soru", "Sağ el kuralı.", [], ["Yön kuralı hatası"], ["F=Bil"], 50),
    "Optik": ("KRİTİK (5/5)", "2 Soru", "Yansıma, Kırılma, Aynalar.", [], [], ["n1sin1=n2sin2"], 60),
    
    # --- KİMYA ---
    "Atom ve Periyodik Sistem": ("Yüksek (4/5)", "1 Soru", "Periyodik özellik değişimi.", [], [], [], 35),
    "Kimyasal Türler Arası Etkileşimler": ("KRİTİK (5/5)", "1 Soru", "İyonik, Kovalent, Metalik.", [], [], [], 40),
    "Gazlar": ("KRİTİK (5/5)", "1 Soru", "İdeal gaz yasası.", ["Mol"], ["Birim hatası"], ["PV=nRT"], 50),
    "Sıvı Çözeltiler": ("Yüksek (4/5)", "1-2 Soru", "Molarite, koligatif özellik.", [], [], ["M=n/V"], 45),
    "Asit-Baz Dengesi": ("KRİTİK (5/5)", "2 Soru", "pH, Titrasyon.", [], [], ["pH=-log[H+]"], 55),
    "Organik Kimya": ("KRİTİK (5/5)", "3-4 Soru", "Alkan, Alken, Fonksiyonel grup.", [], [], [], 80),

    # --- BİYOLOJİ ---
    "Hücre": ("KRİTİK (5/5)", "1 Soru", "Organeller, Madde geçişi.", [], [], [], 40),
    "Kalıtım": ("Yüksek (4/5)", "1 Soru", "Mendel, Soy ağacı.", [], [], [], 35),
    "Sistemler": ("KRİTİK (5/5)", "3-4 Soru", "Sindirim, dolaşım, sinir...", [], [], [], 90),
    "Bitki Biyolojisi": ("KRİTİK (5/5)", "2 Soru", "Dokular, Fotosentez.", [], [], [], 50),
}


# -------------------------------
# Data structures
# -------------------------------
@dataclass(frozen=True)
class MatchResult:
    found: bool
    kb_key: Optional[str] = None
    reason: str = ""   # exact / normalized / substring / fuzzy / none
    score: float = 0.0 # fuzzy similarity

@dataclass
class EnrichmentOptions:
    force: bool = False
    dry_run: bool = False
    backup: bool = True
    fuzzy_cutoff: float = 0.86
    min_substring_len: int = 5
    keep_user_fields: bool = True

# -------------------------------
# Utilities
# -------------------------------
def _normalize(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^\w\sçğıöşü]", " ", s, flags=re.UNICODE)
    tr_map = str.maketrans({"ç": "c", "ğ": "g", "ı": "i", "ö": "o", "ş": "s", "ü": "u"})
    return s.translate(tr_map)

def _safe_write_json(path: str, data: Dict[str, Any], make_backup: bool = True) -> None:
    folder = os.path.dirname(path) or "."
    os.makedirs(folder, exist_ok=True)
    if make_backup and os.path.exists(path):
        shutil.copy2(path, path + ".bak")
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    os.replace(tmp_path, path)

def _load_json_or_empty(path: str) -> Dict[str, Any]:
    if not os.path.exists(path): return {}
    try:
        with open(path, "r", encoding="utf-8") as f: return json.load(f)
    except: return {}

# -------------------------------
# Logic
# -------------------------------

def _build_kb_indexes(kb: Dict[str, Tuple[Any, ...]]) -> Tuple[Dict[str, str], Dict[str, str]]:
    exact_map, norm_map = {}, {}
    for k in kb.keys():
        exact_map[k] = k
        nk = _normalize(k)
        if nk not in norm_map: norm_map[nk] = k
    return exact_map, norm_map

def _match_topic(topic_name: str, kb, exact_map, norm_map, fuzzy_cutoff, min_substring_len) -> MatchResult:
    key = (topic_name or "").strip()
    if not key: return MatchResult(False, None, "none", 0.0)
    if key in exact_map: return MatchResult(True, exact_map[key], "exact", 1.0)
    
    nk = _normalize(key)
    if nk in norm_map: return MatchResult(True, norm_map[nk], "normalized", 1.0)

    for k in kb.keys():
        if len(k) >= min_substring_len and (k in key or key in k):
            return MatchResult(True, k, "substring", 0.95)

    kb_norm_keys = list(norm_map.keys())
    close = difflib.get_close_matches(nk, kb_norm_keys, n=1, cutoff=fuzzy_cutoff)
    if close:
        best = close[0]
        score = difflib.SequenceMatcher(None, nk, best).ratio()
        return MatchResult(True, norm_map[best], "fuzzy", score)

    return MatchResult(False, None, "none", 0.0)

def _extract_kb_fields(kb_data: Tuple[Any, ...]) -> Dict[str, Any]:
    out = {}
    out["importance"] = kb_data[0] if len(kb_data) > 0 else "Orta (3/5)"
    out["questions"] = kb_data[1] if len(kb_data) > 1 else ""
    out["tip"] = kb_data[2] if len(kb_data) > 2 else ""
    out["prerequisites"] = kb_data[3] if len(kb_data) > 3 else []
    out["common_mistakes"] = kb_data[4] if len(kb_data) > 4 else []
    out["mini_formulas"] = kb_data[5] if len(kb_data) > 5 else []
    out["estimated_minutes"] = kb_data[6] if len(kb_data) > 6 else None
    return out

# --- RULE BASED ENRICHMENT WITH CONTEXT ---

def _rule_based_pack(topic_name: str, subject: str) -> Dict[str, List[str]]:
    t = _normalize(topic_name)
    mistakes, formulas, quick_checks, coach_tips = [], [], [], []

    # Subject specific rules
    if subject == "Matematik" or "matematik" in t:
        if "mutlak" in t:
            quick_checks += ["|x-a| ifadesini 'uzaklık' olarak okuyabiliyor musun?"]
            coach_tips += ["Mutlak değer = uzaklık. Önce sayı doğrusunda düşün."]
        if "uslu" in t:
            formulas += ["a^m * a^n = a^(m+n)"]
            coach_tips += ["İşlem yapmadan önce 'taban aynı mı?' kontrolü yap."]
        if "problemler" in t:
             mistakes += ["Soru kökünü okumadan işleme başlamak"]
             coach_tips += ["Problemler: Her gün 10 soru = 1 konu kadar etkili."]

    if subject == "Geometri" or "geometri" in t:
         if "dik ucgen" in t or "pisagor" in t:
             formulas += ["a^2 + b^2 = c^2"]
             coach_tips += ["Pisagor'u yazmadan önce 1 saniye: 'c hipotenüs mü?' diye sor."]
             
    if subject == "Fizik" or "fizik" in t:
         if "newton" in t:
             formulas += ["F=ma"]
             coach_tips += ["Newton: %70 başarı = doğru diyagram (FBD). Önce çiz."]

    if subject == "Kimya" or "kimya" in t:
         if "gaz" in t:
             formulas += ["PV=nRT"]
             coach_tips += ["Gazlar: Sıcaklığı Kelvin'e çevirdin mi? Kontrol et."]

    return {"common_mistakes": mistakes, "mini_formulas": formulas, 
            "quick_checks": quick_checks, "coach_tips": coach_tips}

def _study_variants(topic: str, imp_score: int, q_score: float, subject: str) -> List[Dict[str, Any]]:
    base = 25 + imp_score * 8 + int(q_score * 5)
    
    # Subject Specific Variant Tweaks
    steps_speed = ["Özet Oku", "20 Soru Çöz"]
    if subject == "Türkçe": steps_speed = ["15 Paragraf Oku", "Yanlışları Analiz Et"]
    if subject == "Geometri": steps_speed = ["5 Formül Tekrarı", "10 Soru Çöz"]

    variants = []
    variants.append({"name": "Hız Modu", "minutes": max(20, base-10), "goal": "Pratik", "steps": steps_speed})
    variants.append({"name": "Derinlemesine", "minutes": base+30, "goal": "Kavrama", 
                     "steps": ["Video İzle", "Not Çıkar", "40 Soru Çöz"]})
    
    if imp_score >= 4:
        variants.append({"name": "Kamp Modu", "minutes": base+60, "goal": "Eksiksiz", 
                         "steps": ["Detaylı Analiz", "Çıkmış Sorular (Son 5 Yıl)", "60 Soru"]})
    
    return variants

def _coach_checklist(topic: str, imp_score: int, subject: str) -> List[str]:
    base = ["Konu özeti çıkarıldı mı?", "Yanlışların sebebi not alındı mı?"]
    if imp_score >= 4: 
        base.insert(0, f"Bu konu ({topic}) sınavda belirleyicidir, eksik bırakma.")
    
    if subject == "Fizik": base.append("Formül kartı hazırlandı mı?")
    if subject == "Biyoloji": base.append("Kavram haritası çizildi mi?")
    if subject == "Geometri": base.append("Temel teoremler ezberlendi mi?")
    
    return base

def _spaced_repetition_plan() -> List[Dict[str, Any]]:
    return [
        {"day_offset": 1, "task": "10 soru + not tekrarı"},
        {"day_offset": 3, "task": "20 soru karma test"},
        {"day_offset": 7, "task": "1 deneme sorusu veya zor soru"},
        {"day_offset": 14, "task": "Hızlı gözden geçirme (10 dk)"}
    ]

def _identify_subject(topic_name: str, topic_info: dict) -> str:
    # Try to identify subject from tags first
    tags = topic_info.get("tags", [])
    for t in tags:
        for subj in SUBJECT_COACH_TEMPLATES.keys():
            if subj in t: return subj
    
    # Fallback to name heuristic
    tn = topic_name.lower()
    if "matematik" in tn or "fonksiyon" in tn or "polinom" in tn: return "Matematik"
    if "fizik" in tn or "hareket" in tn or "kuvvet" in tn: return "Fizik"
    if "kimya" in tn or "atom" in tn: return "Kimya"
    if "biyoloji" in tn or "hücre" in tn: return "Biyoloji"
    if "paragraf" in tn or "dil bilgisi" in tn: return "Türkçe"
    
    return "Genel"

def populate(json_path=JSON_PATH, opts=None):
    if opts is None: opts = EnrichmentOptions()
    if not os.path.exists(json_path): return

    data = _load_json_or_empty(json_path)
    topics = data.get("topics", {})
    exact_map, norm_map = _build_kb_indexes(KNOWLEDGE)
    
    updated = 0
    for topic_name, info in topics.items():
        if not isinstance(info, dict): continue
        
        # 1. Subject Identification
        subject = _identify_subject(topic_name, info)
        
        # 2. KB Matching
        m = _match_topic(topic_name, KNOWLEDGE, exact_map, norm_map, opts.fuzzy_cutoff, opts.min_substring_len)
        kb_fields = _extract_kb_fields(KNOWLEDGE[m.kb_key]) if m.found and m.kb_key else None
        
        # 3. Apply KB Fields
        if kb_fields:
            if opts.force or "importance" not in info: info["importance"] = kb_fields["importance"]
            if opts.force or "questions" not in info: info["questions"] = kb_fields["questions"]
            if opts.force or "tip" not in info: info["tip"] = kb_fields["tip"]
            if kb_fields["prerequisites"]: info["prerequisites"] = kb_fields["prerequisites"]
            if kb_fields["estimated_minutes"]: info["estimated_minutes"] = kb_fields["estimated_minutes"]
        
        # 4. Apply Rule-Based Fields (Mistakes, Formulas, Checklists)
        rule = _rule_based_pack(topic_name, subject)
        
        # Merge lists uniquely
        info["common_mistakes"] = list(set(info.get("common_mistakes", []) + rule["common_mistakes"] + (kb_fields["common_mistakes"] if kb_fields else [])))
        info["mini_formulas"] = list(set(info.get("mini_formulas", []) + rule["mini_formulas"] + (kb_fields["mini_formulas"] if kb_fields else [])))
        info["coach_tips"] = list(set(info.get("coach_tips", []) + rule["coach_tips"]))
        
        # 5. Smart Fields
        imp_score = 3
        if "importance" in info:
            if "KRİTİK" in info["importance"]: imp_score=5
            elif "Yüksek" in info["importance"]: imp_score=4
        
        q_score = 1.0 # default logic simplified
        
        info["study_variants"] = _study_variants(topic_name, imp_score, q_score, subject)
        info["coach_checklist"] = _coach_checklist(topic_name, imp_score, subject)
        info["spaced_repetition"] = _spaced_repetition_plan()
        
        # 6. Apply Subject Template Tip if no tip exists
        if "tip" not in info or not info["tip"]:
            tpl = SUBJECT_COACH_TEMPLATES.get(subject)
            if tpl:
                info["tip"] = f"Koç Tavsiyesi: {tpl.get('default_tip')}"

        updated += 1

    data["topics"] = topics
    if not opts.dry_run:
        _safe_write_json(json_path, data, opts.backup)
        
    print(f"Smart Enriched {updated} topics.")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", default=JSON_PATH)
    parser.add_argument("--dry-run", action="store_true")
    # ... other args ...
    args, unknown = parser.parse_known_args() # simplified for tool
    
    opts = EnrichmentOptions(dry_run=args.dry_run)
    populate(args.json, opts)

if __name__ == "__main__":
    main()
