from pathlib import Path

from aula_crawler.auth import cargar_sesion, guardar_sesion


class CtxFalso:
    def __init__(self, cookies=None):
        self.guardadas = cookies or []

    def cookies(self):
        return self.guardadas

    def add_cookies(self, cookies):
        self.guardadas = cookies


def test_sesion_ida_y_vuelta(tmp_path: Path):
    ruta = tmp_path / "sesion.json"
    cookie = {"name": "MoodleSession", "value": "abc", "domain": "a.test", "path": "/"}
    guardar_sesion(CtxFalso([cookie]), ruta)
    nuevo = CtxFalso()
    cargar_sesion(nuevo, ruta)
    assert nuevo.guardadas == [cookie]


def test_cargar_sesion_sin_archivo_o_corrupto(tmp_path: Path):
    ctx = CtxFalso()
    cargar_sesion(ctx, tmp_path / "no_existe.json")
    (tmp_path / "roto.json").write_text("{no es json")
    cargar_sesion(ctx, tmp_path / "roto.json")
    assert ctx.guardadas == []
