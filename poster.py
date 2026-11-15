"""Card Vault PC poster: runs the app on http://localhost:8766 and passes listing calls to Tradera.

Run:  python poster.py
Your Tradera keys and login are saved in tradera.json next to this file. Never share or commit it.
"""
import json, os, sys, uuid, webbrowser, urllib.request, urllib.error, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = os.path.join(HERE, 'tradera.json')
PORT = 8766
API = 'https://api.tradera.com/v4/'

cfg = json.load(open(CFG, encoding='utf8')) if os.path.exists(CFG) else {}
def save(): json.dump(cfg, open(CFG, 'w', encoding='utf8'), indent=1)

def login_url():
    cfg['skey'] = str(uuid.uuid4()); save()
    return 'https://api.tradera.com/token-login?' + urllib.parse.urlencode(
        {'appId': cfg['appId'], 'pkey': cfg['publicKey'], 'skey': cfg['skey']})

def tradera(method, path, body=None):
    h = {'X-App-Id': str(cfg['appId']), 'X-App-Key': cfg['appKey'], 'Content-Type': 'application/json'}
    if cfg.get('token'): h.update({'X-User-Id': str(cfg['userId']), 'X-User-Token': cfg['token']})
    req = urllib.request.Request(API + path, data=body, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=30) as r: return r.status, r.read()
    except urllib.error.HTTPError as e: return e.code, e.read()
    except OSError as e: return 502, json.dumps({'error': str(e)}).encode()

class H(BaseHTTPRequestHandler):
    def send(self, code, data, ctype='application/json'):
        self.send_response(code); self.send_header('Content-Type', ctype)
        self.send_header('Cache-Control', 'no-store'); self.end_headers(); self.wfile.write(data)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path in ('/', '/index.html'):
            return self.send(200, open(os.path.join(HERE, 'index.html'), 'rb').read(), 'text/html; charset=utf-8')
        if u.path == '/tradera-callback':  # Tradera sends the user back here after login
            q = urllib.parse.parse_qs(u.query)
            if 'token' in q:
                cfg.update(userId=int(q['userId'][0]), token=q['token'][0], exp=q.get('exp', [''])[0]); save()
                msg = 'Logged in to Tradera. Close this tab and go back to Card Vault.'
            else: msg = 'Tradera login did not finish. Start poster.py again.'
            return self.send(200, f'<h2 style="font-family:sans-serif">{msg}</h2>'.encode(), 'text/html; charset=utf-8')
        if u.path == '/api/status':
            return self.send(200, json.dumps({'loggedIn': bool(cfg.get('token')), 'exp': cfg.get('exp')}).encode())
        if u.path == '/api/login':
            self.send_response(302); self.send_header('Location', login_url()); self.end_headers(); return
        self.proxy('GET')

    def do_POST(self): self.proxy('POST')
    def do_DELETE(self): self.proxy('DELETE')

    def proxy(self, method):
        u = urllib.parse.urlparse(self.path)
        # The custom header forces a browser preflight, so other websites cannot call this proxy.
        if not u.path.startswith('/api/tradera/') or self.headers.get('X-Vault') != '1':
            return self.send(404, b'{}')
        n = int(self.headers.get('Content-Length') or 0)
        code, data = tradera(method, u.path[len('/api/tradera/'):] + (('?' + u.query) if u.query else ''),
                             self.rfile.read(n) if n else None)
        self.send(code, data or b'{}')

    def log_message(self, *a): pass

if __name__ == '__main__':
    if not cfg.get('appKey'):
        print('First time setup. Get these from https://api.tradera.com (your application page).')
        print(f'In the app settings, set Accept URL to  http://localhost:{PORT}/tradera-callback')
        print('and turn ON "Display token on return URL".\n')
        cfg['appId'] = int(input('App ID: ').strip())
        cfg['appKey'] = input('App key: ').strip()
        cfg['publicKey'] = input('Public key: ').strip()
        save()
    srv = ThreadingHTTPServer(('127.0.0.1', PORT), H)
    url = f'http://localhost:{PORT}/'
    print(f'Card Vault poster runs at {url}  (keep this window open, Ctrl+C to stop)')
    webbrowser.open(url if cfg.get('token') else f'{url}api/login')
    try: srv.serve_forever()
    except KeyboardInterrupt: sys.exit(0)
