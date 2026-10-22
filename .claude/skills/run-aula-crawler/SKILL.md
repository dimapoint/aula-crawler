---
name: run-aula-crawler
description: Run, start, test and smoke-check aula-crawler (CLI que baja aulas Moodle con Playwright). Usar para ejecutar el crawler de punta a punta contra un Moodle falso local sin credenciales reales.
---

Rutas relativas a la raíz del repo. Verificado en Windows 11, Python 3.14, Chromium de Playwright.

Un login real (SSO/2FA) no se puede automatizar. El driver levanta un Moodle falso en `127.0.0.1:8765` (curso con un recurso, una página y un link) y corre el CLI real contra él en Chromium headless.

## Preparación

```bash
pip install -e ".[dev]"
playwright install chromium
```

## Run (agente)

```bash
PYTHONIOENCODING=utf-8 python .claude/skills/run-aula-crawler/driver.py
```

Corre `cursos` y `bajar 1 --sin-ventana` en un perfil y destino temporales, lista lo descargado y termina en `OK` (exit 0) o en `FALTAN: [...]` (exit 1). Salida esperada: `2 nuevos, 0 errores` y los archivos `guia.pdf`, `Apuntes.html`, `_enlaces.md`, `.manifest.json`.

Para cubrir otro caso (mosaicos, carpetas, tareas), ampliar `CURSO` y `Fake.do_GET` en `driver.py`.

## Tests

```bash
python -m pytest -q    # 21 tests, sin red ni navegador
```

## Run (humano)

`aula-crawler login` abre una ventana para iniciar sesión (una sola vez), después `aula-crawler cursos` y `aula-crawler bajar <id>`. Inútil sin pantalla.

## Gotchas

- `PYTHONIOENCODING=utf-8`: la consola de Windows es cp1252 y los nombres con tildes ("Álgebra") rompen el `print`. El driver ya se lo pasa al subproceso, pero hay que ponerlo en tu shell.
- El Moodle falso solo necesita `window.M.cfg.userId > 1` en `/my/` para que `asegurar_login` crea que hay sesión, y `M.cfg.sesskey` para el listado.
- Los recursos redirigen (303) a `/pluginfile.php/...`; el nombre del archivo sale de `Content-Disposition`.
- `--sin-ventana` exige perfil con login previo; con el Moodle falso no hace falta porque la sesión "existe" siempre.
- No probado: contra un Moodle real, mosaicos y `--simulacro`.
