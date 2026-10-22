"""Orquestación: recorre un curso completo y delega cada actividad al Descargador."""

from pathlib import Path

from . import parsing
from .descargas import Descargador
from .utils import limpiar


def correr_curso(page, req, base: str, url: str, raiz: Path, dry_run: bool = False,
                 solo_tipos: set[str] | None = None) -> dict[str, int]:
    page.goto(url, wait_until="domcontentloaded")
    if "/course/view.php" not in page.url:  # Moodle redirigió (login/MFA): no crear carpeta con ese título
        raise RuntimeError(f"Moodle no abrió el curso (redirigió a {page.url}); ¿venció la sesión?")
    html = parsing.soup(page.content())
    nombre = parsing.titulo_curso(page.title())
    print(f"\n=== {nombre} ===")

    d = Descargador(req, base, raiz / nombre, dry_run=dry_run)

    if parsing.es_mosaicos(html):
        secciones = [parsing.seccion_cero(html, base)]
        for titulo, href in parsing.enlaces_mosaicos(html, base):
            secciones.append(parsing.Seccion(
                titulo, href, parsing.actividades(d.html(href), base)))
        secciones = [s for i, s in enumerate(secciones) if i > 0 or s.actividades]
    else:
        secciones = parsing.secciones_curso(html, base)

    for i, sec in enumerate(secciones):
        carpeta = d.dir / f"{i:02d} - {limpiar(sec.titulo)}"
        acts = [a for a in sec.actividades if not solo_tipos or a.tipo in solo_tipos]
        print(f"  [{sec.titulo}] {len(acts)} actividades")
        for act in acts:
            d.procesar(act, carpeta)

    d.guardar_manifest()
    s = d.stats
    print(f"  -> {s['nuevos']} nuevos, {s['salteados']} ya descargados, {s['errores']} errores")
    return s


def listar_cursos(page) -> list[dict]:
    """Cursos en los que estás matriculado (API interna AJAX de Moodle, misma sesión)."""
    from .auth import sesskey

    return page.evaluate(
        """async (sk) => {
            const r = await fetch('/lib/ajax/service.php?sesskey=' + sk +
              '&info=core_course_get_enrolled_courses_by_timeline_classification', {
              method: 'POST', credentials: 'include',
              headers: {'Content-Type': 'application/json'},
              body: JSON.stringify([{index: 0,
                methodname: 'core_course_get_enrolled_courses_by_timeline_classification',
                args: {offset: 0, limit: 0, classification: 'all', sort: 'fullname',
                       customfieldname: '', customfieldvalue: ''}}])});
            const j = await r.json();
            if (!Array.isArray(j)) throw new Error('Moodle respondió: ' + JSON.stringify(j).slice(0, 200));
            if (j[0].error) throw new Error(j[0].exception.message);
            return j[0].data.courses.map(c => ({id: c.id, nombre: c.fullname, oculto: c.hidden}));
        }""",
        sesskey(page),
    )
