#!/usr/bin/env python3
"""Локальный сервер симулятора ИВЛ T1 для работы по Wi-Fi без интернета.

Запуск:  python3 server.py          (порт 8080)
         python3 server.py 9000     (другой порт)
Нужен только Python 3.8+, без дополнительных библиотек.
"""
import json
import os
import queue
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

PORT = int(os.environ.get("PORT") or (sys.argv[1] if len(sys.argv) > 1 else 8080))
HERE = os.path.dirname(os.path.abspath(__file__))
rooms = {}
lock = threading.Lock()


def lan_ips():
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ips.add(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    try:
        for a in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(a[4][0])
    except Exception:
        pass
    return sorted(i for i in ips if not i.startswith("127.") and not i.startswith("169.254."))


def clean(name):
    name = "".join(c for c in (name or "").lower() if c.isalnum() or c == "-")[:20]
    return name or "default"


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def reply(self, code, body=b"", ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if body:
            self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/api/info":
            return self.reply(200, json.dumps({"ips": lan_ips(), "port": PORT}).encode())
        if u.path == "/api/events":
            room = clean(q.get("room", [""])[0])
            inbox = queue.Queue(maxsize=300)
            with lock:
                rooms.setdefault(room, set()).add(inbox)
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            try:
                self.wfile.write(b"retry: 2000\n\n")
                self.wfile.flush()
                while True:
                    try:
                        msg = inbox.get(timeout=15)
                        self.wfile.write(b"data: " + msg + b"\n\n")
                    except queue.Empty:
                        self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
            except Exception:
                pass
            finally:
                with lock:
                    rooms.get(room, set()).discard(inbox)
                self.close_connection = True
            return
        if u.path in ("/", "/index.html"):
            with open(os.path.join(HERE, "index.html"), "rb") as f:
                return self.reply(200, f.read(), "text/html; charset=utf-8")
        self.reply(404, b"not found", "text/plain")

    def do_POST(self):
        u = urlparse(self.path)
        if u.path != "/api/send":
            return self.reply(404)
        n = int(self.headers.get("Content-Length") or 0)
        if n > 16384:
            return self.reply(413)
        body = self.rfile.read(n)
        try:
            json.loads(body)
        except Exception:
            return self.reply(400)
        body = body.replace(b"\n", b" ").replace(b"\r", b" ")
        room = clean(parse_qs(u.query).get("room", [""])[0])
        with lock:
            targets = list(rooms.get(room, ()))
        for t in targets:
            try:
                t.put_nowait(body)
            except queue.Full:
                pass
        self.reply(204)


def main():
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    srv.daemon_threads = True
    print("\nСимулятор ИВЛ T1 — локальный сервер запущен.\n")
    print("Откройте на планшете и телефоне (та же Wi-Fi сеть):")
    for ip in lan_ips() or ["<IP этого компьютера>"]:
        print(f"   http://{ip}:{PORT}/")
    print(f"\nНа этом компьютере: http://localhost:{PORT}/")
    print("Остановить: Ctrl+C\n")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nОстановлено.")


if __name__ == "__main__":
    main()
