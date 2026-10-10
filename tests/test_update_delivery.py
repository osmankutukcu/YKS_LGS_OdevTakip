"""Updater integration without Windows/PyQt/network; no real installer execution."""
import hashlib
import io
import json
import sqlite3
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

# CI executes tests before dependencies; mock only PyQt signal mechanics.
if 'PyQt6' not in sys.modules:
    try:
        import PyQt6
    except ImportError:
        pyqt=types.ModuleType('PyQt6');qtcore=types.ModuleType('PyQt6.QtCore')
        class Signal:
            def __init__(self):self.calls=[]
            def emit(self,*args):self.calls.append(args)
        class Thread:
            def __init__(self,parent=None):pass
        qtcore.QThread=Thread
        qtcore.pyqtSignal=lambda *_a: Signal()
        pyqt.QtCore=qtcore
        sys.modules['PyQt6']=pyqt
        sys.modules['PyQt6.QtCore']=qtcore

from utils import updater
from utils.update_core import INSTALLER_NAME, CHECKSUM_NAME, checksum_of_file

REPO='osmankutukcu/YKS_LGS_OdevTakip'
BASE=f'https://github.com/{REPO}/releases/download/v3.5.2/'
FAKE_EXE=b'MZ' + b'fake_inno_setup_bytes' * 40
SHA=hashlib.sha256(FAKE_EXE).hexdigest()


class DummyResponse(io.BytesIO):
    def __init__(self,data,url): super().__init__(data);self.url=url
    def geturl(self):return self.url


class DeliveryTests(unittest.TestCase):
    def release(self, data=None):
        assets=[{'name':INSTALLER_NAME,'browser_download_url':BASE+INSTALLER_NAME,
                 'size':len(FAKE_EXE),'digest':None},
                {'name':CHECKSUM_NAME,'browser_download_url':BASE+CHECKSUM_NAME}]
        return {'tag_name':'v3.5.2','assets':assets,'body':'Feature update'}

    def test_api_check_and_asset_selection(self):
        payload=json.dumps(self.release()).encode()
        with patch.object(updater,'_urlopen_https',return_value=DummyResponse(payload,'https://api.github.com/repos/x/releases/latest')):
            result=updater.check_for_updates(REPO,'3.5.0')
        self.assertTrue(result['installable'])
        self.assertTrue(result['download_url'].endswith(INSTALLER_NAME))
        self.assertEqual(BASE+CHECKSUM_NAME,result['checksum_url'])

    def test_api_network_error_not_uptodate(self):
        with patch.object(updater,'_urlopen_https',side_effect=OSError('No internet')):
            result=updater.check_for_updates(REPO,'3.5.0')
        self.assertFalse(result['has_update'])
        self.assertIn('No internet',result['error'])

    def test_downloader_valid(self):
        info=updater.check_for_updates(REPO,'3.5.0') if False else {
            'download_url': BASE+INSTALLER_NAME,'checksum_url':BASE+CHECKSUM_NAME,
            'sha256':'','file_size':len(FAKE_EXE),'installable':True}
        def respond(url,**kw):
            if url.endswith('.sha256'):
                return DummyResponse((SHA+'  '+INSTALLER_NAME+'\n').encode(),BASE+CHECKSUM_NAME)
            return DummyResponse(FAKE_EXE,BASE+INSTALLER_NAME)
        with tempfile.TemporaryDirectory() as tmp, patch.object(updater,'_urlopen_https',side_effect=respond):
            task=updater.UpdateDownloaderThread(info,tmp)
            task.run()
            self.assertEqual(SHA,task.verified_digest)
            self.assertEqual(FAKE_EXE,(Path(tmp)/INSTALLER_NAME).read_bytes())

    def test_downloader_wrong_checksum(self):
        info={'download_url':BASE+INSTALLER_NAME,'sha256':'0'*64,'checksum_url':'',
              'file_size':len(FAKE_EXE),'installable':True}
        with tempfile.TemporaryDirectory() as tmp, patch.object(updater,'_urlopen_https',return_value=DummyResponse(FAKE_EXE,BASE+INSTALLER_NAME)):
            task=updater.UpdateDownloaderThread(info,tmp)
            task.run()
            self.assertIsNone(task.verified_digest)
            self.assertFalse((Path(tmp)/INSTALLER_NAME).exists())

    def test_safe_windows_handoff_and_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/INSTALLER_NAME;p.write_bytes(FAKE_EXE)
            source=Path(tmp)/'student.db'
            with sqlite3.connect(str(source)) as db:
                db.execute('CREATE TABLE student(id int)');db.execute('INSERT INTO student VALUES(1)')
            fake_db=types.SimpleNamespace(DB_PATH=str(source))
            fake_qtwidgets=types.ModuleType('PyQt6.QtWidgets')
            fake_qtwidgets.QApplication=type('App',(),{'instance':staticmethod(lambda:None)})
            with patch.object(updater.sys,'platform','win32'),patch.object(updater.sys,'frozen',True,create=True),\
                 patch.dict(sys.modules,{'db':fake_db,'PyQt6.QtWidgets':fake_qtwidgets}),\
                 patch.object(updater,'user_update_directory',return_value=Path(tmp)),\
                 patch('utils.update_core.user_update_directory',return_value=Path(tmp)),\
                 patch.object(updater.subprocess,'Popen') as launch:
                self.assertTrue(updater.apply_update_and_restart(str(p),SHA,len(FAKE_EXE)))
                args = launch.call_args.args[0]
                self.assertEqual(Path(args[0]).name, INSTALLER_NAME)
                self.assertNotIn('python.exe', ' '.join(args))
                self.assertIn('/NORESTART', args)
                self.assertIn('/CLOSEAPPLICATIONS', args)
                saved=list(Path(tmp).rglob('backups/*/student.db'))
                self.assertEqual(1,len(saved))
                with sqlite3.connect(saved[0]) as db:
                    self.assertEqual(1,db.execute('SELECT count(*) FROM student').fetchone()[0])

    def test_prelaunch_bad_hash_prevents_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/INSTALLER_NAME;p.write_bytes(FAKE_EXE)
            with patch.object(updater.sys,'platform','win32'),patch.object(updater.sys,'frozen',True,create=True),\
                 patch.object(updater.subprocess,'Popen') as launch:
                with self.assertRaises(ValueError):
                    updater.apply_update_and_restart(str(p),'0'*64,len(FAKE_EXE))
                launch.assert_not_called()

if __name__=='__main__':unittest.main()
