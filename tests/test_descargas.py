"""Prueba el Descargador con una sesión HTTP falsa (sin navegador ni red)."""
from pathlib import Path

from aula_crawler.descargas import Descargador
from aula_crawler.parsing import Actividad

BASE = "https://aula.test"


class FakeResp:
    def __init__(self, url, body=b"", ct="application/pdf", status=200, headers=None):
        self.url, self._body, self.status = url, body, status
        self.headers = {"content-type": ct, **(headers or {})}

    def body(self):
        return self._body

    def text(self):
        return self._body.decode()


class FakeReq:
    def __init__(self, rutas):
        self.rutas, self.llamadas = rutas, []

    def get(self, url, **kw):
        self.llamadas.append(url)
        return self.rutas[url]


def test_recurso_se_descarga_y_se_saltea_en_la_segunda_corrida(tmp_path: Path):
    url = f"{BASE}/mod/resource/view.php?id=1"
    final = f"{BASE}/pluginfile.php/9/mod_resource/content/1/Clase%201.pdf"
    req = FakeReq({url: FakeResp(final, b"%PDF-1.4 hola")})
    act = Actividad("1", "resource", "Clase 1", url)

    d = Descargador(req, BASE, tmp_path / "Materia", log=lambda *_: None)
    d.procesar(act, d.dir / "01 - Tema")
    d.guardar_manifest()
    assert (d.dir / "01 - Tema" / "Clase 1.pdf").read_bytes() == b"%PDF-1.4 hola"
    assert d.stats["nuevos"] == 1

    d2 = Descargador(req, BASE, tmp_path / "Materia", log=lambda *_: None)
    d2.procesar(act, d2.dir / "01 - Tema")
    assert d2.stats == {"nuevos": 0, "salteados": 1, "errores": 0}


def test_simulacro_no_escribe_nada(tmp_path: Path):
    url = f"{BASE}/mod/resource/view.php?id=2"
    final = f"{BASE}/pluginfile.php/9/x/Guia.pdf"
    req = FakeReq({url: FakeResp(final, b"datos")})
    d = Descargador(req, BASE, tmp_path / "M", dry_run=True, log=lambda *_: None)
    d.procesar(Actividad("2", "resource", "Guia", url), d.dir / "01 - T")
    d.guardar_manifest()
    assert not (tmp_path / "M").exists()


def test_recurso_con_pagina_intermedia(tmp_path: Path):
    url = f"{BASE}/mod/resource/view.php?id=3"
    html = '<a href="/pluginfile.php/1/doc.docx?forcedownload=1">bajar</a>'
    real = f"{BASE}/pluginfile.php/1/doc.docx?forcedownload=1"
    req = FakeReq({
        url: FakeResp(url, html.encode(), ct="text/html"),
        real: FakeResp(real, b"PK", ct="application/octet-stream"),
    })
    d = Descargador(req, BASE, tmp_path / "M", log=lambda *_: None)
    d.procesar(Actividad("3", "resource", "Doc", url), d.dir / "T")
    assert (d.dir / "T" / "doc.docx").exists()


def test_url_registra_enlace(tmp_path: Path):
    url = f"{BASE}/mod/url/view.php?id=4"
    html = '<div class="urlworkaround"><a href="https://cran.r-project.org/">x</a></div>'
    req = FakeReq({url: FakeResp(url, html.encode(), ct="text/html")})
    d = Descargador(req, BASE, tmp_path / "M", log=lambda *_: None)
    d.procesar(Actividad("4", "url", "Descargar R", url), d.dir / "01 - T")
    d.guardar_manifest()
    assert "https://cran.r-project.org/" in (d.dir / "_enlaces.md").read_text()


def test_error_se_cuenta_y_no_corta(tmp_path: Path):
    class Rota:
        def get(self, *a, **k):
            raise ConnectionError("sin red")

    import aula_crawler.descargas as mod
    mod.time.sleep = lambda *_: None  # no esperar en el test
    d = Descargador(Rota(), BASE, tmp_path / "M", log=lambda *_: None)
    d.procesar(Actividad("5", "resource", "X", f"{BASE}/mod/resource/view.php?id=5"), d.dir)
    assert d.stats["errores"] == 1
