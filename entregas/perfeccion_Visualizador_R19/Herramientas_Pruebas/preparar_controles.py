"""Controles CAD sintéticos reproducibles, sin modelos del usuario.

Uso: python preparar_controles.py carpeta_nueva
Después ejecutar ensayar_referencia.py con entrada.stl, base.step y base.run.json.
Estas referencias CAD no se presentan como conversiones R18.
"""
from pathlib import Path
import sys
import cadquery as cq
import trimesh

ROOT = Path(__file__).resolve().parents[1] / 'Visor_experimental_fuentes'
sys.path.insert(0, str(ROOT))
from contratos_r19 import sha, escribir_json
from exportacion_r19 import exportar
from motor_v2 import _calidad
from preprocesador_stl import cargar_exacto
from test_pipeline_r19 import caja_fragmentada, cuerpo_con_planos_y_costura


def main(output):
    output = Path(output)
    output.mkdir(exist_ok=False)
    plate = cq.Solid.makeBox(16, 12, 3, cq.Vector(-8, -6, 0))
    for x in (-4, 0, 4):
        for y in (-3, 3):
            half = cq.Solid.makeCylinder(1.25, 3, cq.Vector(x, y, 0), cq.Vector(0, 0, 1), 180)
            plate = plate.cut(half).cut(half.rotate((x, y, 0), (x, y, 1), 180))
    for name, shape in [('caja_fragmentada', caja_fragmentada()[0]),
                        ('planos_y_taladro', cuerpo_con_planos_y_costura()), ('placa_seis_taladros', plate)]:
        folder = output / name
        folder.mkdir()
        source, baseline = folder / 'entrada.stl', folder / 'base.step'
        exportar(shape, baseline)
        vertices, faces = shape.tessellate(.00025, .04)
        mesh = trimesh.Trimesh([p.toTuple() for p in vertices], faces, process=True)
        mesh.fix_normals()
        if len(mesh.faces) <= len(shape.Faces()):
            mesh = mesh.subdivide().subdivide()
        mesh.export(source)
        quality = _calidad(source, baseline, cargar_exacto(source), control_avanzado=True)
        escribir_json(folder / 'base.run.json', dict(returncode=0, payload=dict(ok=True, resultado=dict(calidad=quality)),
                      source_sha256=sha(source), step_sha256=sha(baseline),
                      origin='CAD sintético construido y validado; no conversión R18'))
        print(name, len(shape.Faces()), 'caras CAD,', len(mesh.faces), 'triángulos STL', flush=True)


if __name__ == '__main__':
    main(*sys.argv[1:])
