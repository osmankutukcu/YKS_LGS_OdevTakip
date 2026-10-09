import math
from datetime import date, timedelta

def analyze_performance_trend(stats: list[dict]) -> dict:
    """
    Son 7 günlük performans verilerini analiz eder ve 'human-like' bir içgörü döner.
    
    Args:
        stats: [{'day': 'Pzt', 'val': 50}, {'day': 'Sal', 'val': 60}, ...]
    
    Returns:
        {
            'status': 'increasing' | 'decreasing' | 'stable' | 'volatile' | 'nodata',
            'message': "Kullanıcıya gösterilecek akıllı mesaj",
            'icon': "📈" 
        }
    """
    if not stats:
        return {
            'status': 'nodata',
            'message': 'Henüz yeterli veri yok.',
            'icon': '⚪'
        }

    values = [d['val'] for d in stats]
    n = len(values)
    
    # 1. Ortalama ve Son Durum
    avg = sum(values) / n
    last_val = values[-1]
    
    # 2. Basit Eğim (Slope) Hesabı (Linear Regression: y = mx + c)
    # x = 0, 1, 2...
    # y = values
    sum_x = sum(range(n))
    sum_y = sum(values)
    sum_xy = sum(i * values[i] for i in range(n))
    sum_xx = sum(i * i for i in range(n))
    
    denominator = (n * sum_xx - sum_x * sum_x)
    
    slope = 0
    if denominator != 0:
        slope = (n * sum_xy - sum_x * sum_y) / denominator

    # 3. Volatilite (Standart Sapma)
    variance = sum((x - avg) ** 2 for x in values) / n
    std_dev = math.sqrt(variance)

    # --- KARAR MEKANİZMASI ---
    
    # Durum 1: Yüksek İstikrar
    if avg > 85 and std_dev < 15:
        return {
            'status': 'excellent',
            'message': f"Mükemmel istikrar! Son 7 gün ortalaması %{int(avg)}. Bu tempoyu korursak hedefleri büyütebiliriz.",
            'icon': '🏆'
        }

    # Durum 2: Belirgin Düşüş (Slope < -2)
    if slope < -2:
        return {
            'status': 'decreasing',
            'message': "Dikkat: Performans trendinde belirgin bir düşüş var. Motivasyon kaybı veya zor konulara geçiş olabilir.",
            'icon': '📉'
        }
    
    # Durum 3: Belirgin Artış (Slope > 2)
    elif slope > 2:
        return {
            'status': 'increasing',
            'message': "Harika! İvme yukarı yönlü. Son günlerdeki çalışma performansı gittikçe artıyor.",
            'icon': '🚀'
        }
    
    # Durum 4: Dengesiz (Yüksek Varyans)
    elif std_dev > 25:
        return {
            'status': 'volatile',
            'message': "Performans çok dalgalı. Bir gün çok iyi, bir gün düşük. Düzenli çalışma rutini oturtmalıyız.",
            'icon': '〰️'
        }
        
    # Durum 5: Düşük ama Stabil
    elif avg < 40:
        return {
            'status': 'low_stable',
            'message': f"Genel ortalama düşük (%{int(avg)}). Öğrencinin temel eksikleri veya zaman yönetimi sorunu olabilir.",
            'icon': '⚠️'
        }

    # Varsayılan
    return {
        'status': 'stable',
        'message': "Genel gidişat stabil. Rutin kontrolleri sürdürün.",
        'icon': '✅'
    }
