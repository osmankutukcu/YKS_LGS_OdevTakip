# -*- coding: utf-8 -*-
import datetime
from PyQt6.QtWidgets import QApplication, QDialog
from PyQt6.QtGui import QTextDocument, QPageLayout, QPageSize
from PyQt6.QtCore import QMarginsF
from PyQt6.QtPrintSupport import QPrinter, QPrintDialog

import db

class PDFReportGenerator:
    def __init__(self):
        pass

    def _generate_html_content(self, student_id: int):
        """
        Fetches data and returns the HTML string for the report.
        Returns None if student not found or error.
        """
        try:
            con = db.get_conn()
            cur = con.cursor()

            # 1. Fetch Student Info
            row_std = cur.execute("SELECT ad, soyad, ana_grup, alt_grup FROM ogrenci WHERE id=?", (student_id,)).fetchone()
            if not row_std:
                return None
            ad_soyad = f"{row_std['ad']} {row_std['soyad']}"
            
            p_ana = row_std['ana_grup'] or ""
            p_alt = row_std['alt_grup'] or ""
            sinif = f"{p_ana} / {p_alt}".strip(" / ") or "Belirtilmemiş"

            # 2. Fetch Stats (General)
            total_hw = cur.execute("SELECT COUNT(*) FROM odev WHERE ogrenci_id=?", (student_id,)).fetchone()[0]
            completed_hw = cur.execute("SELECT COUNT(*) FROM odev WHERE ogrenci_id=? AND (durum='yapildi' OR durum='Tamamlandı')", (student_id,)).fetchone()[0]
            incomplete_hw = total_hw - completed_hw
            rate = int((completed_hw / total_hw) * 100) if total_hw > 0 else 0

            # 3. Fetch Recent Homeworks (Limit 60)
            rows_hw = cur.execute("""
                SELECT o.ders, o.konu_ad, o.durum, o.aciklama, 
                       ok.verilis_tarihi as start_date, 
                       ok.bitis_tarihi as end_date
                FROM odev o
                LEFT JOIN odev_kume ok ON o.kume_id = ok.id
                WHERE o.ogrenci_id=? 
                ORDER BY ok.bitis_tarihi DESC, o.id DESC 
                LIMIT 60
            """, (student_id,)).fetchall()

            # 4. Filter Last 30 Days (Python Side) with ROBUST PARSING
            all_hw_dates = cur.execute("""
                SELECT o.ders, o.durum, ok.bitis_tarihi as end_date 
                FROM odev o
                LEFT JOIN odev_kume ok ON o.kume_id = ok.id
                WHERE o.ogrenci_id=?
            """, (student_id,)).fetchall()
            
            from datetime import datetime, timedelta
            today = datetime.now()
            cutoff = today - timedelta(days=30)
            
            stats_map = {} # ders -> {total:0, done:0}
            
            # --- Robust Date Parser Helper ---
            def parse_date_internal(d_str):
                if not d_str: return None
                # Try common formats: ISO (YYYY-MM-DD), Turkish (DD.MM.YYYY), others
                for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d-%m-%Y", "%Y.%m.%d"):
                    try:
                        return datetime.strptime(d_str, fmt)
                    except ValueError:
                        continue
                return None
            # ---------------------------------

            for r in all_hw_dates:
                d_str = r['end_date']
                d_date = parse_date_internal(d_str)
                
                # If date is valid and recent
                if d_date and d_date >= cutoff:
                    ders = r['ders']
                    status = (r['durum'] or "").lower()
                    if ders not in stats_map: 
                        stats_map[ders] = {'total':0, 'done':0}
                    stats_map[ders]['total'] += 1
                    if status in ('yapildi', 'tamamlandı', 'tamam'):
                        stats_map[ders]['done'] += 1

            # Convert map to list sorted by total
            rows_30 = []
            for ders, val in stats_map.items():
                rows_30.append({'ders': ders, 'total': val['total'], 'done': val['done']})
            rows_30.sort(key=lambda x: x['total'], reverse=True)

            # 5. Fetch Book Progress
            rows_books = []
            try:
                rows_books = cur.execute("""
                    SELECT ders, kitap, bitti_say, konu_say, yuzde 
                    FROM ogrenci_kitap_ilerleme 
                    WHERE ogrenci_id=? 
                    ORDER BY ders, kitap
                """, (student_id,)).fetchall()
            except Exception:
                pass

            # --- NEW: 6. Trial Exams (Denemeler) ---
            rows_trials = []
            try:
                rows_trials = cur.execute("""
                    SELECT d.deneme_adi, d.tarih, SUM(s.net) as toplam_net 
                    FROM deneme_sonuclari s
                    JOIN denemeler d ON d.id = s.deneme_id
                    WHERE s.ogrenci_id=? 
                    GROUP BY d.id 
                    ORDER BY d.tarih DESC 
                    LIMIT 3
                """, (student_id,)).fetchall()
            except Exception:
                pass 

            # --- NEW: 7. Weekly Targets (Koçluk) ---
            target_data = {'target': 0, 'solved': 0, 'pct': 0}
            try:
                row_plan = cur.execute("""
                    SELECT id FROM koc_plan WHERE ogrenci_id=? AND aktif=1 ORDER BY id DESC LIMIT 1
                """, (student_id,)).fetchone()
                
                if row_plan:
                    pid = row_plan['id']
                    row_sums = cur.execute("""
                        SELECT SUM(hedef_soru), SUM(cozulen_soru) FROM koc_hedef WHERE plan_id=?
                    """, (pid,)).fetchone()
                    if row_sums and row_sums[0]:
                        t = row_sums[0] or 0
                        s = row_sums[1] or 0
                        p = int((s/t)*100) if t > 0 else 0
                        target_data = {'target': t, 'solved': s, 'pct': p}
            except Exception:
                pass

            # --- NEW: 8. Subject Status (Konu Takip) ---
            subject_stats = {'done': 0, 'working': 0}
            try:
                rows_subs = cur.execute("""
                    SELECT durum, COUNT(*) as cnt FROM koc_konu_takip WHERE ogrenci_id=? GROUP BY durum
                """, (student_id,)).fetchall()
                for r in rows_subs:
                    if r['durum'] == 2: subject_stats['done'] = r['cnt']
                    elif r['durum'] == 1: subject_stats['working'] = r['cnt']
            except Exception:
                pass


            # 9. Generate HTML
            return self._create_html(ad_soyad, sinif, total_hw, completed_hw, incomplete_hw, rate, 
                                           rows_hw, rows_30, rows_books,
                                           rows_trials, target_data, subject_stats)
        except Exception as e:
            print(f"Data Fetch Error: {e}")
            return None

    def generate_student_report(self, student_id: int, file_path: str) -> bool:
        """
        Generates a PDF report for the given student save to file_path.
        Uses QPdfWriter for robust cross-platform PDF generation.
        """
        html_content = self._generate_html_content(student_id)
        if not html_content:
            return False

        try:
            from PyQt6.QtGui import QPdfWriter
            
            writer = QPdfWriter(file_path)
            writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
            writer.setPageMargins(QMarginsF(10, 10, 10, 10), QPageLayout.Unit.Millimeter)
            # 300 DPI for high quality
            writer.setResolution(300) 
            
            doc = QTextDocument()
            doc.setHtml(html_content)
            doc.print(writer)
            return True
        except Exception as e:
            print(f"PDF Gen Error: {e}")
            return False

    def print_student_report(self, student_id: int) -> bool:
        """
        Opens Print Dialog to print report directly to physical printer.
        """
        html_content = self._generate_html_content(student_id)
        if not html_content:
            return False

        try:
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            # Default to A4
            printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
            printer.setPageMargins(QMarginsF(10, 10, 10, 10), QPageLayout.Unit.Millimeter)

            # Show Dialog
            dialog = QPrintDialog(printer)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                doc = QTextDocument()
                doc.setHtml(html_content)
                doc.print(printer)
                return True
            else:
                return False # Cancelled
        except Exception as e:
            print(f"Direct Print Error: {e}")
            return False

    def _create_html(self, name, sinif, total, done, missing, rate, homeworks, stats_30, books,
                     trials, target_data, subject_stats):
        
        from datetime import datetime, date
        today_date = date.today()
        today_str = today_date.strftime("%d.%m.%Y")
        
        # Colors
        c_blue    = "#1e40af"
        c_green   = "#15803d"
        c_amber   = "#b45309"
        c_red     = "#b91c1c"
        c_gray    = "#374151"
        c_border  = "#e2e8f0"

        # Rate Logic
        if rate >= 85:
            rate_c, rate_bg, rate_txt = c_green, "#dcfce7", "MÜKEMMEL"
        elif rate >= 70:
            rate_c, rate_bg, rate_txt = c_green, "#dcfce7", "İYİ"
        elif rate >= 50:
            rate_c, rate_bg, rate_txt = c_amber, "#fef3c7", "ORTA"
        else:
            rate_c, rate_bg, rate_txt = c_red, "#fee2e2", "KRİTİK"
        
        # Helper: Date Parser
        def parse_date_internal(d_str):
            if not d_str: return None
            for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d-%m-%Y", "%Y.%m.%d"):
                try:
                    return datetime.strptime(d_str, fmt)
                except ValueError:
                    continue
            return None

        # --- HTML Generator Helpers ---

        # 1. Homework Rows
        rows_hw_html = ""
        # Limit display to 20 to save space for new sections
        display_hw = homeworks[:20] 
        for i, hw in enumerate(display_hw):
            status_lower = (hw['durum'] or "").lower()
            start_dt = parse_date_internal(hw['start_date'])
            end_dt = parse_date_internal(hw['end_date'])
            start_str = start_dt.strftime("%d.%m.%Y") if start_dt else (hw['start_date'] or '-')
            end_str = end_dt.strftime("%d.%m.%Y") if end_dt else (hw['end_date'] or '-')

            is_done = status_lower in ("yapildi", "tamamlandı", "tamam")
            is_overdue = False
            if not is_done and end_dt:
                if end_dt.date() < today_date:
                    is_overdue = True

            if is_done:
                st_html = f'<span style="color:{c_green}; font-weight:800;">YAPILDI</span>'
            elif is_overdue:
                st_html = f'<span style="color:{c_red}; font-weight:800;">GECİKTİ</span>'
            else:
                st_html = f'<span style="color:{c_amber}; font-weight:800;">DEVAM</span>'

            bg = "#ffffff" if i % 2 == 0 else "#f8fafc"
            rows_hw_html += f"""
            <tr style="background-color: {bg};">
                <td style="padding: 3pt; border-bottom: 1px solid {c_border}; font-weight:600;">{hw['ders']}</td>
                <td style="padding: 3pt; border-bottom: 1px solid {c_border}; color:#444;">{hw['konu_ad']}</td>
                <td style="padding: 3pt; border-bottom: 1px solid {c_border}; text-align: center; color:#555;">{start_str}</td>
                <td style="padding: 3pt; border-bottom: 1px solid {c_border}; text-align: center; font-weight:600;">{end_str}</td>
                <td style="padding: 3pt; border-bottom: 1px solid {c_border};">{st_html}</td>
                <td style="padding: 3pt; border-bottom: 1px solid {c_border}; color: #666; font-size: 7pt;">{hw['aciklama'] or ''}</td>
            </tr>
            """

        # 2. Last 30 Days
        rows_30_html = ""
        if stats_30:
            for row in stats_30[:6]: # Limit 6 lines
                d = row['ders']
                t = row['total']
                dn = row['done']
                r = int((dn/t)*100) if t>0 else 0
                bar_color = c_green if r >= 80 else (c_amber if r >= 50 else c_red)
                bar_width = max(2, r)
                rows_30_html += f"""
                <tr>
                    <td style="padding: 2pt 0; users width: 45%; font-weight: bold; font-size: 7pt; color: #1e3a8a;">{d}</td>
                    <td style="padding: 2pt 0; width: 15%; color: #666; font-size: 7pt;">{dn}/{t}</td>
                    <td style="padding: 2pt 0; width: 10%; font-weight: bold; color: {bar_color}; font-size: 7pt;">%{r}</td>
                    <td style="padding: 2pt 0; width: 30%; vertical-align: middle;">
                        <table width="100%" height="4" cellspacing="0" cellpadding="0" style="background-color: #f1f5f9; border: 1px solid #e2e8f0;">
                            <tr><td width="{bar_width}%" style="background-color: {bar_color};"></td><td width="{100-bar_width}%"></td></tr>
                        </table>
                    </td>
                </tr>
                """
        else:
            rows_30_html = "<tr><td colspan='4' style='color:#999; font-style:italic; padding: 5pt;'>Veri yok.</td></tr>"

        # 3. Book Progress
        rows_books_html = ""
        if books:
            for row in books[:6]: # Limit 6 lines
                d = row['ders']
                k = row['kitap']
                # Truncate book name if too long
                if len(k) > 20: k = k[:18] + ".."
                y = row['yuzde']
                bar_color = c_green if y >= 80 else (c_amber if y >= 50 else c_red)
                bar_width = max(2, y)
                rows_books_html += f"""
                <tr>
                    <td style="padding: 2pt 0; width: 55%;">
                        <div style="font-weight: 700; font-size: 7pt; color: #1e3a8a;">{d}</div>
                        <div style="font-size: 6pt; color: #555;">{k}</div>
                    </td>
                    <td style="padding: 2pt 0; width: 10%; font-weight: bold; color: {bar_color}; font-size: 7pt;">%{y}</td>
                    <td style="padding: 2pt 0; width: 35%; vertical-align: middle;">
                         <table width="100%" height="4" cellspacing="0" cellpadding="0" style="background-color: #f1f5f9; border: 1px solid #e2e8f0;">
                            <tr><td width="{bar_width}%" style="background-color: {bar_color};"></td><td width="{100-bar_width}%"></td></tr>
                        </table>
                    </td>
                </tr>
                """
        else:
            rows_books_html = "<tr><td colspan='3' style='color:#999; font-style:italic; padding: 5pt;'>Veri yok.</td></tr>"

        # 4. Trials HTML
        if trials:
            trials_html = ""
            for t in trials:
                try:
                    net_val = f"{t['toplam_net']:.1f}" if t['toplam_net'] else "0"
                except: net_val = "0"
                nm = t['deneme_adi'] or "Deneme"
                if len(nm) > 18: nm = nm[:16] + ".."
                
                trials_html += f"""
                <tr>
                    <td style="padding: 2pt 0; font-size: 7pt; font-weight: 600; color: #334155;">{nm}</td>
                    <td style="padding: 2pt 0; font-size: 7pt; text-align: right; font-weight: 800; color: {c_blue};">{net_val} Net</td>
                </tr>
                """
        else:
            trials_html = "<tr><td colspan='2' style='color:#999; font-size:7pt; font-style:italic;'>Deneme verisi yok.</td></tr>"

        # 5. Targets HTML
        tg_t = target_data['target']
        tg_s = target_data['solved']
        tg_p = target_data['pct']
        tg_color = c_green if tg_p > 80 else (c_amber if tg_p > 50 else c_red)
        tg_width = max(2, min(100, tg_p))
        
        # 6. Subjects HTML
        sub_done = subject_stats['done']
        sub_work = subject_stats['working']

        # HTML Structure
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: 'Arial', sans-serif; margin: 0; padding: 0; color: #1f2937; }}
                table {{ border-collapse: collapse; width: 100%; }}
                td, th {{ padding: 0; margin: 0; vertical-align: top; }}
                
                .header-bg {{ background-color: {c_blue}; color: #fff; }}
                
                .section-head {{ 
                    font-size: 10pt; font-weight: 800; color: {c_blue}; 
                    border-bottom: 2px solid {c_blue}; margin-top: 10pt; margin-bottom: 4pt; padding-bottom: 2pt;
                    text-transform: uppercase;
                }}
                
                .stats-cell {{
                    border: 1px solid #ccc; padding: 6pt; text-align: center; background-color: #fff;
                }}
                .stats-val {{ font-size: 14pt; font-weight: 800; color: #111; display: block; }}
                .stats-lbl {{ font-size: 6pt; color: #666; text-transform: uppercase; margin-top: 1pt; display: block; }}
                
                .main-th {{ 
                    background-color: #f8fafc; color: #475569; font-weight: 700; text-align: left; 
                    padding: 4pt; border-bottom: 2px solid #ccc; font-size: 7pt; text-transform: uppercase;
                }}
                
                .card-box {{ border: 1px solid #e2e8f0; background-color: #f8fafc; padding: 5pt; border-radius: 4px; }}
            </style>
        </head>
        <body>
            <!-- HEADER -->
            <table cellpadding="10" class="header-bg" width="100%">
                <tr>
                    <td width="70%">
                        <div style="font-size: 16pt; font-weight: 900;">ÖĞRENCİ ÖZET RAPORU</div>
                        <div style="font-size: 8pt; margin-top: 2pt; opacity: 0.9;">YKS/LGS PERFORMANS VE İLERLEME ANALİZİ</div>
                    </td>
                    <td width="30%" align="right" valign="middle">
                        <div style="font-size: 9pt; font-weight: bold;">RAPOR TARİHİ</div>
                        <div style="font-size: 11pt; font-weight: bold;">{today_str}</div>
                    </td>
                </tr>
            </table>

            <div style="padding: 10pt;">
                
                <!-- STUDENT INFO -->
                <table cellpadding="6" width="100%" style="margin-bottom: 10pt; border: 1px solid #ccc; background-color: #fcfcfc;">
                    <tr>
                        <td width="60%">
                            <span style="font-size: 7pt; color: #666; font-weight: bold; text-transform:uppercase;">ÖĞRENCİ ADI SOYADI</span><br/>
                            <span style="font-size: 11pt; color: {c_blue}; font-weight: 800;">{name}</span>
                        </td>
                        <td width="40%" align="right">
                            <span style="font-size: 7pt; color: #666; font-weight: bold; text-transform:uppercase;">SINIF / DESTEK GRUBU</span><br/>
                            <span style="font-size: 10pt; color: #333; font-weight:600;">{sinif}</span>
                        </td>
                    </tr>
                </table>

                <!-- STATS CARDS -->
                <table cellspacing="8" cellpadding="0" style="margin-bottom: 10pt;" width="100%">
                    <tr>
                        <td class="stats-cell" width="25%">
                            <span class="stats-val">{total}</span>
                            <span class="stats-lbl">TOPLAM ÖDEV</span>
                        </td>
                        <td class="stats-cell" width="25%">
                            <span class="stats-val" style="color: {c_green};">{done}</span>
                            <span class="stats-lbl">TAMAMLANAN</span>
                        </td>
                        <td class="stats-cell" width="25%">
                            <span class="stats-val" style="color: {c_red};">{missing}</span>
                            <span class="stats-lbl">EKSİK / BEKLEYEN</span>
                        </td>
                        <td class="stats-cell" width="25%" style="background-color: {rate_bg}; border-color: {rate_c};">
                            <span class="stats-val" style="color: {rate_c};">%{rate}</span>
                            <span class="stats-lbl">{rate_txt}</span>
                        </td>
                    </tr>
                </table>
                
                <!-- NEW SECTION: ANALYSIS (3 Columns) -->
                <table style="margin-bottom: 10pt;" width="100%">
                   <tr>
                       <!-- COL 1: 30 DAYS -->
                       <td width="32%" valign="top" style="padding-right: 6pt;">
                            <div class="section-head">Son 30 Gün</div>
                            <table width="100%">
                                {rows_30_html}
                            </table>
                       </td>
                       <!-- COL 2: BOOKS & TRIALS -->
                       <td width="34%" valign="top" style="padding-right: 6pt; padding-left: 6pt;">
                            <div class="section-head">Kitap Takip</div>
                            <table width="100%" style="margin-bottom: 8pt;">
                                {rows_books_html}
                            </table>
                            
                            <!-- Embedded Trials -->
                            <div style="font-size: 8pt; font-weight: 800; color: {c_gray}; border-bottom: 1px solid #ccc; margin-bottom: 3pt;">SON DENEMELER</div>
                            <table width="100%">
                                {trials_html}
                            </table>
                       </td>
                       <!-- COL 3: TARGETS & SUBJECTS -->
                       <td width="34%" valign="top" style="padding-left: 6pt;">
                            <div class="section-head">Hedef & Konular</div>
                            
                            <!-- Weekly Target -->
                            <div class="card-box" style="margin-bottom: 8pt;">
                                <div style="font-size: 7pt; font-weight: bold; color: #555;">HAFTALIK SORU HEDEFİ</div>
                                <div style="display:flex; justify-content:space-between; margin-top:2pt;">
                                   <span style="font-size: 9pt; font-weight: 800; color: {c_blue};">{tg_s}</span>
                                   <span style="font-size: 7pt; color: #777; margin-top:2pt;">/ {tg_t}</span>
                                </div>
                                <table width="100%" height="4" cellspacing="0" cellpadding="0" style="margin-top: 3pt; background-color: #fff; border: 1px solid #ccc;">
                                    <tr><td width="{tg_width}%" style="background-color: {tg_color};"></td><td width="{100-tg_width}%"></td></tr>
                                </table>
                            </div>
                            
                            <!-- Subject Status -->
                            <table width="100%">
                                <tr>
                                    <td class="stats-cell" width="50%" style="padding: 4pt;">
                                        <span class="stats-val" style="font-size: 10pt; color: {c_green};">{sub_done}</span>
                                        <span class="stats-lbl" style="font-size: 5pt;">BİTEN KONU</span>
                                    </td>
                                    <td class="stats-cell" width="50%" style="padding: 4pt;">
                                        <span class="stats-val" style="font-size: 10pt; color: {c_amber};">{sub_work}</span>
                                        <span class="stats-lbl" style="font-size: 5pt;">ÇALIŞILAN</span>
                                    </td>
                                </tr>
                            </table>
                       </td>
                   </tr>
                </table>

                <!-- RECENT HOMEWORK -->
                <div class="section-head">Son Ödev Hareketleri (Son 20 Kayıt)</div>
                <table width="100%" style="font-size: 7pt;">
                    <thead>
                        <tr>
                            <th class="main-th" width="18%">Ders</th>
                            <th class="main-th" width="20%">Konu</th>
                            <th class="main-th" width="12%" style="text-align: center;">Başlangıç</th>
                            <th class="main-th" width="12%" style="text-align: center;">Bitiş</th>
                            <th class="main-th" width="12%">Durum</th>
                            <th class="main-th" width="26%">Açıklama</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_hw_html}
                    </tbody>
                </table>

                <!-- TEACHER NOTE -->
                <div style="margin-top: 15pt; border: 1px solid #999; padding: 10pt; height: 60pt;">
                    <table width="100%">
                        <tr>
                            <td align="left" style="font-weight: 800; color: #444; text-transform: uppercase; font-size: 8pt;">
                                ÖĞRETMEN NOTU
                            </td>
                            <td align="right" style="font-weight: 600; color: #444; font-size: 8pt;">
                                Tarih: .........................
                            </td>
                        </tr>
                    </table>
                    <div style="margin-top: 15pt; border-bottom: 1px dotted #ccc; height: 1px;"></div>
                    <div style="margin-top: 15pt; border-bottom: 1px dotted #ccc; height: 1px;"></div>
                </div>

                <div style="text-align: center; color: #999; font-size: 6pt; margin-top: 10pt;">
                    YKS/LGS Homework Manager &bull; Otomatik Performans Raporu
                </div>
            </div>
        </body>
        </html>
        """
        return html
