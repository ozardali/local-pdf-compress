#!/usr/bin/env python3
"""Local web page to make PDFs smaller. Files stay on this computer."""

from __future__ import annotations

import json
import re
import tempfile
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from compress import PRESETS, compress_pdf, find_gs

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "web" / "index.html"
JOBS = Path(tempfile.gettempdir()) / "local-pdf-compress-jobs"
HOST = "127.0.0.1"
PORT = 8765


def _safe_filename(name: str) -> str:
    name = Path(name).name
    name = re.sub(r"[^\w.\- ]+", "_", name, flags=re.UNICODE).strip()
    if not name.lower().endswith(".pdf"):
        name = f"{name or 'document'}.pdf"
    return name[:180]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def _send(self, code: int, body: bytes, content_type: str, extra=None):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if extra:
            for k, v in extra.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, payload: dict):
        self._send(code, json.dumps(payload).encode("utf-8"), "application/json")

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            self._send(200, INDEX.read_bytes(), "text/html; charset=utf-8")
            return
        if parsed.path == "/health":
            try:
                find_gs()
                ok = True
                msg = "Ghostscript is ready to use"
            except FileNotFoundError as e:
                ok = False
                msg = str(e)
            self._json(200 if ok else 503, {"ok": ok, "message": msg, "presets": PRESETS})
            return
        if parsed.path.startswith("/download/"):
            job_id = parsed.path.split("/")[-1]
            if not re.fullmatch(r"[0-9a-f]{32}", job_id or ""):
                self._json(400, {"error": "This download link is not valid"})
                return
            pdf = JOBS / job_id / "out.pdf"
            name = "compressed.pdf"
            meta = JOBS / job_id / "name.txt"
            if meta.exists():
                name = _safe_filename(meta.read_text(encoding="utf-8").strip() or name)
            if not pdf.exists():
                self._json(404, {"error": "The file was not found"})
                return
            data = pdf.read_bytes()
            self._send(
                200,
                data,
                "application/pdf",
                {
                    "Content-Disposition": f'attachment; filename="{name}"',
                },
            )
            return
        self._json(404, {"error": "Page not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/compress":
            self._json(404, {"error": "Page not found"})
            return

        qs = parse_qs(parsed.query)
        quality = (qs.get("quality") or ["medium"])[0]
        filename = unquote((qs.get("filename") or ["document.pdf"])[0])
        filename = _safe_filename(filename)

        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            self._json(400, {"error": "The file is empty"})
            return
        if length > 200 * 1024 * 1024:
            self._json(413, {"error": "This file is larger than 200 MB"})
            return

        raw = self.rfile.read(length)
        if not raw.startswith(b"%PDF"):
            self._json(400, {"error": "This is not a valid PDF"})
            return

        job_id = uuid.uuid4().hex
        folder = JOBS / job_id
        folder.mkdir(parents=True, exist_ok=True)
        src = folder / "in.pdf"
        dest = folder / "out.pdf"
        src.write_bytes(raw)

        try:
            info = compress_pdf(src, dest, quality)
        except Exception as e:
            self._json(500, {"error": str(e)})
            return

        stem = Path(filename).stem
        out_name = f"{stem}-compressed.pdf"
        (folder / "name.txt").write_text(out_name, encoding="utf-8")
        self._json(
            200,
            {
                "job": job_id,
                "filename": out_name,
                "before": info["before"],
                "after": info["after"],
                "saved_percent": info["saved_percent"],
                "note": info["note"],
                "quality": quality,
            },
        )


def main():
    JOBS.mkdir(parents=True, exist_ok=True)
    try:
        find_gs()
    except FileNotFoundError as e:
        print(e)
        raise SystemExit(1)

    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}/"
    print(f"local-pdf-compress is open: {url}")
    print("Press Ctrl+C to stop")
    webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped")


if __name__ == "__main__":
    main()
