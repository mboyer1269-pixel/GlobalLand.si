"""Serve the read-only city locally; no production account access or mutation."""
import argparse
import json
import subprocess
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import city_projection

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
STATIC = {'/': ('index.html', 'text/html'), '/index.html': ('index.html', 'text/html'),
          '/ville.css': ('ville.css', 'text/css'), '/ville.js': ('ville.js', 'text/javascript'),
          '/ville-crepuscule.png': ('ville-crepuscule.png', 'image/png')}


def current_revision():
    return city_projection.git(REPO, 'rev-parse', 'refs/remotes/origin/main').decode().strip()


def snapshot(revision=None):
    return city_projection.snapshot(REPO, revision)


class SnapshotReader:
    def __init__(self, fetch_remote):
        self.fetch_remote = fetch_remote
        self.lock = threading.Lock()
        self.last_attempt = float('-inf')
        self.data = None

    def read(self):
        with self.lock:
            now = time.monotonic()
            if now - self.last_attempt < 55:
                return self.data
            self.last_attempt = now
            stale = False
            if self.fetch_remote:
                try:
                    city_projection.git(REPO, 'fetch', '--no-tags', '--no-recurse-submodules',
                                        'origin', 'main', timeout=18)
                except (RuntimeError, subprocess.TimeoutExpired):
                    stale = True
            try:
                revision = current_revision()
                data = self.data if self.data and self.data['revision'] == revision else snapshot(revision)
            except (RuntimeError, subprocess.TimeoutExpired, ValueError, KeyError, TypeError, AttributeError):
                if not self.data:
                    return None
                data = self.data
                stale = True
            self.data = {**data, 'stale': stale, 'sourceMode': 'remote' if self.fetch_remote else 'cached',
                         'checkedAt': datetime.now(timezone.utc).isoformat()}
            return self.data


def handler_for(reader):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.headers.get('Host') != f'127.0.0.1:{self.server.server_port}':
                self.send_error(403)
                return
            if self.path == '/snapshot.json':
                data = reader.read()
                if data is None:
                    self.send_error(503, 'Instantane indisponible')
                    return
                body, mime = json.dumps(data, ensure_ascii=False).encode(), 'application/json'
            elif self.path in STATIC:
                name, mime = STATIC[self.path]
                body = (HERE / name).read_bytes()
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', mime if mime == 'image/png' else f'{mime}; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store' if self.path == '/snapshot.json' else 'no-cache')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(body)
    return Handler


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--repo', type=Path, default=REPO, help='Copie Git publique à lire.')
    parser.add_argument('--cached', action='store_true', help='Ne pas actualiser origin/main depuis GitHub.')
    parser.add_argument('--snapshot', action='store_true', help='Imprimer la projection et quitter.')
    parser.add_argument('--revision', help='SHA figé, uniquement avec --snapshot.')
    options = parser.parse_args()
    if options.revision and not options.snapshot:
        parser.error('--revision requires --snapshot')
    REPO = options.repo.resolve()
    if options.snapshot:
        print(json.dumps(snapshot(options.revision), ensure_ascii=True))
    else:
        server = ThreadingHTTPServer(('127.0.0.1', options.port), handler_for(SnapshotReader(not options.cached)))
        print(f'Ville de GlobalLand : http://127.0.0.1:{server.server_port}/', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
