"""V13.5: minimal, read-only integrity report opened explicitly by teacher."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from html import escape as _html_escape
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QPlainTextEdit, QTextEdit, QMessageBox,
)

from services.homework_integrity_v135 import AuditResult, audit_database, audit_draft_matrix


def snapshot_form(form) -> tuple[list[dict], list[dict]]:
    cells = []
    for lesson, table in (getattr(form, "_ders_tablolari", {}) or {}).items():
        for row in range(table.rowCount()):
            topic = table.item(row, 0)
            if topic is None:
                continue
            for col in range(1, table.columnCount()):
                book = table.horizontalHeaderItem(col)
                cell = table.item(row, col)
                if book is None or cell is None:
                    continue
                cells.append({
                    "ders": lesson, "kitap": book.text(), "konu": topic.text(),
                    "checked": cell.checkState() == Qt.CheckState.Checked,
                    "locked": not bool(cell.flags() & Qt.ItemFlag.ItemIsUserCheckable),
                })
    tasks = []
    table = getattr(form, "verilen", None)
    if table is not None:
        # Read source rows; do not filter by current visual sort, search or selection.
        for row in range(table.rowCount()):
            texts = []
            for col in range(3):
                item = table.item(row, col)
                texts.append(item.text() if item is not None else "")
            if any(texts):
                tasks.append(dict(zip(("ders", "kitap", "konu"), texts)))
    return cells, tasks


def open_readonly_database(path: Path) -> sqlite3.Connection:
    path = Path(path).expanduser().resolve(strict=True)
    # SQLite's read-only URI, without immutable=1 (which would ignore WAL updates).
    con = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=5)
    con.execute("PRAGMA query_only=ON")
    return con


def summarize(result: AuditResult, title: str) -> str:
    lines = [title, "=" * len(title)]
    for item in result.findings:
        lines.append(f"[{item.severity.upper()}] {item.message}  |  Adet: {item.count}")
        if item.references:
            lines.append("  Örnek kayıt/hücre: " + "; ".join(item.references))
        if item.guidance:
            lines.append("  Öneri: " + item.guidance)
    if not result.findings:
        lines.append("Kontrol edilen veri alanlarında sorun bulunmadı.")
    if result.notes:
        lines.append("\nSınırlar ve açıklamalar:")
        lines.extend("- " + note for note in result.notes)
    return "\n".join(lines)


def _humanize_finding(item) -> tuple[str, str, str, str, str]:
    """Return (badge_html, friendly_title, why_it_happens, teacher_action, ref_text)."""
    msg = str(getattr(item, "message", "") or "")
    sev = str(getattr(item, "severity", "info") or "info").lower()
    cnt = int(getattr(item, "count", 0) or 0)
    refs = "; ".join(getattr(item, "references", ()) or ())
    guidance = str(getattr(item, "guidance", "") or "")

    # A broken student/group link is never dismissed merely because it appears
    # in an old table. This dialog cannot prove that active work is unaffected.
    if sev in ('critical', 'high'):
        badge = (f'<span style="background-color:#ffe4e6;color:#9f1239;font-weight:800;'
                 f'padding:3px 7px;font-size:11px;">🔴 Bağlantıyı İncele ({cnt} kayıt)</span>')
        title = f'<b>{_html_escape(msg)}</b>'
        why = ('Ödev, öğrenci veya küme bağlantısı beklenen kuralları karşılamıyor. '
               'Etki alanı yalnızca bu raporla kesinleştirilemez.')
        act = _html_escape(guidance or 'İlgili kayıtları ve yedeği karşılaştırın; otomatik değiştirmeyin.')
    elif sev == 'medium':
        badge = (f'<span style="background-color:#fef3c7;color:#92400e;font-weight:800;'
                 f'padding:3px 7px;font-size:11px;">⚠️ Taslağı İncele ({cnt} kayıt)</span>')
        title = f'<b>{_html_escape(msg)}</b>'
        why = 'Düzenlenebilir ödev taslağı ile seçili ekrandaki diğer bilgiler uyuşmayabilir.'
        act = _html_escape(guidance or 'Kaydetmeden önce seçimi gözden geçirin.')
    else:
        badge = (f'<span style="background-color:#e0f2fe;color:#0369a1;font-weight:800;'
                 f'padding:3px 7px;font-size:11px;">ℹ️ Bilgi ({cnt} kayıt)</span>')
        title = f'<b>{_html_escape(msg)}</b>'
        why = 'Bu kontrolün kapsamında bilgi amaçlı bulgu.'
        act = _html_escape(guidance or 'Gerekiyorsa ilgili kayıtları gözden geçirin.')
    return badge, title, why, act, refs


class IntegrityDialog(QDialog):
    def __init__(self, form, db_path: Path, parent=None):
        super().__init__(parent or form)
        self.setWindowTitle("🔎 Ödev Veri Denetimi ve Güvenlik Raporu — V13.5")
        self.resize(940, 700)
        self.setStyleSheet("""
            QDialog { background: #f8fafc; color: #0f172a; }
            QPushButton {
                background: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px;
                padding: 8px 16px; font-weight: 700; color: #1e293b;
            }
            QPushButton:hover { background: #eff6ff; border-color: #93c5fd;  color: #15191E;}
        """)
        self._plain_report = ""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        top_bar = QHBoxLayout()
        head = QLabel("🔎 Ödev Veri Denetimi ve Güvenlik Raporu — V13.5")
        head.setStyleSheet("font-weight:800; font-size:18px; color:#0f172a;")
        badge = QLabel("🛡️ Salt Okunur Denetim (Verileri Değiştirmez)")
        badge.setStyleSheet(
            "background:#e0f2fe; color:#0369a1; border:1px solid #bae6fd; "
            "font-weight:700; font-size:11.5px; padding:5px 12px; border-radius:8px;"
        )
        top_bar.addWidget(head)
        top_bar.addStretch(1)
        top_bar.addWidget(badge)
        layout.addLayout(top_bar)

        note = QLabel("Salt okunur: Tikler, ödevler, öğrenci kayıtları ve veritabanı değiştirilmez.")
        note.setWordWrap(True)
        note.setStyleSheet("color:#475569; font-size:12px;")
        layout.addWidget(note)

        self.content = QTextEdit(self)
        self.content.setReadOnly(True)
        self.content.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.content.setStyleSheet(
            "QTextEdit { background:#ffffff; border:1px solid #cbd5e1; border-radius:10px; padding:10px;  color: #15191E;}"
        )
        layout.addWidget(self.content, 1)

        row = QHBoxLayout()
        rerun = QPushButton("🔄 Yeniden Denetle")
        rerun.clicked.connect(lambda: self._run(form, db_path))
        copy = QPushButton("📋 Raporu Kopyala")
        copy.setStyleSheet(
            "QPushButton { background:#2563eb; color:#ffffff; border:none; border-radius:8px; padding:8px 18px; font-weight:700; }"
            "QPushButton:hover { background:#1d4ed8; }"
        )
        copy.clicked.connect(lambda: QApplication.clipboard().setText(self._plain_report or self.content.toPlainText()))
        close = QPushButton("Kapat")
        close.clicked.connect(self.accept)
        row.addWidget(rerun)
        row.addWidget(copy)
        row.addStretch(1)
        row.addWidget(close)
        layout.addLayout(row)
        self._run(form, db_path)

    def _run(self, form, db_path):
        # Database scan intentionally independent from student selection.
        parts = []
        db_res = None
        db_err = None
        draft_res = None
        draft_err = None
        selected = None
        cells_count = 0
        tasks_count = 0

        try:
            with open_readonly_database(db_path) as con:
                db_res = audit_database(con)
                parts.append(summarize(db_res, "VERİTABANI BAĞLANTILARI"))
        except Exception as exc:
            db_err = str(exc)
            parts.append("VERİTABANI: Salt okunur açma / kontrol başarısız: " + str(exc))
        try:
            selected = form._secili_ogrenci_id()
            loaded = getattr(form, "_loaded_student_id", None)
            cells, tasks = snapshot_form(form)
            cells_count = len(cells)
            tasks_count = len(tasks)
            draft_res = audit_draft_matrix(cells, tasks,
                                           selected_student=selected, loaded_student=loaded)
            parts.append(summarize(draft_res, "SEÇİLİ ÖĞRENCİNİN KAYDEDİLMEMİŞ TASLAĞI"))
        except Exception as exc:
            draft_err = str(exc)
            parts.append("TASLAK: Ekran görüntüsü kontrol edilemedi: " + str(exc))
        parts.append("ÖNEMLİ: Bu sonuçlar otomatik düzeltme talimatı değildir. "
                     "Kayıtlı sarı/yeşil hücreler ile tarihsel ödevler ayrı korunur.")
        self._plain_report = "\n\n".join(parts)

        # Build teacher-friendly visual HTML report
        draft_findings = list(draft_res.findings) if draft_res is not None else []
        db_findings = list(db_res.findings) if db_res is not None else []

        if draft_err:
            c1_bg, c1_brd, c1_fg = "#fff1f2", "#fecdd3", "#9f1239"
            c1_title = "⚠️ Ekran Taslağı Kontrol Edilemedi"
            c1_body = _html_escape(draft_err)
        elif not draft_findings:
            c1_bg, c1_brd, c1_fg = "#f0fdf4", "#86efac", "#166534"
            c1_title = "✅ Kontrol Edilen Taslak Alanlarında Bulgu Yok"
            st_lbl = f"Öğrenci #{selected}" if selected else "Seçili öğrenci yok"
            c1_body = (
                f"• <b>Seçili Öğrenci:</b> {_html_escape(st_lbl)}<br>"
                f"• <b>İncelenen Hücre / Satır:</b> {cells_count} hücre, {tasks_count} verilen ödev satırı<br>"
                f"• <b>Tespit Edilen Sorun:</b> 0<br>"
                f"• <b>Anlamı:</b> Yalnız bu denetimin kapsadığı taslak eşleşmelerinde uyarı yok. Kaydetme ve diğer kontroller ayrıca gereklidir."
            )
        else:
            c1_bg, c1_brd, c1_fg = "#fffbeb", "#fcd34d", "#92400e"
            c1_title = f"⚠️ Açık Ekranda {len(draft_findings)} Uyarı Bulundu"
            c1_body = (
                f"• <b>Seçili Öğrenci ID:</b> {selected or '—'}<br>"
                f"• <b>Bulgular:</b> Aşağıdaki rehber tablosunda açıklanmıştır.<br>"
                f"• <b>Öneri:</b> Kaydetmeden önce aşağıdaki açıklamayı kontrol edin."
            )

        if db_err:
            c2_bg, c2_brd, c2_fg = "#fff1f2", "#fecdd3", "#9f1239"
            c2_title = "⚠️ Veritabanı Okunamadı"
            c2_body = _html_escape(db_err)
        elif not db_findings:
            c2_bg, c2_brd, c2_fg = "#f0fdf4", "#86efac", "#166534"
            c2_title = "✅ Kontrol Edilen Veritabanı Bağlantılarında Bulgu Yok"
            c2_body = (
                "• <b>Durum:</b> Denetlenen ödev–küme–öğrenci bağlantılarında bulgu yok; genel sistem sağlığı sınanmadı.<br>"
                "• <b>Tespit Edilen Sorun:</b> 0<br>"
                "• <b>Öğretmen Ne Yapmalı?</b> Bu kapsamda uyarı yok; mevcut kayıt akışını normal şekilde kullanabilirsiniz."
            )
        else:
            total_orphan = sum(int(getattr(f, "count", 0) or 0) for f in db_findings)
            c2_bg, c2_brd, c2_fg = "#fffbeb", "#fcd34d", "#92400e"
            c2_title = f"⚠️ {total_orphan} Kayıt Bağlantısında İnceleme Gerekiyor"
            c2_body = (
                f"• <b>Tespit:</b> Ödev/küme/öğrenci bağlantıları için <b>{total_orphan} bulgu</b> var; hepsi eski ve etkisiz kabul edilmemelidir.<br>"
                f"• <b>Aktif Öğrenciyi Etkiler mi?</b> Bu rapordan kesin belirlenemez; kayıt aidiyetleri incelenmelidir.<br>"
                f"• <b>Öğretmen Ne Yapmalı?</b> Önce kayıtları ve yedekleri karşılaştırın; otomatik düzeltme yapmayın."
            )

        rows_html = []
        for f_item in (draft_findings + db_findings):
            badge_h, title_h, why_h, act_h, refs_h = _humanize_finding(f_item)
            ref_sub = f'<br><span style="color:#64748b;font-size:10px;">Örnek ID: {_html_escape(refs_h)}</span>' if refs_h else ''
            rows_html.append(f'''
            <tr>
              <td valign="top">{badge_h}</td>
              <td valign="top" style="font-size:11.5px;">{title_h}{ref_sub}</td>
              <td valign="top" style="font-size:11.5px;color:#334155;">{why_h}</td>
              <td valign="top" style="font-size:11.5px;">{act_h}</td>
            </tr>
            ''')

        if not draft_findings and not draft_err:
            rows_html.append(f'''
            <tr bgcolor="#f8fafc">
              <td valign="top"><span style="background-color:#dcfce7;color:#166534;font-weight:800;padding:3px 7px;font-size:11px;">✅ Canlı Taslak (0 Sorun)</span></td>
              <td valign="top" style="font-size:11.5px;"><b>Açık Ödev Tablosu Kontrolü</b><br><span style="color:#64748b;font-size:10.5px;">({cells_count} hücre / {tasks_count} satır denetlendi)</span></td>
              <td valign="top" style="font-size:11.5px;color:#334155;">Mükerrer konu, öğrenci uyuşmazlığı veya bozuk tik olup olmadığı kontrol edildi.</td>
              <td valign="top" style="font-size:11.5px;color:#166534;"><b>Bu kapsamda uyarı yok; mevcut kayıt akışını normal şekilde kullanabilirsiniz.</b></td>
            </tr>
            ''')

        html = f'''
        <div style="font-family:'Helvetica Neue',Arial,sans-serif;color:#0f172a;font-size:12px;">
          <table width="100%" cellspacing="0" cellpadding="10" style="border:1px solid #bfdbfe;margin-bottom:10px;">
            <tr>
              <td bgcolor="#eff6ff">
                <div style="font-size:12.5px;font-weight:800;color:#1e3a8a;">📖 BU EKRAN NE İŞE YARAR VE NASIL OKUNMALIDIR?</div>
                <div style="font-size:11.5px;color:#1e40af;margin-top:3px;line-height:1.45;">
                  Bu ekran, <b>1) Şu an açık olan öğrencinin ödev ekranında</b> ve <b>2) Genel veritabanı arşivinde</b> kopuk veya eksik bir kayıt olup olmadığını kontrol eder. Denetim tamamen güvenlidir; hiçbir ödevi silmez veya değiştirmez.
                </div>
              </td>
            </tr>
          </table>

          <table width="100%" cellspacing="8" cellpadding="11" style="margin-bottom:10px;">
            <tr>
              <td width="50%" bgcolor="{c1_bg}" valign="top" style="border:2px solid {c1_brd};">
                <div style="font-size:10.5px;font-weight:800;color:{c1_fg};">1. AKTİF ÖĞRENCİ EKRANI (CANLI TASLAK)</div>
                <div style="font-size:15px;font-weight:800;color:#0f172a;margin-top:3px;">{c1_title}</div>
                <div style="font-size:11.5px;color:{c1_fg};margin-top:5px;line-height:1.45;">{c1_body}</div>
              </td>
              <td width="50%" bgcolor="{c2_bg}" valign="top" style="border:2px solid {c2_brd};">
                <div style="font-size:10.5px;font-weight:800;color:{c2_fg};">2. VERİTABANI GENEL ARŞİVİ (GEÇMİŞ KAYITLAR)</div>
                <div style="font-size:15px;font-weight:800;color:#0f172a;margin-top:3px;">{c2_title}</div>
                <div style="font-size:11.5px;color:{c2_fg};margin-top:5px;line-height:1.45;">{c2_body}</div>
              </td>
            </tr>
          </table>

          <div style="font-size:12.5px;font-weight:800;color:#1e293b;margin-bottom:5px;">
            🔍 TESPİT EDİLEN BULGULARIN AÇIKLAMASI (Kullanıcı Rehberi)
          </div>
          <table width="100%" cellspacing="0" cellpadding="8" style="border:1px solid #cbd5e1;margin-bottom:10px;">
            <tr bgcolor="#f1f5f9" style="font-weight:800;color:#334155;font-size:11px;">
              <td width="18%">Önem Derecesi</td>
              <td width="28%">Ne Bulundu? (Sade Açıklama)</td>
              <td width="27%">Neden Oluşur?</td>
              <td width="27%">Ne Yapmalısınız?</td>
            </tr>
            {''.join(rows_html)}
          </table>

          <table width="100%" cellspacing="0" cellpadding="8" style="border:1px solid #e2e8f0;">
            <tr>
              <td bgcolor="#f8fafc" style="font-size:10.5px;color:#64748b;white-space:pre-wrap;"><b>🛠️ Teknik Destek Özeti:</b>\n{_html_escape(self._plain_report)}</td>
            </tr>
          </table>
        </div>
        '''
        self.content.setHtml(html)

