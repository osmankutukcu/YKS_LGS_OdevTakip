import random
from datetime import date


class SmartTipGenerator:
    """
    Kullanıcı istatistiklerini analiz eder ve bağlama uygun,
    profesyonel, motive edici ve aksiyon odaklı 'Günün İpucu' üretir.

    ✅ Mevcut yapıyı bozmaz:
    - generate(stats, trend_analysis=None) çağrısı aynen çalışır
    - dönüş: {'text','icon','colors'} aynen
    """

    @staticmethod
    def generate(
        stats: dict,
        trend_analysis: dict = None,
        # --- EK: opsiyonel kişiselleştirme (mevcut yapıyı bozmaz) ---
        tone: str = "ogrenci",          # "ogrenci" | "veli" | "yonetici"
        student_name: str = None,       # "Furkan"
        branch: str = None              # "Sayısal", "Eşit Ağırlık", "TYT", "AYT Matematik" vb.
    ) -> dict:
        # ---------------------------
        # 0) Güvenli parse yardımcıları
        # ---------------------------
        def to_int(v, default=0):
            try:
                if v is None:
                    return default
                if isinstance(v, bool):
                    return int(v)
                return int(v)
            except Exception:
                try:
                    return int(float(str(v).replace(",", ".")))
                except Exception:
                    return default

        def clamp(x, lo, hi):
            return max(lo, min(hi, x))

        def pct(x):
            return clamp(to_int(x, 0), 0, 100)

        def normalize_alerts(alerts):
            if not alerts:
                return []
            out = []
            for a in alerts:
                if isinstance(a, dict):
                    txt = str(a.get("text") or a.get("msg") or a.get("message") or "").strip()
                    sev = str(a.get("severity") or a.get("level") or "").strip().lower()
                    tip = str(a.get("tip") or a.get("action") or "").strip()
                else:
                    txt = str(a).strip()
                    sev = ""
                    tip = ""

                if not txt:
                    continue

                if sev not in ("high", "medium", "low"):
                    t = txt.lower()
                    if any(k in t for k in ["kritik", "acil", "gecik", "kaçır", "eksik", "critical", "overdue"]):
                        sev = "high"
                    elif any(k in t for k in ["uyarı", "risk", "dikkat", "warning"]):
                        sev = "medium"
                    else:
                        sev = "low"

                out.append({"severity": sev, "text": txt, "tip": tip})

            rank = {"high": 0, "medium": 1, "low": 2}
            out.sort(key=lambda x: rank.get(x["severity"], 1))
            return out

        def day_context():
            today = date.today()
            wd = today.weekday()
            if wd == 0:
                return ("Pazartesi", "Haftaya doğru başla", "📅")
            if wd == 4:
                return ("Cuma", "Haftayı güçlü kapat", "🎯")
            if wd >= 5:
                return ("Hafta Sonu", "Derin çalışma / deneme zamanı", "📝")
            return ("Hafta İçi", "Rutin + küçük kazanım", "⚡")

        def tone_pack(tone_key: str):
            """
            Her ton için dil/üslup paketleri.
            """
            tone_key = (tone_key or "ogrenci").strip().lower()
            if tone_key in ("veli", "parent"):
                return {
                    "hello": "Bilgilendirme",
                    "you": "Siz",
                    "focus": "odak",
                    "action_title": "Bugün yapılacaklar (veli desteğiyle)",
                    "softener": "Dilerseniz",
                    "closing": "Küçük ama düzenli adımlar büyük fark yaratır.",
                    "style": "veli",
                }
            if tone_key in ("yonetici", "yönetici", "admin", "teacher", "ogretmen"):
                return {
                    "hello": "Yönetici Notu",
                    "you": "Siz",
                    "focus": "öncelik",
                    "action_title": "Bugün yapılacaklar (operasyon planı)",
                    "softener": "Öneri:",
                    "closing": "Ölç, uygula, geri bildirim al, iyileştir.",
                    "style": "yonetici",
                }
            # varsayılan: öğrenci
            return {
                "hello": "AI Koç Notu",
                "you": "Sen",
                "focus": "hedef",
                "action_title": "Bugün yapılacaklar (mini görevler)",
                "softener": "Hadi",
                "closing": "Bugün küçük bir adım at, yarın büyütürüz.",
                "style": "ogrenci",
            }

        # ---------------------------
        # 1) Veri çözümleme
        # ---------------------------
        stats = stats or {}
        rate = pct(stats.get("success_rate", 0))
        streak = to_int(stats.get("streak_days", 0), 0)
        minutes = to_int(stats.get("weekly_minutes", 0), 0)
        total = to_int(stats.get("total_homeworks", 0), 0)

        alerts = normalize_alerts(stats.get("alerts", []))
        high_alerts = [a for a in alerts if a["severity"] == "high"]
        med_alerts = [a for a in alerts if a["severity"] == "medium"]

        trend_status = None
        trend_msg = None
        if isinstance(trend_analysis, dict):
            trend_status = trend_analysis.get("status")
            trend_msg = trend_analysis.get("message")

        day_name, day_theme, day_icon = day_context()
        tp = tone_pack(tone)

        # Kişiselleştirme başlığı
        who = student_name.strip() if isinstance(student_name, str) and student_name.strip() else None
        br = branch.strip() if isinstance(branch, str) and branch.strip() else None
        header_bits = [tp["hello"]]
        if who:
            header_bits.append(who)
        if br:
            header_bits.append(f"({br})")
        header = " • ".join(header_bits)

        # ---------------------------
        # 2) KPI / risk
        # ---------------------------
        
        # --- EMPTY STATE CHECK ---
        total_students = stats.get("total_students", None)
        if total == 0 or total_students == 0:
            # Hiç veri yoksa
            
            # Gün bağlamı
            day_line = f"{day_icon} {day_name}: {day_theme}."
            
            welcome_msg = "Henüz sistemde analiz edilecek bir veri bulunamadı."
            tasks_block = (
                "• İlk adım: 'Öğrenci Kaydı' menüsünden öğrenci ekle.\n"
                "• İkinci adım: 'Ödev Takip' menüsünden ilk ödevi ver.\n"
                "• Üçüncü adım: Yarın buraya tekrar bak, ilk analizi göreceksin."
            )
            
            full_text = (
                f"{header}\n"
                f"{day_line}\n"
                f"{welcome_msg}\n\n"
                f"Sistemi başlatmak için:\n{tasks_block}\n\n"
                "Başlamak başarmanın yarısıdır! 🚀"
            )
            
            return {
                "text": full_text,
                "icon": "👋",
                "colors": ("#64748b", "#334155")
            }
        # -------------------------

        alert_penalty = (len(high_alerts) * 18) + (len(med_alerts) * 8)
        discipline = clamp((rate * 0.55) + (clamp(streak, 0, 30) * 1.2) - alert_penalty, 0, 100)

        risk = 0
        if rate < 70:
            risk += (70 - rate) * 0.8
        risk += len(high_alerts) * 22
        risk += max(0, 7 - streak) * 5
        risk = clamp(int(risk), 0, 100)

        # ---------------------------
        # 3) Bugün yapılacaklar → 3 maddelik mini görev
        # ---------------------------
        # Tonlara göre 3 görev üretimi (daha gerçek “AI koç” gibi)
        def build_today_tasks():
            # Özel durum: kritik uyarı
            if high_alerts:
                top = high_alerts[0]["text"]
                if tp["style"] == "yonetici":
                    return [
                        f"Kritik listeyi çıkar: {len(high_alerts)} kritik uyarı → ilk 5 vakayı sırala.",
                        f"En kritik maddeyi kapatacak aksiyon belirle: “{top}”.",
                        "Gün sonu: 10 dk raporla (kaç kişi temizlendi / kaç kişi kaldı).",
                    ]
                if tp["style"] == "veli":
                    return [
                        f"Kritik gecikme var ({len(high_alerts)}): bugün 15 dk kısa görüşme/hatırlatma planlayın.",
                        "En kısa 1 ödevi birlikte seçip bitirmesini sağlayın (başlamak = yarı başarı).",
                        "Akşam 5 dk: ‘Bugün ne iyi gitti?’ mini değerlendirme yapın.",
                    ]
                # öğrenci
                return [
                    f"Öncelik: kritik gecikmeyi azalt ({len(high_alerts)}). 1 kısa işi seç ve bitir.",
                    "25 dk odak + 5 dk mola (pomodoro).",
                    "Bitince işaretle: ‘tamamlandı’ → motivasyon zinciri kırılmaz.",
                ]

            # Başarı düşükse
            if rate < 70:
                if tp["style"] == "yonetici":
                    return [
                        "Başarı düşüşünün kök nedenini seç: konu/plan/motivasyon (1 tanesi).",
                        "Bugün planı sadeleştir: 1 zor konu + 1 kısa tekrar hedefi yaz.",
                        "Gün sonu: gerçekleşen süreyi ölç → yarın kapasiteyi %10 ayarla.",
                    ]
                if tp["style"] == "veli":
                    return [
                        "Bugün 20 dk ‘en zor konu’ için sessiz ortam + telefon kapalı.",
                        "10 soru çözdürüp sadece yanlışlara bakın (uzun analiz yok).",
                        "Küçük ödül: tamamlayınca 10 dk sevdiği etkinlik.",
                    ]
                return [
                    "1 zor konudan sadece 1 parça seç (küçük hedef).",
                    "10 soru + 5 dk yanlış analizi yap.",
                    "Bittiğinde 5 dk özet çıkar (3 madde).",
                ]

            # Streak düşükse
            if streak < 3:
                if tp["style"] == "yonetici":
                    return [
                        "Minimum rutin tanımla: günlük 20 dk zorunlu çalışma.",
                        "Öğrencinin en düşük dirençli görevini seç (başlatma amaçlı).",
                        "Gün sonu: streak’ı koruyacak yarın için 1 mikro görev bırak.",
                    ]
                if tp["style"] == "veli":
                    return [
                        "Bugün sadece 20 dk: ‘başlama’ eşiğini geçsin yeter.",
                        "Çalışma bitince hemen işaretleyin (görsel takip motivasyonu artırır).",
                        "Yarın için masaya 1 küçük görev bırakın (hazır ortam).",
                    ]
                return [
                    "Sadece 20 dk çalış (minimum kural).",
                    "En kolay görevden başla, ısınma yap.",
                    "Yarın için 1 mini hedef yaz (1 cümle).",
                ]

            # Genel durum: dengeli
            if minutes < 300:
                # az çalışma → yükselt
                if tp["style"] == "yonetici":
                    return [
                        "Bugün süre hedefini artır: +15 dk ekle (kademeli artış).",
                        "1 zor + 1 kolay görevle dengele.",
                        "Gün sonu: süre gerçekleşmesini sisteme kaydet.",
                    ]
                if tp["style"] == "veli":
                    return [
                        "Bugün 35 dk hedef koyun (25+10).",
                        "Zor görevi önce yapın, kolayla kapatın.",
                        "Akşam 5 dk: yarının hedefini beraber yazın.",
                    ]
                return [
                    "Bugün 35–45 dk hedef koy (25+10+5).",
                    "1 zor + 1 kolay görev seç.",
                    "Gün sonu 5 dk: yarın için plan kontrolü yap.",
                ]

            # iyi gidiyor
            if tp["style"] == "yonetici":
                return [
                    "İyi giden rutini bozma: bugün planı aynı iskelette sürdür.",
                    "Hata analizi için 10 dk slot aç (kalite artırır).",
                    "Gün sonu: risk skorunu kontrol et, gerekiyorsa küçük düzeltme yap.",
                ]
            if tp["style"] == "veli":
                return [
                    "Rutin güzel: bugün sadece istikrarı koruyun.",
                    "10 dk yanlışlara bakıp doğru yöntemle tekrar ettirin.",
                    "Kısa motivasyon: ‘Bugün düzenliydin’ geri bildirimi verin.",
                ]
            return [
                "Planı aynen uygula (istikrar).",
                "10 dk yanlış analizi ekle.",
                "Kendine küçük bir ödül koy (tamamlayınca).",
            ]

        tasks3 = build_today_tasks()

        # ---------------------------
        # 4) Metin üretimi (ton + isim + branş)
        # ---------------------------
        # Giriş satırı: kime göre
        header_bits = [tp["hello"]]
        if who:
            header_bits.append(who)
        if br:
            header_bits.append(f"({br})")
        header = " • ".join(header_bits)

        # Durum cümlesi (tonlara göre)
        if tp["style"] == "yonetici":
            state_line = f"Durum özeti: Başarı %{rate} | Streak {streak} gün | Haftalık {minutes} dk | Risk %{risk}."
        elif tp["style"] == "veli":
            state_line = f"Durum: Başarı %{rate}, {streak} günlük seri, haftalık {minutes} dk çalışma. Risk seviyesi %{risk}."
        else:
            state_line = f"Bugünkü durumun: %{rate} başarı, {streak} gün seri, bu hafta {minutes} dk. Risk %{risk}."

        # Trend satırı (varsa)
        trend_line = ""
        if trend_status:
            if trend_status == "increasing":
                trend_line = "Trend: Yükseliş var. Bu ivmeyi korumak için küçük bir zorluk artışı ekleyebiliriz."
            elif trend_status == "decreasing":
                trend_line = "Trend: Düşüş var. Planı sadeleştirip düzeni geri alalım."
            elif trend_status == "volatile":
                trend_line = "Trend: Dalgalı. Daha stabil bir rutin daha iyi sonuç verir."
            elif trend_msg:
                trend_line = f"Trend notu: {trend_msg}"

        # Kritik uyarı vurgusu
        alert_line = ""
        if high_alerts:
            alert_line = f"🚨 Kritik: {len(high_alerts)} adet kritik uyarı var. Öncelik bu liste."
        elif med_alerts:
            alert_line = f"⚠️ Uyarı: {len(med_alerts)} orta seviye uyarı var. Bugün küçük düzeltmeler yeter."

        # 3 görev metni
        tasks_block = "\n".join([f"• {t}" for t in tasks3])

        # Gün bağlamı
        day_line = f"{day_icon} {day_name}: {day_theme}."

        # Tam metin
        full_text = (
            f"{header}\n"
            f"{day_line}\n"
            f"{state_line}\n"
            f"{alert_line}\n"
            f"{trend_line}\n"
            f"\n{tp['action_title']}:\n{tasks_block}\n"
            f"\n{tp['closing']}"
        ).strip()

        # ---------------------------
        # 5) Renk/ikon seçimi (profesyonel)
        # ---------------------------
        # Renk şeması: risk ve başarıya göre
        if high_alerts or risk >= 70:
            icon = "🚨"
            colors = ("#ef4444", "#7f1d1d")
        elif risk >= 40:
            icon = "⚠️"
            colors = ("#f59e0b", "#b45309")
        elif rate >= 85 and streak >= 7:
            icon = "🚀"
            colors = ("#10b981", "#047857")
        elif rate >= 70:
            icon = "⚡"
            colors = ("#3b82f6", "#1e40af")
        else:
            icon = "🧩"
            colors = ("#64748b", "#334155")

        # Deterministik küçük varyasyon: ikon aynı kalabilir ama metin tutarlı kalsın
        seed_key = f"{date.today().isoformat()}|{tone}|{who}|{br}|{rate}|{streak}|{minutes}|{len(high_alerts)}|{len(med_alerts)}"
        rnd = random.Random(seed_key)
        # Bazı günler ikonu “gün bağlamı” ile zenginleştirelim (çok küçük)
        if tp["style"] == "ogrenci" and rnd.random() < 0.25:
            icon = day_icon

        return {
            "text": full_text,
            "icon": icon,
            "colors": colors
        }
