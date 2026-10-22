"""Ventana simple (tkinter) para elegir cursos con casillas y bajarlos sin saber sus IDs."""

import contextlib
import json
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk
from tkinter.scrolledtext import ScrolledText

from .auth import asegurar_login, cargar_sesion, guardar_sesion
from .crawler import correr_curso, listar_cursos
from .utils import url_curso


class _HaciaCola:
    """stdout falso: cada print del crawler termina en el log de la ventana."""

    def __init__(self, salida: queue.Queue):
        self.salida = salida

    def write(self, texto: str) -> None:
        if texto:
            self.salida.put(("log", texto))

    def flush(self) -> None:
        pass


def _trabajar(base: str, perfil: Path, pedidos: queue.Queue, salida: queue.Queue) -> None:
    """Todo Playwright vive en este hilo: la API sync no se puede usar desde otro."""
    from playwright.sync_api import sync_playwright

    perfil.mkdir(parents=True, exist_ok=True)
    archivo_sesion = perfil.parent / "sesion.json"
    try:
        with sync_playwright() as pw:
            ctx = pw.chromium.launch_persistent_context(str(perfil), headless=False, accept_downloads=True)
            cargar_sesion(ctx, archivo_sesion)
            try:
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
                with contextlib.redirect_stdout(_HaciaCola(salida)):
                    asegurar_login(page, base)
                salida.put(("cursos", listar_cursos(page)))
                while (pedido := pedidos.get()) is not None:
                    ids, raiz, simulacro = pedido
                    total = {"nuevos": 0, "salteados": 0, "errores": 0}
                    with contextlib.redirect_stdout(_HaciaCola(salida)):
                        for c in ids:
                            try:
                                s = correr_curso(page, ctx.request, base, url_curso(base, c), raiz, simulacro)
                            except Exception as e:  # un curso roto no corta los demás
                                print(f"\n! error en el curso {c}: {e}")
                                total["errores"] += 1
                                continue
                            for k in total:
                                total[k] += s[k]
                    salida.put(("fin", total))
            finally:
                guardar_sesion(ctx, archivo_sesion)
                ctx.close()
    except (Exception, SystemExit) as e:  # SystemExit: asegurar_login venció el tiempo
        salida.put(("error", str(e) or type(e).__name__))


def abrir(base: str, perfil: Path) -> int:
    pedidos = queue.Queue()  # ventana -> hilo de Playwright
    salida = queue.Queue()  # hilo de Playwright -> ventana
    hilo = threading.Thread(target=_trabajar, args=(base, perfil, pedidos, salida), daemon=True)
    hilo.start()

    root = tk.Tk()
    root.title("aula-crawler")
    root.geometry("660x620")

    estado = tk.StringVar(value="Conectando… (si se abre Chromium pidiendo login, iniciá sesión ahí)")
    ttk.Label(root, textvariable=estado).pack(anchor="w", padx=8, pady=(8, 4))

    marco = ttk.Frame(root)
    marco.pack(fill="both", expand=True, padx=8)
    lienzo = tk.Canvas(marco, highlightthickness=0, height=240)
    barra = ttk.Scrollbar(marco, orient="vertical", command=lienzo.yview)
    lista = ttk.Frame(lienzo)
    lista.bind("<Configure>", lambda _e: lienzo.configure(scrollregion=lienzo.bbox("all")))
    lienzo.create_window((0, 0), window=lista, anchor="nw")
    lienzo.configure(yscrollcommand=barra.set)
    lienzo.bind_all("<MouseWheel>", lambda e: lienzo.yview_scroll(-e.delta // 120, "units"))
    lienzo.pack(side="left", fill="both", expand=True)
    barra.pack(side="right", fill="y")
    marcados: list[tuple[tk.BooleanVar, dict]] = []

    def marcar(valor: bool) -> None:
        for var, _curso in marcados:
            var.set(valor)

    fila_marcar = ttk.Frame(root)
    fila_marcar.pack(fill="x", padx=8, pady=4)
    ttk.Button(fila_marcar, text="Todos", command=lambda: marcar(True)).pack(side="left")
    ttk.Button(fila_marcar, text="Ninguno", command=lambda: marcar(False)).pack(side="left", padx=4)

    preferencias = perfil.parent / "ui.json"
    try:
        ultima = json.loads(preferencias.read_text(encoding="utf-8"))["carpeta"]
    except (OSError, ValueError, KeyError, TypeError):
        ultima = str(Path.home() / "Aulas")
    destino = tk.StringVar(value=ultima)

    def elegir_carpeta() -> None:
        if carpeta := filedialog.askdirectory(initialdir=destino.get()):
            destino.set(carpeta)

    fila_carpeta = ttk.Frame(root)
    fila_carpeta.pack(fill="x", padx=8, pady=4)
    ttk.Label(fila_carpeta, text="Carpeta:").pack(side="left")
    ttk.Entry(fila_carpeta, textvariable=destino).pack(side="left", fill="x", expand=True, padx=4)
    ttk.Button(fila_carpeta, text="Elegir…", command=elegir_carpeta).pack(side="left")

    simulacro = tk.BooleanVar()
    fila_bajar = ttk.Frame(root)
    fila_bajar.pack(fill="x", padx=8, pady=4)
    ttk.Checkbutton(fila_bajar, text="Simulacro (muestra qué bajaría, sin escribir nada)",
                    variable=simulacro).pack(side="left")
    boton_bajar = ttk.Button(fila_bajar, text="Bajar", state="disabled")
    boton_bajar.pack(side="right")

    log = ScrolledText(root, height=12, state="disabled")
    log.pack(fill="both", expand=True, padx=8, pady=(4, 8))

    def escribir(texto: str) -> None:
        log.configure(state="normal")
        log.insert("end", texto)
        log.see("end")
        log.configure(state="disabled")

    def lanzar() -> None:
        ids = [str(c["id"]) for var, c in marcados if var.get()]
        if not ids:
            estado.set("Tildá al menos un curso.")
            return
        boton_bajar.configure(state="disabled")
        estado.set("Bajando… (el detalle va abajo)")
        try:
            preferencias.write_text(json.dumps({"carpeta": destino.get()}), encoding="utf-8")
        except OSError:
            pass  # recordar la carpeta es comodidad; no frena la descarga
        pedidos.put((ids, Path(destino.get()).expanduser(), simulacro.get()))

    boton_bajar.configure(command=lanzar)

    def revisar_cola() -> None:
        while True:
            try:
                tipo, dato = salida.get_nowait()
            except queue.Empty:
                break
            if tipo == "cursos":
                for c in dato:
                    var = tk.BooleanVar()
                    marcados.append((var, c))
                    ttk.Checkbutton(lista, text=c["nombre"], variable=var).pack(anchor="w")
                estado.set(f"{len(dato)} cursos. Tildá los que quieras bajar.")
                boton_bajar.configure(state="normal")
            elif tipo == "log":
                escribir(dato)
            elif tipo == "fin":
                estado.set(f"Listo: {dato['nuevos']} nuevos, {dato['salteados']} ya estaban, "
                           f"{dato['errores']} errores.")
                boton_bajar.configure(state="normal")
            elif tipo == "error":
                estado.set(f"Error: {dato}")
        root.after(100, revisar_cola)

    def cerrar() -> None:
        pedidos.put(None)
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", cerrar)
    revisar_cola()
    root.mainloop()
    # shortcut: si cerrás en medio de una descarga, a los 10 s se corta sin guardar la sesión;
    # agregar cancelación entre archivos si molesta.
    hilo.join(timeout=10)
    return 0
