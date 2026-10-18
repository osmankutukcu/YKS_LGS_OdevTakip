# -*- coding: utf-8 -*-
"""V25.7 one-recipient WhatsApp link test; NEVER processes student data or queue."""
from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

RELEASE = '7.0.0-rc14'

def bridge_dir():
    base = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[2]))
    return base / 'services' / 'whatsapp_queue' / 'baileys_node_v257'

def prerequisites(node=None, folder=None):
    if sys.platform != 'win32':
        return False, 'V25.7 pilotu Windows içindir; mevcut Mac WhatsApp yöntemleri değişmez.'
    folder = Path(folder) if folder else bridge_dir()
    node = node or shutil.which('node')
    if not node:
        return False, 'Node.js 20+ bulunamadı. Resmî nodejs.org üzerinden kurup uygulamayı yeniden açın.'
    try:
        p = subprocess.run([node, '--version'], capture_output=True, text=True, timeout=5)
        version = int(p.stdout.strip().lstrip('v').split('.')[0])
        if p.returncode != 0 or version < 20:
            return False, 'Node.js 20+ sürümü gerekiyor.'
    except (ValueError, OSError, subprocess.SubprocessError, IndexError):
        return False, 'Node.js sürümü doğrulanamadı.'
    if not (folder/'bridge.mjs').is_file() or not (folder/'package.json').is_file():
        return False, 'Baileys test dosyaları eksik; ZIP tam kurulmalı.'
    try:
        pkg=json.loads((folder/'package.json').read_text(encoding='utf8'))
        if pkg['dependencies']['@whiskeysockets/baileys'] != RELEASE:
            return False, 'Baileys sürümü doğrulanamadı.'
        lock=json.loads((folder/'package-lock.json').read_text(encoding='utf8'))
        direct=lock['packages']['node_modules/@whiskeysockets/baileys']
        if direct.get('version') != RELEASE or not direct.get('integrity','').startswith('sha512-'):
            return False, 'Bağımlılık kilidi güvenlik kontrolünden geçmedi.'
    except (OSError,KeyError,TypeError,ValueError):
        return False, 'Baileys henüz kurulmamış. Windows_Hazirla_V257.cmd dosyasını çalıştırın.'
    if not (folder/'node_modules'/'@whiskeysockets'/'baileys').is_dir():
        return False, 'Baileys bağımlılıkları henüz kurulmamış. Windows_Hazirla_V257.cmd çalıştırın.'
    return True, 'Test bağlantısı hazır; hesap eşleştirmesi henüz yapılmadı.'
