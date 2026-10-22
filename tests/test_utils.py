from pathlib import Path

from aula_crawler.utils import carpeta_unica, id_de_url, limpiar, nombre_desde_headers, url_curso


def test_limpiar_quita_caracteres_prohibidos():
    assert limpiar("Clase 1: Intro/Repaso?.pdf") == "Clase 1 Intro Repaso .pdf"


def test_limpiar_vacio_y_largo():
    assert limpiar("") == "sin_nombre"
    assert len(limpiar("a" * 500)) <= 90


def test_nombre_desde_content_disposition_utf8():
    h = {"content-disposition": "attachment; filename*=UTF-8''Gu%C3%ADa%201.pdf"}
    assert nombre_desde_headers(h, "https://x/y") == "Guía 1.pdf"


def test_nombre_desde_filename_utf8_crudo():
    crudo = "Clase práctica Regresión.docx".encode().decode("latin-1")  # como llega por Playwright
    h = {"content-disposition": f'inline; filename="{crudo}"'}
    assert nombre_desde_headers(h, "https://x/y") == "Clase práctica Regresión.docx"
    h = {"content-disposition": 'inline; filename="Guía.pdf"'}  # ya bien decodificado: no se toca
    assert nombre_desde_headers(h, "https://x/y") == "Guía.pdf"


def test_nombre_desde_url_si_no_hay_header():
    url = "https://aula.test/pluginfile.php/1/mod_resource/content/1/Clase%201.pptx?forcedownload=1"
    assert nombre_desde_headers({}, url) == "Clase 1.pptx"


def test_url_curso():
    assert url_curso("https://a.test/", "15188") == "https://a.test/course/view.php?id=15188"
    assert url_curso("https://a.test", "https://a.test/course/view.php?id=9") == "https://a.test/course/view.php?id=9"


def test_id_de_url():
    assert id_de_url("https://a.test/mod/resource/view.php?id=77&x=1") == "77"


def test_carpeta_unica(tmp_path: Path):
    f = tmp_path / "a.pdf"
    f.write_text("x")
    assert carpeta_unica(f).name == "a (1).pdf"
