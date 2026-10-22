"""Funciones puras de apoyo (sin red ni navegador), fáciles de testear."""

import re
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

_PROHIBIDOS = re.compile(r'[\\/:*?"<>|\r\n\t]+')


def limpiar(nombre: str | None, maximo: int = 90) -> str:
    """Devuelve un nombre válido para cualquier sistema de archivos."""
    nombre = _PROHIBIDOS.sub(" ", nombre or "").strip(" .")
    nombre = re.sub(r"\s+", " ", nombre)
    return nombre[:maximo].rstrip(" .") or "sin_nombre"


def nombre_desde_headers(headers: dict[str, str], url: str) -> str:
    """Nombre de archivo según Content-Disposition, o el último tramo de la URL."""
    cd = headers.get("content-disposition", "")
    m = re.search(r"filename\*=UTF-8''([^;]+)", cd, re.I) or re.search(
        r'filename="?([^";]+)"?', cd, re.I
    )
    if m:
        nombre = unquote(m.group(1))
        try:  # Moodle manda UTF-8 crudo en filename="..." y llega leído como latin-1
            nombre = nombre.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass  # ya era texto correcto
        return limpiar(nombre, 150)
    return limpiar(unquote(Path(urlparse(url).path).name), 150)


def url_curso(base: str, arg: str) -> str:
    """Acepta un ID numérico o una URL completa y devuelve la URL del curso."""
    if arg.isdigit():
        return f"{base.rstrip('/')}/course/view.php?id={arg}"
    return arg


def id_de_url(href: str) -> str:
    """Extrae el parámetro ?id= de una URL de Moodle (cmid), o la URL si no hay."""
    return parse_qs(urlparse(href).query).get("id", [href])[0]


def carpeta_unica(destino: Path) -> Path:
    """Si el archivo ya existe agrega ' (1)', ' (2)', etc."""
    i = 1
    candidato = destino
    while candidato.exists():
        candidato = destino.with_name(f"{destino.stem} ({i}){destino.suffix}")
        i += 1
    return candidato
