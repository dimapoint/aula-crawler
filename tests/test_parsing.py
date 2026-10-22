from pathlib import Path

from aula_crawler import parsing

FX = Path(__file__).parent / "fixtures"
BASE = "https://aula.test"


def leer(nombre: str):
    return parsing.soup((FX / nombre).read_text(encoding="utf-8"))


def test_titulo_curso():
    assert parsing.titulo_curso("Curso: ESTADÍSTICA MULTIVARIADA | UCC") == "ESTADÍSTICA MULTIVARIADA"


def test_detecta_mosaicos_y_dedupe():
    h = leer("curso_mosaicos.html")
    assert parsing.es_mosaicos(h)
    tiles = parsing.enlaces_mosaicos(h, BASE)
    assert [t for t, _ in tiles] == [
        "Estadística Multivariada", "Modelos Lineales", "Ejercicios prácticos", "Ejercicios prácticos"]


def test_tipo_correcto_sin_prefijo():
    acts = parsing.actividades(leer("seccion_mosaicos.html"), BASE)
    assert [a.tipo for a in acts] == ["resource", "url", "forum", "folder", "folder", "assign"]


def test_subsection_no_se_come_al_primer_hijo():
    acts = parsing.actividades(leer("seccion_mosaicos.html"), BASE)
    carpetas = [a for a in acts if a.tipo == "folder"]
    assert [a.cmid for a in carpetas] == ["104", "105"]
    assert {a.subcarpeta for a in carpetas} == {"Scripts Cátedra A"}


def test_nombre_sin_texto_oculto():
    acts = parsing.actividades(leer("seccion_mosaicos.html"), BASE)
    assert acts[0].nombre == "Clase 1"
    assert acts[1].nombre == "Descargar R"


def test_seccion_cero_vacia_en_mosaicos():
    assert parsing.seccion_cero(leer("curso_mosaicos.html"), BASE).actividades == []


def test_formato_semanas():
    h = leer("curso_semanas.html")
    assert not parsing.es_mosaicos(h)
    secs = parsing.secciones_curso(h, BASE)
    assert [s.titulo for s in secs] == ["General", "Semana 1"]
    assert [a.cmid for a in secs[1].actividades] == ["12", "13"]


def test_enlaces_a_archivos():
    h = parsing.soup('<a href="/pluginfile.php/1/a.pdf?forcedownload=1">a</a><a href="/x">x</a>'
                     '<a href="/pluginfile.php/1/a.pdf?forcedownload=1">dup</a>')
    assert parsing.enlaces_a_archivos(h, BASE) == [f"{BASE}/pluginfile.php/1/a.pdf?forcedownload=1"]


def test_destino_url_workaround():
    h = parsing.soup('<div class="urlworkaround"><a href="https://cran.r-project.org/">link</a></div>')
    assert parsing.destino_url(h) == "https://cran.r-project.org/"
