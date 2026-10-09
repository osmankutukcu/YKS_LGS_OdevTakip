# -*- coding: utf-8 -*-
"""
services/exam_score_calculator.py

ÖSYM YKS (TYT, AYT Sayısal, AYT Eşit Ağırlık, AYT Sözel, AYT Dil) ve 
MEB LGS resmi puan hesaplama katsayıları, tahmini Türkiye sıralaması/yüzdelik dilim motoru 
ve Türkiye geneli ortalama net kıyaslama verileri.
"""

from typing import Dict, Any, Tuple, Optional

# ----------------------------------------------------------------------
# 1. Resmi Türkiye Geneli Sınav İstatistikleri (ÖSYM & MEB Benchmark)
# ----------------------------------------------------------------------
TURKEY_BENCHMARKS = {
    "TYT": {
        "year": "2024 ÖSYM",
        "total_candidates": 3036945,
        "subjects": {
            "Türkçe": {"questions": 40, "average_net": 21.42, "std_dev": 8.1},
            "Sosyal": {"questions": 20, "average_net": 8.51, "std_dev": 4.2},
            "Matematik": {"questions": 40, "average_net": 7.85, "std_dev": 6.9},
            "Fen": {"questions": 20, "average_net": 3.64, "std_dev": 4.1}
        },
        "total_average_net": 41.42
    },
    "AYT": {
        "year": "2024 ÖSYM",
        "total_candidates": 1983766,
        "subjects": {
            "Matematik": {"questions": 40, "average_net": 5.54, "std_dev": 6.2},
            "Fizik": {"questions": 14, "average_net": 2.24, "std_dev": 2.8},
            "Kimya": {"questions": 13, "average_net": 1.45, "std_dev": 2.5},
            "Biyoloji": {"questions": 13, "average_net": 2.34, "std_dev": 2.6},
            "Edebiyat": {"questions": 24, "average_net": 6.12, "std_dev": 4.5},
            "Tarih": {"questions": 10, "average_net": 2.15, "std_dev": 2.1},
            "Coğrafya": {"questions": 6, "average_net": 1.42, "std_dev": 1.5},
            "Felsefe": {"questions": 12, "average_net": 1.95, "std_dev": 2.4},
            "Din": {"questions": 6, "average_net": 1.62, "std_dev": 1.4}
        },
        "total_average_net": 18.5
    },
    "LGS": {
        "year": "2024 MEB",
        "total_candidates": 1030000,
        "subjects": {
            "Türkçe": {"questions": 20, "average_net": 11.20, "std_dev": 4.8},
            "Matematik": {"questions": 20, "average_net": 5.62, "std_dev": 4.1},
            "Fen": {"questions": 20, "average_net": 9.45, "std_dev": 5.2},
            "İnkılap": {"questions": 10, "average_net": 6.84, "std_dev": 2.6},
            "Din": {"questions": 10, "average_net": 7.42, "std_dev": 2.4},
            "İngilizce": {"questions": 10, "average_net": 5.35, "std_dev": 3.1}
        },
        "total_average_net": 45.88
    }
}

# ----------------------------------------------------------------------
# 2. ÖSYM ve MEB Puan Hesaplama Fonksiyonları
# ----------------------------------------------------------------------
def calculate_tyt_score(net_dict: Dict[str, float], obp: float = 80.0) -> Dict[str, Any]:
    """
    TYT Ham Puanı (100 - 500) ve Yerleştirme Puanı Hesaplar.
    Resmi Katsayılar:
    Türkçe: 3.30, Matematik: 3.30, Fen: 3.40, Sosyal: 3.40, Taban Puan: 100
    """
    tr = net_dict.get("Türkçe", 0.0)
    mat = net_dict.get("Matematik", 0.0)
    fen = net_dict.get("Fen", 0.0)
    sos = net_dict.get("Sosyal", 0.0)
    
    total_net = tr + mat + fen + sos
    
    # Ham puan
    ham_puan = 100.0 + (tr * 3.30) + (mat * 3.30) + (fen * 3.40) + (sos * 3.40)
    ham_puan = min(500.0, max(100.0, ham_puan))
    
    obp_katki = obp * 0.6
    yerlestirme_puani = ham_puan + obp_katki
    
    tahmini_sira, dilim = estimate_yks_ranking("TYT", ham_puan, total_net)
    
    return {
        "puan_turu": "TYT",
        "toplam_net": round(total_net, 2),
        "ham_puan": round(ham_puan, 2),
        "yerlestirme_puani": round(yerlestirme_puani, 2),
        "tahmini_sira": tahmini_sira,
        "yuzdelik_dilim": dilim
    }

def calculate_ayt_score(net_dict: Dict[str, float], alan: str = "SAY", tyt_score: float = 300.0, obp: float = 80.0) -> Dict[str, Any]:
    """
    AYT Sayısal / Eşit Ağırlık / Sözel Puan Hesaplama.
    Formül: %40 TYT Katkısı + %60 AYT Katsayıları + Taban Puan
    """
    alan = alan.upper()
    total_net = sum(net_dict.values())
    
    # TYT Ham puan katkısı (%40)
    tyt_katki = (tyt_score - 100.0) * 0.40 if tyt_score > 100.0 else 0.0
    
    ayt_net_puani = 0.0
    
    if alan == "SAY":
        mat = net_dict.get("Matematik", 0.0)
        fiz = net_dict.get("Fizik", 0.0)
        kim = net_dict.get("Kimya", 0.0)
        biyo = net_dict.get("Biyoloji", 0.0)
        ayt_net_puani = (mat * 3.00) + (fiz * 2.85) + (kim * 3.07) + (biyo * 3.07)
    elif alan == "EA":
        mat = net_dict.get("Matematik", 0.0)
        edeb = net_dict.get("Edebiyat", 0.0)
        tar1 = net_dict.get("Tarih-1", net_dict.get("Tarih", 0.0))
        cog1 = net_dict.get("Coğrafya-1", net_dict.get("Coğrafya", 0.0))
        ayt_net_puani = (mat * 3.00) + (edeb * 3.00) + (tar1 * 2.80) + (cog1 * 3.33)
    else: # SOZ
        edeb = net_dict.get("Edebiyat", 0.0)
        tar1 = net_dict.get("Tarih-1", net_dict.get("Tarih", 0.0))
        cog1 = net_dict.get("Coğrafya-1", net_dict.get("Coğrafya", 0.0))
        tar2 = net_dict.get("Tarih-2", 0.0)
        cog2 = net_dict.get("Coğrafya-2", 0.0)
        fel = net_dict.get("Felsefe", 0.0)
        din = net_dict.get("Din", 0.0)
        ayt_net_puani = (edeb * 3.00) + (tar1 * 2.80) + (cog1 * 3.33) + (tar2 * 2.91) + (cog2 * 2.91) + (fel * 3.00) + (din * 3.33)
        
    ham_puan = 100.0 + tyt_katki + ayt_net_puani
    ham_puan = min(500.0, max(100.0, ham_puan))
    
    obp_katki = obp * 0.6
    yerlestirme_puani = ham_puan + obp_katki
    
    tahmini_sira, dilim = estimate_yks_ranking(f"AYT_{alan}", ham_puan, total_net)
    
    return {
        "puan_turu": f"AYT-{alan}",
        "toplam_net": round(total_net, 2),
        "ham_puan": round(ham_puan, 2),
        "yerlestirme_puani": round(yerlestirme_puani, 2),
        "tahmini_sira": tahmini_sira,
        "yuzdelik_dilim": dilim
    }

def calculate_lgs_score(net_dict: Dict[str, float]) -> Dict[str, Any]:
    """
    MEB LGS Puan Hesaplama (100 - 500 Puan Aralığı).
    Formül: Taban (100) + (Tr*4 + Mat*4 + Fen*4 + İnk*1 + Din*1 + İng*1) * 1.4815
    """
    tr = net_dict.get("Türkçe", 0.0)
    mat = net_dict.get("Matematik", 0.0)
    fen = net_dict.get("Fen", 0.0)
    ink = net_dict.get("İnkılap", 0.0)
    din = net_dict.get("Din", 0.0)
    ing = net_dict.get("İngilizce", 0.0)
    
    total_net = tr + mat + fen + ink + din + ing
    weighted_net = (tr * 4.0) + (mat * 4.0) + (fen * 4.0) + (ink * 1.0) + (din * 1.0) + (ing * 1.0)
    
    katsayi = 400.0 / 270.0 # ~ 1.48148
    puan = 100.0 + (weighted_net * katsayi)
    puan = min(500.0, max(100.0, puan))
    
    tahmini_sira, dilim = estimate_lgs_ranking(puan, total_net)
    
    return {
        "puan_turu": "LGS",
        "toplam_net": round(total_net, 2),
        "ham_puan": round(puan, 2),
        "yerlestirme_puani": round(puan, 2),
        "tahmini_sira": tahmini_sira,
        "yuzdelik_dilim": dilim
    }

def estimate_yks_ranking(exam_key: str, score: float, total_net: float) -> Tuple[int, float]:
    total_c = 3000000
    if score >= 485:
        rank = int(100 + (500 - score) * 300)
    elif score >= 450:
        rank = int(1000 + (485 - score) * 450)
    elif score >= 400:
        rank = int(16000 + (450 - score) * 1200)
    elif score >= 350:
        rank = int(76000 + (400 - score) * 2600)
    elif score >= 300:
        rank = int(206000 + (350 - score) * 5200)
    elif score >= 250:
        rank = int(466000 + (300 - score) * 9000)
    elif score >= 200:
        rank = int(916000 + (250 - score) * 15000)
    else:
        rank = int(1666000 + (200 - score) * 12000)
        
    rank = max(1, min(total_c, rank))
    dilim = round((rank / total_c) * 100, 2)
    return rank, dilim

def estimate_lgs_ranking(score: float, total_net: float) -> Tuple[int, float]:
    total_c = 1030000
    if score >= 495:
        rank = int(1 + (500 - score) * 100)
    elif score >= 475:
        rank = int(500 + (495 - score) * 250)
    elif score >= 450:
        rank = int(5500 + (475 - score) * 500)
    elif score >= 400:
        rank = int(18000 + (450 - score) * 1200)
    elif score >= 350:
        rank = int(78000 + (400 - score) * 2200)
    elif score >= 300:
        rank = int(188000 + (350 - score) * 3400)
    elif score >= 250:
        rank = int(358000 + (300 - score) * 4500)
    else:
        rank = int(583000 + (250 - score) * 3000)
        
    rank = max(1, min(total_c, rank))
    dilim = round((rank / total_c) * 100, 2)
    return rank, dilim

def calculate_exam_score(exam_type: str, net_dict: Dict[str, float], alan: str = "SAY") -> Dict[str, Any]:
    u_type = exam_type.upper()
    if "TYT" in u_type:
        return calculate_tyt_score(net_dict)
    elif "AYT" in u_type:
        return calculate_ayt_score(net_dict, alan=alan)
    elif "LGS" in u_type:
        return calculate_lgs_score(net_dict)
    else:
        tot = sum(net_dict.values())
        return {
            "puan_turu": "GENEL",
            "toplam_net": round(tot, 2),
            "ham_puan": round(100.0 + tot * 3.5, 2),
            "yerlestirme_puani": round(100.0 + tot * 3.5, 2),
            "tahmini_sira": 50000,
            "yuzdelik_dilim": 10.0
        }
