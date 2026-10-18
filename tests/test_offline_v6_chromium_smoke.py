"""Optional Chromium real-browser smoke test; synthetic/static app, no student DB.
Run from project root; requires Playwright Python and chromium executable.
"""
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit
import mimetypes
import threading
import tempfile
import pytest

ROOT=Path(__file__).resolve().parents[1]

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path=urlsplit(self.path).path
        if path=='/': file=ROOT/'web_api/templates/index.html'
        elif path=='/sw.js':file=ROOT/'web_api/static/sw.js'
        elif path.startswith('/static/'):
            file=(ROOT/'web_api'/path.lstrip('/')).resolve()
            if not file.is_relative_to((ROOT/'web_api/static').resolve()):
                self.send_error(403);return
        else:
            self.send_error(404);return
        if not file.exists():self.send_error(404);return
        t=mimetypes.guess_type(file)[0] or 'application/octet-stream'
        if file.suffix=='.js':t='application/javascript'
        self.send_response(200)
        self.send_header('Content-Type',t)
        self.send_header('Cache-Control','no-store')
        self.send_header('Content-Length',str(file.stat().st_size))
        self.end_headers()
        try:self.wfile.write(file.read_bytes())
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):pass
    def log_message(self,*_):pass


def test_chromium_smoke():
    pw = pytest.importorskip("playwright.sync_api", reason="İsteğe bağlı Playwright paketi kurulu değil.")
    if not Path('/usr/bin/chromium').exists():
        pytest.skip("/usr/bin/chromium mevcut değil.")
    sync_playwright = pw.sync_playwright
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    url=f'http://127.0.0.1:{server.server_port}/'
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox','--disable-dev-shm-usage'])
            with tempfile.TemporaryDirectory(prefix='yks_v6_browser_') as directory:
                context=browser.new_context(service_workers='allow')
                page=context.new_page()
                page.goto(url,wait_until='load',timeout=25000)
                page.wait_for_function("async () => { const r=await navigator.serviceWorker.getRegistration('/'); return !!r?.active; }",timeout=25000)
                page.wait_for_function("async () => {const c=await caches.open('yks-kocluk-shell-v6');return !!(await c.match('/static/js/offline_health_v6.js'));}",timeout=25000)
                online=page.evaluate("""async () => ({ready:!!(await caches.open('yks-kocluk-shell-v6')).match,
                            health:(await OfflineHealthV6.audit()).results.find(x=>x.code==='shell').ok,
                            version:(await OfflineHealthV6.audit()).results.find(x=>x.code==='worker').ok})""")
                assert online['health'] and online['version'],online
                context.set_offline(True)
                page.reload(wait_until='load',timeout=25000)
                assert page.locator('title').text_content()=='YKS-LGS Koçluk & Ödev Takip'
                offline=page.evaluate("""async () => {
                   const a=await OfflineHealthV6.audit();
                   return {shell:a.results.find(x=>x.code==='shell').ok,
                           worker:a.results.find(x=>x.code==='worker').ok,
                           snapshot:a.results.find(x=>x.code==='snapshot').ok};
                }""")
                assert offline['shell'] and offline['worker'] and not offline['snapshot'],offline
                print('PASS Chromium: V6 service worker install, full shell cache, genuine offline reload, no student snapshot => fail-closed')
                context.close()
            browser.close()
    finally:
        server.shutdown()


if __name__ == '__main__':
    test_chromium_smoke()
