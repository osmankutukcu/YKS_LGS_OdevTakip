# -*- coding: utf-8 -*-
"""Raporlarda veri yok / küçük örneklem ayrımını yapan salt hesaplama yardımcıları.

Veritabanına erişmez ve görev durumlarını DEĞİŞTİRMEZ. Tamamlanma = ödev
kayıt oranıdır; sınav başarısı veya öğrencinin akademik yeterliği değildir.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

# Performans Paneli (services.performance_evidence_v14) ile aynı varsayılan eşik.
MIN_REPORT_SAMPLE = 5


@dataclass(frozen=True)
class CompletionEvidence:
    completed: int
    total: int
    percent: float | None
    status: str  # no_data | limited | sufficient

    @property
    def is_classifiable(self) -> bool:
        return self.status == "sufficient"


def completion_evidence(completed: int, total: int, minimum: int = MIN_REPORT_SAMPLE) -> CompletionEvidence:
    """Kaydı olmayan oran ile gerçek %0'ı karıştırmayın.

    Yüzde eski rapordaki formülle birebir aynıdır. Eşik yalnızca
    kullanıcıya sunulan çıkarımı sınırlamak için kullanılır.
    """
    total = max(0, int(total or 0))
    completed = min(total, max(0, int(completed or 0)))
    if total == 0:
        return CompletionEvidence(completed, 0, None, "no_data")
    percent = round(100.0 * completed / total, 1)
    return CompletionEvidence(completed, total, percent,
                              "sufficient" if total >= minimum else "limited")


def observed_rate_evidence(values: Iterable[float | None], minimum: int = MIN_REPORT_SAMPLE):
    """Günlük gözlemlerde NULL günler veri sayılmaz; tarihsel değişim tahmin edilmez."""
    clean = [float(x) for x in values if x is not None]
    if not clean:
        return None, 0, "no_data"
    mean = round(sum(clean) / len(clean), 1)
    return mean, len(clean), "sufficient" if len(clean) >= minimum else "limited"


def cohort_overview(rows: Iterable[Mapping], minimum: int = MIN_REPORT_SAMPLE):
    """Ödül/risk sayıları yalnızca yeterli görevi olan öğrencileri kapsar.

    Ortalama: görevi bulunan öğrencilerin öğrenci-bazlı aritmetik ortalaması;
    az örneklemliler ortalamaya dahildir ama ayrıca bildirilir.
    """
    rows = list(rows)
    full = [r for r in rows if int(r["gorev_toplam"]) >= minimum]
    measured = [r for r in rows if int(r["gorev_toplam"]) > 0]
    limited = [r for r in measured if int(r["gorev_toplam"]) < minimum]
    avg = (round(sum(float(r["basari_pct"]) for r in measured) / len(measured), 1)
           if measured else None)
    return {
        "total": len(rows),
        "measured": len(measured),
        "no_data": len(rows) - len(measured),
        "limited": len(limited),
        "classifiable": len(full),
        "avg": avg,
        "high": sum(1 for r in full if float(r["basari_pct"]) >= 80.0),
        "followup": sum(1 for r in full if float(r["basari_pct"]) < 50.0),
    }
