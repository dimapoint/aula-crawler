"""Interpretación del HTML de Moodle. Sin red: recibe texto y devuelve estructuras."""

import re
from dataclasses import dataclass, field
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from .utils import id_de_url, limpiar

RE_ARCHIVO = re.compile(r"pluginfile\.php|forcedownload=1")
TIPOS_DESCARGABLES = {"resource", "folder", "url", "page", "assign"}


@dataclass
class Actividad:
    cmid: str
    tipo: str          # resource, folder, url, page, assign, forum, subsection...
    nombre: str
    href: str
    subcarpeta: str | None = None


@dataclass
class Seccion:
    titulo: str
    url: str | None = None                     # None = ya está en la página del curso
    actividades: list[Actividad] = field(default_factory=list)


def soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def es_mosaicos(html: BeautifulSoup) -> bool:
    return bool(html.select('a[href*="course/section.php"]'))


def titulo_curso(titulo_pagina: str) -> str:
    """'Curso: ESTADÍSTICA MULTIVARIADA | UCC' -> 'ESTADÍSTICA MULTIVARIADA'."""
    t = titulo_pagina.split("|")[0]
    t = re.sub(r"^\s*Curso:\s*", "", t)
    return limpiar(t)


def enlaces_mosaicos(html: BeautifulSoup, base: str) -> list[tuple[str, str]]:
    """(titulo, url) de cada mosaico, sin duplicados y en orden."""
    vistos: set[str] = set()
    out: list[tuple[str, str]] = []
    for a in html.select('a[href*="course/section.php"]'):
        href = urljoin(base, a["href"])
        titulo = a.get_text(" ", strip=True)
        if href in vistos or not titulo:
            continue
        vistos.add(href)
        out.append((titulo, href))
    return out


def _tipo(li: Tag) -> str:
    return next((c[8:] for c in li.get("class", []) if c.startswith("modtype_")), "")


def _nombre(li: Tag, a: Tag) -> str:
    el = li.select_one(".instancename")
    if el is None:
        return a.get_text(" ", strip=True)
    # El texto directo excluye el <span class="accesshide"> ("Archivo", "Carpeta"...)
    directo = "".join(el.find_all(string=True, recursive=False)).strip()
    return directo or el.get_text(" ", strip=True)


def actividades(nodo: Tag | BeautifulSoup, base: str) -> list[Actividad]:
    """Todas las actividades de un nodo, incluyendo las anidadas en subapartados."""
    out: list[Actividad] = []
    vistos: set[str] = set()
    for li in nodo.select("li.activity"):
        tipo = _tipo(li)
        if tipo == "subsection":
            continue  # contenedor; sus hijos también son li.activity
        a = li.select_one(".activityname a, a.aalink")
        if a is None or not a.get("href"):
            continue
        href = urljoin(base, a["href"])
        cmid = id_de_url(href)
        if cmid in vistos:
            continue
        vistos.add(cmid)
        padre = li.find_parent("li", class_="modtype_subsection")
        titulo_sub = padre.select_one(".sectionname") if padre else None
        sub = limpiar(titulo_sub.get_text(" ", strip=True)) if titulo_sub else None
        out.append(Actividad(cmid, tipo, _nombre(li, a), href, sub))
    return out


def secciones_curso(html: BeautifulSoup, base: str) -> list[Seccion]:
    """Secciones de un curso en formato temas/semanas (todo viene en la misma página)."""
    out: list[Seccion] = []
    for li in html.select("li.section.course-section"):
        if "delegated" in li.get("class", []):
            continue  # subapartado: lo maneja actividades()
        t = li.select_one(".sectionname")
        titulo = t.get_text(" ", strip=True) if t else "General"
        out.append(Seccion(titulo, None, actividades(li, base)))
    return out


def seccion_cero(html: BeautifulSoup, base: str) -> Seccion:
    s0 = html.select_one('li.section[data-number="0"], #section-0')
    return Seccion("General", None, actividades(s0, base) if s0 else [])


def enlaces_a_archivos(html: BeautifulSoup, base: str) -> list[str]:
    """URLs de archivos de Moodle (pluginfile) dentro de una página, ordenadas."""
    return sorted({urljoin(base, a["href"]) for a in html.find_all("a", href=RE_ARCHIVO)})


def destino_url(html: BeautifulSoup) -> str | None:
    """Link externo de una actividad 'URL' cuando Moodle muestra la página intermedia."""
    a = html.select_one(".urlworkaround a") or html.select_one("a[href^=http]")
    return a["href"] if a else None
