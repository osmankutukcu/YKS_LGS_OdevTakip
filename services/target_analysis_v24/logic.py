# -*- coding: utf-8 -*-
"""Hedef analizi için bağımsız, yan etkisiz doğrulama mantığı.

Bu modül kayıt, veritabanı veya Qt bağlantısı yapmaz. Eski davranışa varsayım
üreterek müdahale etmez. Deneme sonuçları ayrıştırılamıyorsa başarısız olur.
"""
from __future__ import annotations
import math
from typing import Iterable, Tuple


class TargetDataError(ValueError):
    pass


def validated_net(value, maximum: int, label: str, *, required: bool = True) -> float:
    raw = str('' if value is None else value).strip().replace(',', '.')
    if not raw:
        if required:
            raise TargetDataError(f'{label} boş bırakılamaz.')
        return 0.0
    try:
        amount = float(raw)
    except (TypeError, ValueError):
        raise TargetDataError(f'{label} sayısal bir değer olmalıdır.') from None
    # 4 yanlış 1 doğru götürebildiği için matematiksel olarak negatif net mümkündür.
    if not math.isfinite(amount) or amount < -maximum / 4 or amount > maximum:
        raise TargetDataError(f'{label} geçerli net aralığının dışında (-{maximum/4:g} … {maximum}).')
    return amount


def _paper_tags(label: str) -> list[str]:
    import re
    up = (label or '').strip().upper()
    return [key for key in ('TYT', 'AYT', 'YDT', 'LGS')
            if re.search(r'(?<![A-Z])' + key + r'(?![A-Z])', up)]


def _paper_from_label(label: str) -> str | None:
    tags = _paper_tags(label)
    return tags[0] if len(tags) == 1 else None


def extract_known_exam_nets(rows: Iterable[Tuple[str, float]], exam_name: str, exam_type: str) -> dict[str,float]:
    """Açıkça etiketlenmiş deneme türlerini ayırır; bilinmeyen dersleri ASLA %60/%40 bölmez.

    exam_type ör. YKS-SAY, YKS-DIL, LGS. exam_name denemenin d.tur alanıdır.
    Tekil TYT/AYT/LGS denemesi için sınavın tür etiketinden çıkarım güvenlidir.
    Genel 'YKS' belgesi altında 'Matematik' gibi bir ders ise güvenli değildir.
    """
    exam_type = (exam_type or '').upper()
    known = {"TYT": 0.0,"AYT": 0.0,"YDT": 0.0,"LGS": 0.0}
    counts = {k:0 for k in known}
    unknown = []
    # 'TYT-AYT' gibi bileşik denemede birini varsayarak toplam netleri yanlış bölme.
    tags = _paper_tags(exam_name)
    outer = tags[0] if len(tags) == 1 else None
    rows = list(rows)
    if not rows: raise TargetDataError('Bu denemede ders sonucu bulunamadı.')
    for name, raw_net in rows:
        local_tags = _paper_tags(name)
        # Çoklu ders etiketi varsa tekil sınav türüne YORUMLAMAYIN.
        label = None if len(local_tags) > 1 else (_paper_from_label(name) or outer)
        if label is None:
            unknown.append(str(name or 'etiketsiz ders'))
            continue
        if exam_type.startswith('YKS') and label == 'LGS':
            raise TargetDataError('Seçili YKS türü ile son LGS denemesi uyumsuz.')
        if exam_type == 'LGS' and label != 'LGS':
            raise TargetDataError('Seçili LGS türü ile son YKS denemesi uyumsuz.')
        if label not in known: continue
        try:
            net = float(raw_net)
        except (TypeError, ValueError):
            raise TargetDataError(f'{name} için net okunamadı.') from None
        if not math.isfinite(net):
            raise TargetDataError(f'{name} için net geçersiz.')
        known[label] += net
        counts[label] += 1
    if unknown:
        raise TargetDataError('Deneme derslerinin sınav türü belirsiz: ' + ', '.join(unknown[:4]) + '. TYT/AYT oranı tahmin edilmeyecek; netleri elle doğrulayın.')
    if exam_type == 'LGS':
        if not counts['LGS']: raise TargetDataError('LGS sonucu bulunamadı.')
        validated_net(known['LGS'],90,'LGS neti')
        return {'LGS': round(known['LGS'], 2)}
    if not (counts['TYT'] or counts['AYT'] or counts['YDT']):
        raise TargetDataError('TYT/AYT/YDT sonucu bulunamadı.')
    if exam_type == 'YKS-DIL' and counts['AYT']:
        raise TargetDataError('YKS-DİL için AYT neti YDT olarak varsayılamaz.')
    if exam_type != 'YKS-DIL' and counts['YDT']:
        raise TargetDataError('YDT neti seçili YKS puan türüne aktarılamaz.')
    if counts['TYT']: validated_net(known['TYT'],120,'TYT neti')
    if counts['AYT']: validated_net(known['AYT'],80,'AYT neti')
    if counts['YDT']: validated_net(known['YDT'],80,'YDT neti')
    return {k:round(known[k],2) for k in ('TYT','YDT' if exam_type == 'YKS-DIL' else 'AYT') if counts[k]}


def target_data_source_label(year: int) -> str:
    # Paket içi 2024/2025/2026 tabloları kaynak belgesi ve program kodu
    # bazında doğrulanmadı; resmî veri olduğunu İDDİA ETMEYİN.
    return f'{year} • Paket içi örnek/tahmin — resmî kaynakla doğrulanmadı'
