"""Interfaz de línea de comandos: aula-crawler login | cursos | bajar."""

import argparse
import sys
from pathlib import Path

from . import __version__
from .auth import PERFIL_DEFECTO, asegurar_login, cargar_sesion, guardar_sesion
from .crawler import correr_curso, listar_cursos
from .utils import url_curso

BASE_DEFECTO = "https://presencial.ucc.edu.ar"


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="aula-crawler",
        description="Descarga automáticamente el contenido de tus aulas virtuales Moodle.")
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("--base-url", default=BASE_DEFECTO, help=f"sitio Moodle (defecto: {BASE_DEFECTO})")
    p.add_argument("--perfil", default=str(PERFIL_DEFECTO), help="carpeta con la sesión guardada")
    sub = p.add_subparsers(dest="accion", required=True)

    sub.add_parser("login", help="abre el navegador para iniciar sesión (una sola vez)")
    sub.add_parser("cursos", help="lista tus cursos con su ID")
    sub.add_parser("ui", help="abre una ventana para elegir cursos y bajarlos")

    b = sub.add_parser("bajar", help="descarga uno o más cursos")
    b.add_argument("cursos", nargs="*", help="ID o URL de cada curso (sin nada: menú para elegir)")
    b.add_argument("--todos", action="store_true", help="bajar todos tus cursos")
    b.add_argument("-o", "--salida", default=str(Path.home() / "Aulas"), help="carpeta de destino")
    b.add_argument("--simulacro", action="store_true", help="muestra qué bajaría, sin escribir nada")
    b.add_argument("--tipos", default="", help="limitar a tipos: resource,folder,url,page,assign")
    b.add_argument("--sin-ventana", action="store_true", help="navegador oculto (requiere login previo)")
    return p


def elegir_cursos(cursos: list[dict], entrada: str) -> list[str]:
    """Traduce '1 3,5' o 'todos' (números del menú) a IDs de curso; ignora lo que no sea válido."""
    if entrada.strip().lower() == "todos":
        return [str(c["id"]) for c in cursos]
    elegidos = []
    for parte in entrada.replace(",", " ").split():
        if parte.isdigit() and 1 <= int(parte) <= len(cursos):
            elegidos.append(str(cursos[int(parte) - 1]["id"]))
    return elegidos


def menu_cursos(page) -> list[str]:
    cursos = listar_cursos(page)
    for numero, c in enumerate(cursos, 1):
        print(f"{numero:>3}. {c['nombre']}")
    return elegir_cursos(cursos, input("\nNúmeros de los cursos a bajar (ej: 1 3 5, o 'todos'): "))


def main(argv: list[str] | None = None) -> int:
    a = parser().parse_args(argv)
    if a.accion == "ui":
        from .ui import abrir  # abre su propio Playwright en un hilo aparte

        return abrir(a.base_url, Path(a.perfil))
    from playwright.sync_api import sync_playwright

    Path(a.perfil).mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            a.perfil, headless=getattr(a, "sin_ventana", False), accept_downloads=True)
        archivo_sesion = Path(a.perfil).parent / "sesion.json"
        cargar_sesion(ctx, archivo_sesion)
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            asegurar_login(page, a.base_url)

            if a.accion == "cursos":
                for c in listar_cursos(page):
                    print(f"{c['id']:>7}  {c['nombre']}")
            elif a.accion == "bajar":
                if a.todos:
                    ids = [str(c["id"]) for c in listar_cursos(page)]
                elif a.cursos:
                    ids = a.cursos
                else:
                    ids = menu_cursos(page) if sys.stdin.isatty() else []
                if not ids:
                    print("Pasá IDs/URLs de cursos o usá --todos.", file=sys.stderr)
                    return 2
                tipos = {t.strip() for t in a.tipos.split(",") if t.strip()} or None
                total = {"nuevos": 0, "salteados": 0, "errores": 0}
                for c in ids:
                    s = correr_curso(page, ctx.request, a.base_url, url_curso(a.base_url, c),
                                     Path(a.salida).expanduser(), a.simulacro, tipos)
                    for k in total:
                        total[k] += s[k]
                print(f"\nListo: {total['nuevos']} nuevos, {total['salteados']} ya estaban, "
                      f"{total['errores']} errores.")
                return 1 if total["errores"] else 0
        finally:
            guardar_sesion(ctx, archivo_sesion)
            ctx.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
