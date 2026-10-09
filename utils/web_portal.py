# -*- coding: utf-8 -*-
import os
import json
import sqlite3
from datetime import date, datetime, timedelta
import db

class WebPortalGenerator:
    """
    Seçilen öğrenci için tek dosyalık (HTML) modern bir web panosu oluşturur.
    Chart.js CDN kullanarak grafikler çizer.
    """
    def __init__(self, student_id: int, student_name: str):
        self.sid = student_id
        self.name = student_name
        self.con = db.get_conn()

    def generate(self, output_path: str):
        """HTML dosyasını üretir ve kaydeder."""
        data = self._fetch_data()
        html_content = self._render_html(data)
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)

    def _fetch_data(self):
        """Veritabanından gerekli analiz verilerini çeker."""
        # Önce analiz motorunu çalıştırıp verileri tazeleyelim
        try:
            from utils.analytics_engine import rebuild_daily, rebuild_weekly_by_ders
            # Geniş bir aralık verelim: Son 40 gün + Gelecek 7 gün
            # portal grafiklerinde kullanılıyor
            start_date = date.today() - timedelta(days=40)
            end_date = date.today() + timedelta(days=7)
            
            rebuild_daily(self.con, start_date, end_date)
            # Haftalık ders verisi opsiyonel ama yapabiliriz
            # rebuild_weekly_by_ders(self.con, ...) - gerekirse
        except ImportError:
            pass

        cur = self.con.cursor()
        
        # 1. Genel Durum (Toplam Çözülen, Tamamlanan Görevler)
        # Basitçe odev_satir ve odev tablolarından toplam sayılara bakalım
        # Performans tabloları (ogrenci_perf_gunluk vs) dolu varsayıyoruz.
        
        # Son 30 Gündeki İstatistikler
        cur.execute("""
            SELECT COUNT(*), SUM(tamam) 
            FROM ogrenci_perf_gunluk 
            WHERE ogrenci_id=? AND date(gun) >= date('now', '-30 days')
        """, (self.sid,))
        row = cur.fetchone()
        last_30_total = row[0] if row else 0
        last_30_done = row[1] if row and row[1] else 0
        
        try:
            success_rate = int((last_30_done / last_30_total) * 100) if last_30_total > 0 else 0
        except:
            success_rate = 0

        # 2. Ders Bazlı Başarı (Bar Chart)
        # Hem odev hem de odev_satir tablolarını birleştirelim
        
        cur.execute("""
            SELECT COALESCE(ders, 'Genel') as ders_adi,
                   COUNT(*) as toplam,
                   SUM(CASE WHEN durum IN ('tamam','yapildi','yapıldı','bitti','done') THEN 1 ELSE 0 END) as bitti
              FROM (
                  SELECT ders, LOWER(COALESCE(durum,'devam')) as durum FROM odev_satir WHERE ogrenci_id=?
                  UNION ALL
                  SELECT ders, LOWER(COALESCE(durum,'devam')) as durum FROM odev WHERE ogrenci_id=?
              )
             GROUP BY COALESCE(ders, 'Genel')
        """, (self.sid, self.sid))
        
        subjects = []
        subj_rates = []
        for r in cur.fetchall():
            d_name = r[0]
            d_tot = r[1]
            d_done = r[2]
            rate = int((d_done/d_tot)*100) if d_tot > 0 else 0
            subjects.append(d_name)
            subj_rates.append(rate)

        # 3. Son 5 Hafta Gelişim (Line Chart)
        # ogrenci_perf_gunluk tablosunu haftalık gruplayarak
        cur.execute("""
            SELECT strftime('%W', gun) as hafta,
                   MIN(date(gun)),
                   SUM(tamam),
                   COUNT(*)
              FROM ogrenci_perf_gunluk
             WHERE ogrenci_id=? AND date(gun) >= date('now', '-35 days')
             GROUP BY hafta
             ORDER BY MIN(date(gun))
        """, (self.sid,))
        
        weeks = []
        weekly_rates = []
        for r in cur.fetchall():
            w_date = r[1] # Haftanın ilk günü temsili
            w_done = r[2]
            w_total = r[3]
            rate = int((w_done/w_total)*100) if w_total > 0 else 0
            # Tarihi formatla g-a
            try:
                dt = datetime.strptime(w_date, "%Y-%m-%d")
                lbl = dt.strftime("%d %b")
            except:
                lbl = w_date
            weeks.append(lbl)
            weekly_rates.append(rate)

        # 4. Geciken/Bekleyen Ödev Listesi (Son 10)
        # Hem odev hem odev_satir
        cur.execute("""
            SELECT ders, kitap, konu, tarih
            FROM (
                SELECT ders, kitap, konu, tarih, id, durum FROM odev_satir WHERE ogrenci_id=?
                UNION ALL
                SELECT ders, kitap_ad as kitap, konu_ad as konu, NULL as tarih, id, durum FROM odev WHERE ogrenci_id=?
            )
            WHERE durum NOT IN ('tamam','yapildi','yapıldı','bitti','done')
            ORDER BY COALESCE(tarih, '9999-99-99') ASC, id DESC
            LIMIT 10
        """, (self.sid, self.sid))
        
        pending_tasks = []
        for r in cur.fetchall():
            pending_tasks.append({
                "ders": r[0] or "-",
                "kitap": r[1] or "-",
                "konu": r[2] or "-",
                "tarih": r[3] or "-"
            })

        return {
            "generated_at": date.today().strftime("%d.%m.%Y"),
            "student_name": self.name,
            "stats": {
                "success_rate": success_rate,
                "total_tasks_30d": last_30_total,
                "done_tasks_30d": last_30_done
            },
            "charts": {
                "subjects": subjects,
                "subj_rates": subj_rates,
                "weeks": weeks,
                "weekly_rates": weekly_rates
            },
            "pending": pending_tasks
        }

    def _render_html(self, data):
        # JSON verileri JS içine gömmek için
        chart_data_js = json.dumps(data["charts"])
        
        html = f"""<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Öğrenci Portalı - {data['student_name']}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {{
            --primary: #3b82f6;
            --bg: #f8fafc;
            --card-bg: #ffffff;
            --text: #1e293b;
            --text-light: #64748b;
            --border: #e2e8f0;
            --success: #22c55e;
            --danger: #ef4444;
        }}
        body {{
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            background-color: var(--bg);
            color: var(--text);
            margin: 0;
            padding: 20px;
            line-height: 1.5;
        }}
        .container {{
            max-width: 1000px;
            margin: 0 auto;
        }}
        header {{
            background: var(--card-bg);
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        h1 {{ margin: 0; font-size: 1.5rem; }}
        .date {{ color: var(--text-light); font-size: 0.9rem; }}
        
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }}
        
        .card {{
            background: var(--card-bg);
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            border: 1px solid var(--border);
        }}
        
        .stat-box {{
            text-align: center;
        }}
        .stat-val {{
            font-size: 2.5rem;
            font-weight: 700;
            color: var(--primary);
        }}
        .stat-label {{
            color: var(--text-light);
            font-weight: 500;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9rem;
        }}
        th {{ text-align: left; color: var(--text-light); padding: 10px; border-bottom: 1px solid var(--border); }}
        td {{ padding: 10px; border-bottom: 1px solid var(--border); }}
        tr:last-child td {{ border-bottom: none; }}
        
        .badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.75rem;
            font-weight: 600;
            background: #f1f5f9;
            color: #475569;
        }}
        .badge-red {{ background: #fef2f2; color: #ef4444; }}
    </style>
</head>
<body>

<div class="container">
    <header>
        <div>
            <h1>👋 Merhaba, {data['student_name']}</h1>
            <div class="date">Rapor Tarihi: {data['generated_at']}</div>
        </div>
        <div style="text-align:right">
            <span style="display:block; font-size:0.8rem; color:var(--text-light)">Başarı Oranı</span>
            <span style="font-size:1.5rem; font-weight:bold; color:var(--success)">%{data['stats']['success_rate']}</span>
        </div>
    </header>

    <!-- Üst İstatistikler -->
    <div class="grid">
        <div class="card stat-box">
            <div class="stat-val">{data['stats']['done_tasks_30d']}</div>
            <div class="stat-label">Son 30 Gün Tamamlanan</div>
        </div>
        <div class="card stat-box">
            <div class="stat-val">{data['stats']['total_tasks_30d']}</div>
            <div class="stat-label">Son 30 Gün Toplam Görev</div>
        </div>
    </div>

    <!-- Grafikler -->
    <div class="grid">
        <div class="card">
            <h3>📈 Haftalık Gelişim</h3>
            <canvas id="trendChart"></canvas>
        </div>
        <div class="card">
            <h3>📚 Ders Başarısı</h3>
            <canvas id="subjectChart"></canvas>
        </div>
    </div>

    <!-- Eksik Listesi -->
    <div class="card">
        <h3>⚠️ Öncelikli Eksikler (İlk 10)</h3>
        <table>
            <thead>
                <tr>
                    <th>Ders</th>
                    <th>Kitap / Kaynak</th>
                    <th>Konu</th>
                    <th>Tarih</th>
                </tr>
            </thead>
            <tbody>
"""
        for task in data["pending"]:
            html += f"""
                <tr>
                    <td><b>{task['ders']}</b></td>
                    <td>{task['kitap']}</td>
                    <td>{task['konu']}</td>
                    <td><span class="badge badge-red">{task['tarih']}</span></td>
                </tr>
            """
            
        html += """
            </tbody>
        </table>
        <div style="margin-top:15px; text-align:center; color:var(--text-light); font-size:0.8rem;">
            * Sadece tamamlanmamış veya gecikmiş ilk 10 görev listelenmiştir.
        </div>
    </div>
</div>

<script>
    const data = JSON.parse('""" + chart_data_js + """');
    
    // Trend Chart
    new Chart(document.getElementById('trendChart'), {
        type: 'line',
        data: {
            labels: data.weeks,
            datasets: [{
                label: 'Başarı %',
                data: data.weekly_rates,
                borderColor: '#3b82f6',
                backgroundColor: 'rgba(59,130,246,0.1)',
                tension: 0.4,
                fill: true
            }]
        },
        options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: { y: { beginAtZero: true, max: 100 } }
        }
    });

    // Subject Chart
    new Chart(document.getElementById('subjectChart'), {
        type: 'bar',
        data: {
            labels: data.subjects,
            datasets: [{
                label: 'Başarı %',
                data: data.subj_rates,
                backgroundColor: [
                    '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'
                ],
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: { y: { beginAtZero: true, max: 100 } }
        }
    });
</script>

</body>
</html>
"""
        return html
