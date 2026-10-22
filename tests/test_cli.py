from aula_crawler.cli import elegir_cursos

CURSOS = [{"id": 15188, "nombre": "Estadística"}, {"id": 16179, "nombre": "Arquitectura"},
          {"id": 15057, "nombre": "Física I"}]


def test_elegir_por_numero():
    assert elegir_cursos(CURSOS, "1 3") == ["15188", "15057"]
    assert elegir_cursos(CURSOS, "2,3") == ["16179", "15057"]


def test_elegir_todos_e_invalidos():
    assert elegir_cursos(CURSOS, " Todos ") == ["15188", "16179", "15057"]
    assert elegir_cursos(CURSOS, "0 4 x") == []
