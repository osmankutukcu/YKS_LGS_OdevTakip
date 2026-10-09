
from datetime import date, timedelta
GUNLER = ['Pazartesi','Salı','Çarşamba','Perşembe','Cuma','Cumartesi','Pazar']

def haftalik_plan(odevler, baslangic_gunu=None, tur_sayisi=3):
    """odevler: [{'ders','kitap','konu','sure'}] listesi
    baslangic_gunu: 0=Pt .. 6=Pazar; None ise bugünün haftalık indexine göre
    """
    if baslangic_gunu is None:
        baslangic_gunu = (date.today().weekday())  # 0=Pt
    plan = {g: {f'Tur {t}': [] for t in range(1, tur_sayisi+1)} for g in range(7)}
    # dağıtım: sırayla günlere ve turlara
    g = baslangic_gunu; t = 1
    for o in odevler:
        plan[g][f'Tur {t}'].append(o)
        g = (g + 1) % 7
        if g == baslangic_gunu:
            t = t + 1 if t < tur_sayisi else 1
    return plan

def plan_metni(plan):
    lines = []
    for g in range(7):
        lines.append(f"=== {GUNLER[g]} ===")
        for tur, lst in plan[g].items():
            if not lst: continue
            lines.append(f"{tur}:")
            for o in lst:
                lines.append(f"- {o.get('ders')}/{o.get('kitap')} – {o.get('konu')} ({o.get('sure','')} dk)")
        lines.append("")
    return "\n".join(lines)
