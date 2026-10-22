# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Comandos

```bash
uv sync --extra dev && uv run playwright install chromium   # make install
uv run pytest -q                                             # make test (sin red ni navegador)
uv run pytest tests/test_parsing.py::nombre_del_test         # un solo test
uv run ruff check .                                          # make lint (line-length 110; E,F,I,B,UP)
uv run aula-crawler ui                                       # ventana tkinter para tildar cursos y bajar
uv run aula-crawler login | cursos | bajar [<id|url...>] [--todos] [--simulacro] [--tipos resource,folder] [-o dir]
```

Para correr el crawler de punta a punta sin credenciales reales hay una skill local: `.claude/skills/run-aula-crawler` (Moodle falso local).

Código, mensajes y docs están en español (rioplatense); mantené esa convención en nombres y textos.

## Arquitectura

CLI que baja contenido de un Moodle (por defecto `presencial.ucc.edu.ar`, cambiable con `--base-url`) usando una sesión persistente de Playwright. Flujo: `cli.main` → `auth.asegurar_login` → `crawler.correr_curso` por curso → `Descargador.procesar` por actividad.

- `auth.py`: perfil persistente de Chromium en `~/.aula_crawler/perfil`. El login se hace una vez: si están `AULA_USUARIO` y `AULA_CLAVE` en el entorno, completa el formulario estándar de Moodle (`#username`/`#password`/`#loginbtn`); si no (o si hay SSO/2FA), espera a que el usuario inicie sesión en la ventana. La UCC tiene MFA (`/admin/tool/mfa/auth.php`): ahí `M.cfg.userId` ya está seteado, por eso `logueado` excluye esa URL. La cookie `MoodleSession` es de sesión y Chromium la borra al cerrarse, por eso `cli.main` la guarda en `~/.aula_crawler/sesion.json` (`guardar_sesion`) y la restaura al arrancar (`cargar_sesion`): el MFA se pide solo cuando Moodle vence la sesión. Las credenciales nunca se escriben a disco ni van en el repo. Las páginas intermedias del login también traen `userId`, por eso la espera confirma volviendo a `/my/`.
- `crawler.py`: orquesta un curso. Dos layouts: **mosaicos** (sección 0 en la página del curso + una página por mosaico, cada una parseada aparte) y **temas/semanas** (todo en una página). La carpeta del curso sale del título de la página, por eso `correr_curso` falla si Moodle redirigió fuera de `/course/view.php` (sesión vencida) en vez de crear una carpeta con el título del login/MFA. Cada sección se escribe en `NN - Título/`. `listar_cursos` llama al AJAX interno de Moodle (`core_course_get_enrolled_courses_by_timeline_classification`) con el `sesskey` de la página.
- `cli.py`: `bajar` sin IDs muestra un menú numerado (solo si stdin es una terminal; `elegir_cursos` es la parte testeable).
- `ui.py`: tkinter en el hilo principal y **todo** Playwright en un único hilo trabajador (la API sync no tolera otro hilo); se hablan por dos `queue.Queue` (pedidos ventana→hilo, mensajes hilo→ventana leídos con `root.after`). El log se captura redirigiendo `stdout`, porque `correr_curso`/`Descargador` usan `print`. La última carpeta se recuerda en `~/.aula_crawler/ui.json`.
- `utils.nombre_desde_headers`: Moodle manda UTF-8 crudo en `filename="..."` y Playwright lo entrega leído como latin-1; se recodifica (sin eso salen nombres tipo `RegresiÃ³n`).
- `parsing.py`: funciones puras sobre HTML (BeautifulSoup) → `Seccion`/`Actividad`. Es lo que cubren los tests, con fixtures en `tests/fixtures/*.html`. Si cambia el HTML de Moodle, se arregla acá y se agrega un fixture.
- `descargas.py`: `Descargador` baja cada tipo (`resource`, `folder`, `assign`, `page`, `url`) con reintentos, usa `ctx.request` (misma sesión/cookies que el navegador), lleva stats y un `.manifest.json` por curso para la sincronización incremental. `dry_run` evita toda escritura. Los links externos van a `_enlaces.md`.

Tipos no soportados (foros, cuestionarios, etc.) se ignoran a propósito.
