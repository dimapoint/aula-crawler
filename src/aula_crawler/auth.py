"""Sesión de navegador persistente: el login se hace una sola vez (a mano o con variables de entorno)."""

import json
import os
import sys
import time
from pathlib import Path

PERFIL_DEFECTO = Path.home() / ".aula_crawler" / "perfil"
_JS_LOGUEADO = "() => !!(window.M && M.cfg && M.cfg.userId && M.cfg.userId > 1)"


def cargar_sesion(ctx, ruta: Path) -> None:
    """Restaura las cookies de sesión (MoodleSession) que Chromium borra al cerrarse."""
    try:
        ctx.add_cookies(json.loads(ruta.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass  # sin archivo o corrupto: se hace login normal


def guardar_sesion(ctx, ruta: Path) -> None:
    ruta.write_text(json.dumps(ctx.cookies()), encoding="utf-8")


def logueado(page) -> bool:
    if "/admin/tool/mfa/" in page.url:
        return False  # contraseña OK pero falta el segundo factor; M.cfg.userId ya está cargado acá
    try:
        return bool(page.evaluate(_JS_LOGUEADO))
    except Exception:
        return False  # la página está navegando (por ejemplo, redirección SSO)


def asegurar_login(page, base: str, espera_max: int = 300) -> None:
    """Si no hay sesión guardada, espera a que el usuario inicie sesión en la ventana."""
    page.goto(f"{base}/my/", wait_until="domcontentloaded")
    if logueado(page):
        return
    usuario, clave = os.environ.get("AULA_USUARIO"), os.environ.get("AULA_CLAVE")
    if usuario and clave:
        # Formulario estándar de Moodle; si hay SSO/2FA, el bucle de abajo espera a que se complete.
        page.goto(f"{base}/login/index.php", wait_until="domcontentloaded")
        page.fill("#username", usuario)
        page.fill("#password", clave)
        page.click("#loginbtn")
        page.wait_for_load_state("domcontentloaded")
        # Volver a /my/ como en el camino normal: el sesskey de la página post-login no sirve para AJAX.
        page.goto(f"{base}/my/", wait_until="domcontentloaded")
        if logueado(page):
            print(">> Sesión iniciada con AULA_USUARIO y guardada.")
            return
        if "/admin/tool/mfa/" in page.url:
            print("\n>> Usuario y contraseña OK; falta el código MFA en la ventana.", flush=True)
    # flush: si la salida va a un archivo/pipe, sin esto el aviso no aparece hasta que termina
    print("\n>> Iniciá sesión en la ventana del navegador (espero hasta "
          f"{espera_max // 60} minutos)...", flush=True)
    t0 = time.time()
    while time.time() - t0 < espera_max:
        time.sleep(2)
        if logueado(page):
            # Confirmar en /my/: páginas intermedias del login ya traen userId, y si falta el MFA el
            # servidor redirige a /admin/tool/mfa/.
            page.goto(f"{base}/my/", wait_until="domcontentloaded")
            if logueado(page):
                print(">> Sesión detectada y guardada.")
                return
    sys.exit("No se detectó el login a tiempo.")


def sesskey(page) -> str:
    return page.evaluate("() => M.cfg.sesskey")
