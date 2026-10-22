"""Smoke de punta a punta: Moodle falso local + aula-crawler real con Chromium headless.

Uso (desde la raíz del repo): python .claude/skills/run-aula-crawler/driver.py
Imprime la salida del CLI y falla (exit 1) si no baja lo esperado.
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PUERTO = 8765
BASE = f"http://127.0.0.1:{PUERTO}"
SESION = '<script>window.M={cfg:{userId:2,sesskey:"abc"}}</script>'


def act(cmid, tipo, nombre):
    return (f'<li class="activity modtype_{tipo}"><div class="activityname"><a class="aalink" '
            f'href="{BASE}/mod/{tipo}/view.php?id={cmid}"><span class="instancename">{nombre}</span>'
            f'</a></div></li>')


CURSO = (f'<html><head><title>Curso: Álgebra | Fake</title>{SESION}</head><body><ul>'
         '<li class="section course-section"><h3 class="sectionname">Semana 1</h3><ul>'
         + act(12, "resource", "Guía 1") + act(13, "page", "Apuntes") + act(14, "url", "R")
         + "</ul></li></ul></body></html>")


class Fake(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def responder(self, cuerpo, tipo="text/html; charset=utf-8", codigo=200, extra=None):
        datos = cuerpo if isinstance(cuerpo, bytes) else cuerpo.encode()
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(datos)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(datos)

    def do_POST(self):  # listado de cursos (AJAX interno)
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        j = [{"error": False, "data": {"courses": [{"id": 1, "fullname": "Álgebra", "hidden": False}]}}]
        self.responder(json.dumps(j), "application/json")

    def do_GET(self):
        p = self.path
        if p.startswith("/my/"):
            self.responder(f"<html><head>{SESION}</head><body>mis cursos</body></html>")
        elif p.startswith("/course/view.php"):
            self.responder(CURSO)
        elif p.startswith("/mod/resource/"):
            self.responder("", codigo=303, extra={"Location": "/pluginfile.php/1/guia.pdf"})
        elif p.startswith("/pluginfile.php"):
            self.responder(b"%PDF-fake", "application/pdf",
                           extra={"Content-Disposition": 'attachment; filename="guia.pdf"'})
        elif p.startswith("/mod/page/"):
            self.responder('<html><body><div role="main"><a href="https://ejemplo.org/x">Sitio</a></div></body></html>')
        elif p.startswith("/mod/url/"):
            self.responder("", codigo=303, extra={"Location": "https://ejemplo.org/r"})
        else:
            self.responder("no existe", codigo=404)


def main() -> int:
    srv = ThreadingHTTPServer(("127.0.0.1", PUERTO), Fake)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    with tempfile.TemporaryDirectory() as tmp:
        base = [sys.executable, "-m", "aula_crawler", "--base-url", BASE, "--perfil", f"{tmp}/perfil"]
        for args in (["cursos"], ["bajar", "1", "-o", f"{tmp}/out", "--sin-ventana"]):
            r = subprocess.run(base + args, capture_output=True, text=True, encoding="utf-8",
                               env={**os.environ, "PYTHONIOENCODING": "utf-8"})
            print(r.stdout, r.stderr)
            if r.returncode:
                return 1
        archivos = sorted(p.relative_to(tmp).as_posix() for p in Path(tmp, "out").rglob("*") if p.is_file())
        print("\n".join(archivos))
        esperados = ["00 - Semana 1/Apuntes.html", "00 - Semana 1/guia.pdf", "_enlaces.md", ".manifest.json"]
        faltan = [e for e in esperados if not any(a.endswith(e) for a in archivos)]
        if faltan:
            print("FALTAN:", faltan)
            return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
