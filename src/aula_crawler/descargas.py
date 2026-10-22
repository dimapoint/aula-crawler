"""Descarga de cada tipo de actividad (archivo, carpeta, URL, página, tarea)."""
from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path

from . import parsing
from .parsing import Actividad
from .utils import carpeta_unica, limpiar, nombre_desde_headers

REINTENTOS = 3


class Descargador:
    def __init__(self, req, base: str, destino: Path, dry_run: bool = False,
                 log: Callable[[str], None] = print):
        self.req, self.base, self.dir = req, base, destino
        self.dry_run, self.log = dry_run, log
        self.enlaces: list[str] = []
        self.stats = {"nuevos": 0, "salteados": 0, "errores": 0}
        self._manifest_path = destino / ".manifest.json"
        self.manifest: dict[str, str] = {}
        if self._manifest_path.exists():
            self.manifest = json.loads(self._manifest_path.read_text(encoding="utf-8"))

    # ---------------------------------------------------------------- red
    def get(self, url: str, **kw):
        ultimo: Exception | None = None
        for intento in range(REINTENTOS):
            try:
                r = self.req.get(url, **kw)
                if r.status >= 500:
                    raise RuntimeError(f"HTTP {r.status}")
                return r
            except Exception as e:  # noqa: BLE001 - reintento genérico de red
                ultimo = e
                time.sleep(1.5 * (intento + 1))
        raise RuntimeError(f"falló tras {REINTENTOS} intentos: {ultimo}")

    def html(self, url: str):
        return parsing.soup(self.get(url).text())

    def _guardar(self, resp, carpeta: Path, nombre_pref: str | None = None) -> Path:
        nombre = nombre_desde_headers(resp.headers, resp.url)
        if nombre_pref and not Path(nombre).suffix:
            nombre = limpiar(nombre_pref) + Path(nombre).suffix
        destino = carpeta_unica(carpeta / nombre)
        if self.dry_run:
            self.log(f"    (simulacro) {destino.relative_to(self.dir)}")
            return destino
        carpeta.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(resp.body())
        return destino

    # ------------------------------------------------------------ despacho
    def procesar(self, act: Actividad, carpeta: Path) -> None:
        if act.cmid in self.manifest and Path(self.manifest[act.cmid]).exists():
            self.stats["salteados"] += 1
            return
        if act.subcarpeta:
            carpeta = carpeta / act.subcarpeta
        manejador = {
            "resource": self.recurso, "folder": self.carpeta, "url": self.url,
            "page": self.pagina, "assign": self.tarea,
        }.get(act.tipo)
        if manejador is None:
            return  # foros, cuestionarios, etc.
        try:
            manejador(act, carpeta)
        except Exception as e:  # noqa: BLE001
            self.stats["errores"] += 1
            self.log(f"    ! error en '{act.nombre}': {e}")

    def guardar_manifest(self) -> None:
        if self.dry_run:
            return
        self.dir.mkdir(parents=True, exist_ok=True)
        self._manifest_path.write_text(
            json.dumps(self.manifest, indent=1, ensure_ascii=False), encoding="utf-8")
        if self.enlaces:
            ruta = self.dir / "_enlaces.md"
            previos = ruta.read_text(encoding="utf-8").splitlines() if ruta.exists() else []
            ruta.write_text("\n".join(sorted(set(previos) | set(self.enlaces))) + "\n", encoding="utf-8")

    def _registrar(self, act: Actividad, ruta: Path) -> None:
        self.manifest[act.cmid] = str(ruta)
        self.stats["nuevos"] += 1

    # ----------------------------------------------------------- manejadores
    def recurso(self, act: Actividad, carpeta: Path) -> None:
        r = self.get(act.href)
        if "text/html" in r.headers.get("content-type", ""):
            # Moodle mostró una página intermedia (modo "incrustar" / "en página")
            h = parsing.soup(r.text())
            destinos = parsing.enlaces_a_archivos(h, self.base)
            if not destinos:
                self.log(f"    ? sin archivo descargable: {act.nombre}")
                return
            r = self.get(destinos[0])
        ruta = self._guardar(r, carpeta, act.nombre)
        self._registrar(act, ruta)
        self.log(f"    + {ruta.name}")

    def carpeta(self, act: Actividad, carpeta: Path) -> None:
        destino = carpeta / limpiar(act.nombre)
        for link in parsing.enlaces_a_archivos(self.html(act.href), self.base):
            ruta = self._guardar(self.get(link), destino)
            self.log(f"    + {destino.name}/{ruta.name}")
        self._registrar(act, destino)

    def url(self, act: Actividad, carpeta: Path) -> None:
        r = self.get(act.href, max_redirects=0)
        destino = r.headers.get("location") or parsing.destino_url(parsing.soup(r.text())) or act.href
        self.enlaces.append(f"- [{act.nombre}]({destino}) — {carpeta.name}")
        self.log(f"    ~ link: {act.nombre}")

    def pagina(self, act: Actividad, carpeta: Path) -> None:
        h = self.html(act.href)
        cuerpo = h.select_one("#region-main .box.generalbox, [role=main]") or h
        ruta = carpeta / f"{limpiar(act.nombre)}.html"
        if not self.dry_run:
            carpeta.mkdir(parents=True, exist_ok=True)
            ruta.write_text(f"<meta charset='utf-8'><h1>{act.nombre}</h1>{cuerpo}", encoding="utf-8")
        for a in cuerpo.find_all("a", href=True):
            if a["href"].startswith("http") and "pluginfile" not in a["href"]:
                self.enlaces.append(f"- [{a.get_text(' ', strip=True) or a['href']}]({a['href']}) — {act.nombre}")
        self._registrar(act, ruta)
        self.log(f"    + {ruta.name}")

    def tarea(self, act: Actividad, carpeta: Path) -> None:
        h = self.html(act.href)
        destino = carpeta / f"Tarea - {limpiar(act.nombre)}"
        desc = h.select_one("#intro, .activity-description")
        if desc and not self.dry_run:
            destino.mkdir(parents=True, exist_ok=True)
            (destino / "consigna.html").write_text(f"<meta charset='utf-8'>{desc}", encoding="utf-8")
        for link in parsing.enlaces_a_archivos(h, self.base):
            self._guardar(self.get(link), destino)
        self._registrar(act, destino)
        self.log(f"    + tarea: {act.nombre}")
