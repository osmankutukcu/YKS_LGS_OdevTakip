import sqlite3
import collections
import re
from typing import Optional, Dict, List, Any

def analyze_weakness_nlp(con: sqlite3.Connection, student_id: int) -> Optional[Dict[str, Any]]:
    """
    Öğrencinin başarısız veya eksik kaldığı ödevlerin metinlerini analiz eder.
    Basit bir NLP (Token Frequency + Context) yaklaşımıyla zayıf noktaları tespit eder.
    
    Returns:
        {
            "report_text": str,
            "target_subject": str,
            "keywords": List[str]
        }
    """
    cursor = con.cursor()
    
    # 1. Başarısız veya Sürekli Ertelenen Ödevleri Çek
    # Durum analizi (Case insensitive)
    # Bitmiş ödevler haricindekileri veya gecikmişleri al
    sql = """
        SELECT ders, kitap, konu, durum 
        FROM odev 
        WHERE ogrenci_id = ? 
        AND (durum IS NULL OR lower(durum) NOT IN ('yapildi', 'tamam', 'tamamlandı', 'tamamlandi'))
        AND kume_id IN (
            SELECT id FROM odev_kume WHERE bitis_tarihi < date('now')
        )
    """
    try:
        rows = cursor.execute(sql, (student_id,)).fetchall()
    except Exception:
        return None
    
    if not rows:
        return None

    # 2. Tokenizasyon ve Frekans Analizi
    subject_fails = collections.defaultdict(int)
    topic_tokens = collections.defaultdict(int)
    
    # Stop words (Türkçe eğitim bağlamında etkisiz kelimeler)
    STOP_WORDS = {
        "ve", "ile", "için", "bir", "bu", "şu", 
        "test", "soru", "çözümü", "konu", "anlatımı", 
        "bölüm", "part", "kitap", "deneme", "etüt", "tekrar",
        "ödev", "sayfa", "testi", "soruları", "yaprak"
    }
    
    total_fails = 0
    for r in rows:
        ders = (r['ders'] or "").strip()
        konu = (r['konu'] or "").strip()
        
        if not ders: continue
        
        subject_fails[ders] += 1
        total_fails += 1
        
        # Konu metnini temizle (sadece harfler)
        # Regex: harf dışı karakterleri boşluk yap
        clean_text = re.sub(r'[^\w\s]', ' ', konu.lower())
        tokens = clean_text.split()
        
        for t in tokens:
            if len(t) > 2 and t not in STOP_WORDS and not t.isdigit():
                topic_tokens[t] += 1
                
    if total_fails < 3:
        return None # Yeterli veri yok

    # 3. İçgörü Üretimi (Natural Language Generation)
    
    # En çok zorlanılan ders (Dominant Subject)
    top_subject = max(subject_fails, key=subject_fails.get)
    subject_fail_count = subject_fails[top_subject]
    
    # Eğer bu ders toplam hataların %40'ından fazlasını oluşturuyorsa o derse odaklanalım
    is_subject_dominant = (subject_fail_count / total_fails) > 0.4
    
    # En çok tekrar eden konu kelimeleri
    # Sadece o derse ait keywordleri filtrelemek daha doğru olurdu ama 
    # basitlik adına global bakıyoruz, zaten dominant ders domine edecektir.
    common_topics = sorted(topic_tokens.items(), key=lambda x: x[1], reverse=True)[:4]
    
    # RAPOR OLUŞTURMA
    report = "### 🧠 Yapay Zeka Eksik Analizi\n\n"
    
    if is_subject_dominant:
        report += f"**Tespit:** Öğrencinin özellikle **{top_subject}** dersinde yoğunlaştığı ({subject_fail_count} eksik ödev) görülmektedir.\n\n"
    else:
        report += f"**Tespit:** Eksikler birden fazla derse yayılmış durumda, ancak **{top_subject}** öne çıkıyor.\n\n"
    
    recommendations = []
    if common_topics:
        keywords = [t[0] for t in common_topics]
        keywords_str = ", ".join([k.capitalize() for k in keywords])
        report += f"**Kavramsal Analiz:** Yapılan NLP taramasında, eksik bırakılan görevlerde şu terimler sıkça geçmektedir:\n"
        report += f"> *{keywords_str}*\n\n"
        report += "**Öneri:** Bu kavramları içeren pekiştirme testlerinden oluşan bir set hazırlanması önerilir."
        recommendations = keywords
    else:
        report += "**Analiz:** Spesifik bir konu örüntüsü bulunamadı. Genel tekrar önerilir."
        
    return {
        "report_text": report,
        "target_subject": top_subject,
        "keywords": recommendations
    }
