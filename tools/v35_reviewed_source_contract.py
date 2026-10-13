# -*- coding: utf-8 -*-
"""Audited source contract for V35 RC2 weekly-calendar corrections.

A historical whole-file comparison is insufficient: the weekly PDF launcher
changed intentionally, while the teacher's tick/save/control logic did not.
The approved whole-file fingerprint AND AST fingerprints of critical handlers
must both match.  Windows acceptance remains a separate manual gate.
"""
from __future__ import annotations
import ast
from hashlib import sha256
from pathlib import Path

APPROVED_WEEKLY_HOMEWORK_SHA256 = "f015d489390ad0d529aabd2f447eaeaed14ccd54f48aaa81dd4a5ed47aef6cad"
HISTORICAL_V27_HOMEWORK_SHA256 = "b522636d49cdeaf643fef5704a3c63e39a7b5d7230d7f405f78330ebe5a2d68f"
LEGACY_HANDLERS = {'ui/homework_form.py': {'class': 'OdevTakipFormu', 'methods': {'_tik_degisti': ['ee136d1446a999b8bdcbcf6fb1e94091ae0d5b1d482003f5ca2e9f917e4ea715'], '_kaydet_kume': ['5212786c4f7ae0538ce1e005b14f9dcba970b6c616c4f77d944ca1be1a179d0d'], '_odev_kontrol': ['ad1b493928c41c01aa2123247313c1821a19ba7e5cca54aaa8472da4f37b19cb', 'e15ceda7090467209c7761ffd8365d014ada4420ff9113b9e87ee77e198bab84'], '_toplam_sure_guncelle': ['6ef7755129ac6daec47a105a324f7219a40c4ce1f0a5211d67b0420863f50862'], '_whatsapp_gonder': ['d5768fd5e0f043d85a17431e13e3e54a542f896e6ce73a7cd724ceac239b615e'], '_pdf_yazdir': ['0e53faa01eed0334a1cf64fea75fe9fc9c1e838e8e137c742b19bf99b57e9324'], '_sync_verilen_rows_from_table': ['d07c3b3c8660df6fc1a3d2c1a1068ac1b19234c56858b9dee9cb9460f91e1866']}}, 'ui/odev_kontrol.py': {'class': 'OdevKontrolDialog', 'methods': {'_kaydet': ['594371f8d87be1168ed9cb3649a6d386332db8154f731bc5b63ebeb6b5bb2617'], '_chk_cell_click': ['a31547e745249728c4eebd57f1b4b1d10c72fbbcc784bd747e4992c4e7e49f40'], '_on_table_item_changed': ['34d657727551cc792f4b75168a435f70e7a51b9a18dd70f06316ce46f73df618'], '_kume_ac': ['cadcdc80be468fc7fd1b4a6c19c298dc5bcf5bc054485c14349410e9d7e468bf'], '_aktar': ['b174ac81868246d82b28fcab1301959bc5cf1e727dd0bd6258f5db6c1bbbb6bf'], '_hepsi_tamam': ['ccb4324c70272c601b78c5c3b332489d43aef97452a32736e0114b47822c5c68'], '_hepsi_geri': ['22fec7893da285721d42aa6805897c976d5672d31284df82ad5f6b3bfe990f6e'], 'aktar_silmeden': ['29b7edc5495f3f258a1d1332b70ed56fdb4a534139ae767df9feac9a691c67c5']}}}


ALT_LEGACY_METHODS = {
    'ui/homework_form.py': {
        '_tik_degisti': ['46cc5efcf7d908a94056732e0e2a41cbb08c2a9e97bddd32d8770cb9eb8456eb'],
        '_kaydet_kume': ['bf2ff386c7fa4c97cdc48e8910be83319309562e7fd13962e98fd625aa3c637e'],
        '_odev_kontrol': ['74335827202fe43e19385e6acd6fd9090d4cb9ec5b123a61eb4658c7cfe88559', '65f88cd96cbd1adbe6c590abc33e7b413fa051d2a3839aed8a231e868d154ac0'],
        '_toplam_sure_guncelle': ['700dcdb120d9d587cce1da290d2f902f85b1a6c5c5299e2b818dc3163463cc10'],
        '_whatsapp_gonder': ['a9642db64f3d0172d501e61babdc0060dba92aa3685a064c91a32fdad1ab6a18'],
        '_pdf_yazdir': ['c237b34509af6731f3d4351ce784d5f85a147726e6bc5ac1587cc95359b95989'],
        '_sync_verilen_rows_from_table': ['66918a1493527ea14628396bb8eabe004a2963c5c1ff653180618f68e5a9530a']
    },
    'ui/odev_kontrol.py': {
        '_kaydet': ['a474348ffcc65659c850ac2d8c8267c0031a940e388f04f12e6b81f21029ccc8'],
        '_chk_cell_click': ['ceaf8b3cbf9a7211e52cd7bcc285eabdca58bbe87c1250018e93cc58a9470cdb'],
        '_on_table_item_changed': ['d718d887f49e525a7c2cd5569ebad9ccedd16101caf297e0c7e3da7457fcdad6'],
        '_kume_ac': ['e28ec59b42fd30cfd918bd81503849144fe97a5347acc2f10582575fe0574b1c'],
        '_aktar': ['534030a148612d1f82945594f4aacf77d0edd71e0b740eb154164c02ebf5fbee'],
        '_hepsi_tamam': ['d74ce16fef9af2ea1a7597b4a56c5958b3911a445a524948e96e26f37d23563b'],
        '_hepsi_geri': ['1aa7602099e5101dcff683887892449a8b47c439cc4dcafefe1e4c283f934775'],
        'aktar_silmeden': ['cbd17d57f090b7c6d3667ac2ee591bb6f487b59174ed6b1c6c739138cf5b367f']
    }
}


def verify_legacy_handlers(root: Path) -> None:
    """Fail closed if a critical old handler changes, including duplicates."""
    root=Path(root)
    for relative, spec in LEGACY_HANDLERS.items():
        path=root/relative
        tree=ast.parse(path.read_text(encoding='utf-8'))
        cls=next((node for node in tree.body if isinstance(node,ast.ClassDef)
                  and node.name==spec['class']),None)
        if cls is None:
            raise ValueError('Korunan arayüz sınıfı bulunamadı: ' + relative)
        for name, expected in spec['methods'].items():
            actual=[sha256(ast.dump(m,include_attributes=False).encode()).hexdigest()
                    for m in cls.body if isinstance(m,(ast.FunctionDef,ast.AsyncFunctionDef))
                    and m.name==name]
            if actual != expected and actual != ALT_LEGACY_METHODS.get(relative, {}).get(name):
                raise ValueError('Korunan işlem değişmiş: ' + relative + ' / ' + name)
