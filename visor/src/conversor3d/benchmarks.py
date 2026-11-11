"""Casos sintéticos reproducibles con referencia CAD y propiedades conocidas."""
from pathlib import Path
import hashlib
import json
import math

import cadquery as cq
import trimesh
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_Sewing
from OCP.Geom import Geom_BezierSurface
from OCP.GeomConvert import GeomConvert
from OCP.TColgp import TColgp_Array2OfPnt
from OCP.gp import gp_Pnt


def residual_box() -> cq.Solid:
    """Caja exacta 6×4×2 mm con seis dominios B-Spline en su cara superior."""
    faces = [f for f in cq.Solid.makeBox(6, 4, 2).Faces() if f.Center().z < 1.99]
    for x in range(6):
        poles = TColgp_Array2OfPnt(1, 2, 1, 2)
        for i, xx in enumerate((x, x + 1), 1):
            for j, yy in enumerate((0, 4), 1):
                poles.SetValue(i, j, gp_Pnt(xx, yy, 2))
        surface = GeomConvert.SurfaceToBSplineSurface_s(Geom_BezierSurface(poles))
        faces.append(cq.Face(BRepBuilderAPI_MakeFace(surface, 1e-7).Face()))
    sewing = BRepBuilderAPI_Sewing(1e-7)
    for face in faces:
        sewing.Add(face.wrapped)
    sewing.Perform()
    return cq.Solid.makeSolid(cq.Shape.cast(sewing.SewedShape()))


def cases() -> dict:
    cylinder = cq.Solid.makeCylinder(3, 10)
    rounded = cq.Workplane('XY').circle(3).extrude(10).edges().fillet(.5).val()
    radius, fillet, height = 3., .5, 10.
    inner = radius - fillet
    rounded_volume = (math.pi * radius ** 2 * (height - 2 * fillet)
                      + 2 * math.pi * (inner ** 2 * fillet
                                      + inner * math.pi * fillet ** 2 / 2
                                      + 2 * fillet ** 3 / 3))
    wall = cq.Solid.makeBox(10, 8, 2).cut(
        cq.Solid.makeBox(9.7, 7.7, 2, cq.Vector(.15, .15, 0)))
    hole = cq.Solid.makeBox(6, 4, 2).cut(
        cq.Solid.makeCylinder(.15, 2, cq.Vector(3, 2, 0)))
    freeform = cq.Solid.makeLoft([
        cq.Wire.makeCircle(2, cq.Vector(0, 0, 0), cq.Vector(0, 0, 1)),
        cq.Wire.makeCircle(2.5, cq.Vector(.5, 0, 3), cq.Vector(0, 0, 1)),
        cq.Wire.makeCircle(1.5, cq.Vector(-.2, 0, 6), cq.Vector(0, 0, 1)),
    ])
    return {
        'cylinder': {'shape': cylinder, 'volume_mm3': math.pi * 90, 'euler': 2},
        'rounded': {'shape': rounded, 'volume_mm3': rounded_volume, 'euler': 2},
        'thin_wall': {'shape': wall, 'volume_mm3': (80 - 9.7 * 7.7) * 2, 'euler': 0,
                      'minimum_wall_mm': .15, 'void_point_mm': [5, 4, 1]},
        'small_hole': {'shape': hole, 'volume_mm3': 48 - math.pi * .15 ** 2 * 2, 'euler': 0,
                       'hole_diameter_mm': .3, 'void_point_mm': [3, 2, 1]},
        'freeform': {'shape': freeform, 'volume_mm3': freeform.Volume(), 'euler': 2},
        'rotated': {'shape': rounded.rotate((0, 0, 0), (1, 2, 3), .61 * 180 / math.pi)
                    .translate((-20, 13, -4)), 'volume_mm3': rounded_volume, 'euler': 2},
        'residual_planes': {'shape': residual_box(), 'volume_mm3': 48., 'euler': 2},
    }


def generate(output: Path) -> list[dict]:
    """Genera datos de prueba nuevos; nunca repara ni modifica un STL del usuario."""
    output = Path(output)
    output.mkdir(exist_ok=False)
    manifest = []
    for name, spec in cases().items():
        shape = spec['shape']
        vertices, triangles = shape.tessellate(.0005, .08)
        mesh = trimesh.Trimesh([p.toTuple() for p in vertices], triangles, process=True)
        mesh.fix_normals()
        source, reference = output / (name + '.stl'), output / (name + '.step')
        mesh.export(source)
        cq.exporters.export(shape, str(reference))
        manifest.append({'name': name, **{k: v for k, v in spec.items() if k != 'shape'},
                         'stl_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                         'cad_faces': len(shape.Faces()), 'triangles': len(mesh.faces),
                         'reference': 'CAD sintético conocido; no conversión STL a STEP'})
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return manifest
