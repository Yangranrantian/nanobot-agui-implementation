from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class AguiHandler(SimpleHTTPRequestHandler):
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        '.js': 'text/javascript; charset=utf-8',
        '.mjs': 'text/javascript; charset=utf-8',
        '.css': 'text/css; charset=utf-8',
        '.json': 'application/json; charset=utf-8',
    }

    def end_headers(self) -> None:
        # Avoid stale local cache/service-worker artifacts when iterating quickly.
        self.send_header('Cache-Control', 'no-store, max-age=0')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()


def main() -> None:
    parser = argparse.ArgumentParser(description='Serve AGUI static files with browser-safe MIME types.')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=4173)
    args = parser.parse_args()

    directory = Path(__file__).resolve().parent
    handler = partial(AguiHandler, directory=str(directory))
    with ThreadingHTTPServer((args.host, args.port), handler) as server:
        print(f'AGUI web listening on http://{args.host}:{args.port}')
        server.serve_forever()


if __name__ == '__main__':
    main()
