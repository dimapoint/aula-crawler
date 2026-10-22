# aula-crawler

![CI](https://github.com/dimapoint/aula-crawler/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Licencia](https://img.shields.io/badge/licencia-MIT-green)

Descarga automáticamente el contenido de tus aulas virtuales Moodle y lo deja ordenado en carpetas, aunque el profe haya armado un laberinto de mosaicos, subapartados, carpetas y links.

Probado contra el aula virtual de la UCC (`presencial.ucc.edu.ar`, formato mosaicos). Funciona con cualquier Moodle 4.x/5.x.

## Qué hace

- Recorre el curso completo: mosaicos, secciones de temas/semanas y subapartados anidados.
- Baja archivos, carpetas, adjuntos de tareas (con su consigna) y páginas de contenido.
- Guarda los links externos (R, Drive, YouTube, etc.) en un `_enlaces.md` por materia.
- Sincroniza de forma incremental: lo que ya bajaste no se vuelve a descargar.
- Modo simulacro para ver qué bajaría sin escribir nada.
- Login una sola vez (SSO y 2FA incluidos): la sesión queda guardada en tu compu. Tu contraseña nunca se guarda: entrás a mano en la ventana o, si querés, la pasás por las variables de entorno `AULA_USUARIO`/`AULA_CLAVE`.

## Instalación

```bash
git clone https://github.com/dimapoint/aula-crawler.git
cd aula-crawler
uv tool install .
uvx playwright install chromium
```

## Uso

```bash
# 1) Iniciar sesión (abre una ventana; entrás como siempre y la cerrás sola)
aula-crawler login

# 2) Ver tus cursos con su ID
aula-crawler cursos

# Lo más cómodo: una ventana con tus cursos para tildar, elegir carpeta y bajar
aula-crawler ui

# 3) Bajar cursos: sin argumentos te muestra un menú numerado para elegir
aula-crawler bajar

# o directo por ID o URL
aula-crawler bajar 15188
aula-crawler bajar 15188 15190 -o ~/Facultad

# O todos de una vez
aula-crawler bajar --todos -o ~/Facultad

# Ver qué bajaría sin escribir nada
aula-crawler bajar 15188 --simulacro

# Sólo ciertos tipos de contenido
aula-crawler bajar 15188 --tipos resource,folder
```

Para otro Moodle: `aula-crawler --base-url https://otra.universidad.edu cursos`.

## Cómo queda ordenado

```
~/Facultad/
└── ESTADÍSTICA MULTIVARIADA/
    ├── 01 - Estadística Multivariada/
    ├── 03 - Modelos Lineales/
    │   ├── Scripts Cátedra A/        <- subapartado
    │   │   └── Regresión Lineal/     <- carpeta de Moodle
    │   └── Clase 1.pdf
    ├── 07 - Ejercicios prácticos/
    ├── _enlaces.md                   <- links externos
    └── .manifest.json                <- registro para sincronizar
```

## Tipos de actividad soportados

| Tipo Moodle | Qué se hace |
|---|---|
| `resource` | Descarga el archivo |
| `folder` | Descarga todos los archivos en una subcarpeta |
| `assign` | Guarda la consigna (HTML) y sus adjuntos |
| `page` | Guarda la página en HTML y registra sus links |
| `url` | Agrega el link a `_enlaces.md` |
| foros, cuestionarios, etc. | Se ignoran |

## Desarrollo

```bash
uv sync --extra dev
uv run pytest          # tests con HTML de ejemplo, sin red ni navegador
uv run ruff check .
```

Estructura:

- `src/aula_crawler/parsing.py` interpreta el HTML (puro, testeable).
- `src/aula_crawler/descargas.py` descarga cada tipo de actividad, con reintentos.
- `src/aula_crawler/crawler.py` orquesta el recorrido de un curso.
- `src/aula_crawler/auth.py` maneja la sesión persistente del navegador.
- `src/aula_crawler/cli.py` define los comandos.

## Problemas conocidos

- Si un archivo sale como `? sin archivo descargable`, abrí un issue con el tipo de actividad (no pegues URLs con tu sesión).
- Si Moodle te desloguea, corré `aula-crawler login` de nuevo.

## Uso responsable

Usalo sólo con tus propias cuentas y materiales a los que tengas acceso, respetando los términos de tu universidad y los derechos de autor de los docentes. El script hace pocas solicitudes seguidas; no lo uses para saturar el servidor.

## Licencia

MIT. Ver [LICENSE](LICENSE).
