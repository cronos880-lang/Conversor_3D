"""Propuestas sobre copias B-Rep; ninguna propuesta se aprueba aquí."""
from pathlib import Path
import cadquery as cq
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepBuilderAPI import BRepBuilderAPI_Copy
from OCP.GeomAbs import GeomAbs_Plane
from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain
from contratos_r19 import sha, escribir_json, TOLERANCIA_COSTURA_MM, MAX_CARAS_CAD
from topologia_r19 import exigir_solido
from reconocimiento_r19 import analizar
from exportacion_r19 import exportar


def construir(source, output, method):
    source, output = map(Path, (source, output))
    if output.exists():
        raise ValueError('La construcción necesita un directorio nuevo')
    before = sha(source)
    shape = cq.importers.importStep(str(source)).val()
    exigir_solido(shape)
    inventory = analizar(shape)
    if len(shape.Faces()) > MAX_CARAS_CAD:
        raise ValueError('Fuera del presupuesto de construcción')
    if method == 'costuras':
        if not inventory.get('pares_cilindricos'):
            raise ValueError('Sin cilindros contiguos del mismo soporte')
        from costuras_r19 import refinar
        candidate, operations = refinar(source, output)
    elif method == 'planos':
        if not inventory.get('pares_planos_coplanares'):
            raise ValueError('Sin planos contiguos coplanares')
        output.mkdir()
        copied = cq.Shape.cast(BRepBuilderAPI_Copy(shape.wrapped, True, False).Shape())
        unify = ShapeUpgrade_UnifySameDomain(copied.wrapped, True, True, False)
        unify.SetSafeInputMode(True)
        unify.SetLinearTolerance(TOLERANCIA_COSTURA_MM)
        unify.SetAngularTolerance(1e-10)
        # KeepShape(edge) bloquea la reunión de las caras que comparten la
        # arista. Así se protegen todos los soportes curvos y sus costuras.
        for face in copied.Faces():
            if BRepAdaptor_Surface(face.wrapped).GetType() != GeomAbs_Plane:
                for edge in face.Edges():
                    unify.KeepShape(edge.wrapped)
        unify.Build()
        result = cq.Shape.cast(unify.Shape())
        exigir_solido(result)
        if len(result.Faces()) >= len(shape.Faces()):
            raise ValueError('La consolidación no reduce caras')
        candidate = output / 'candidato.step'
        reread, exported = exportar(result, candidate)
        operations = dict(operacion='ShapeUpgrade_UnifySameDomain', curvas_protegidas=True,
                          tolerancia_mm=TOLERANCIA_COSTURA_MM, caras_antes=len(shape.Faces()),
                          caras_despues=len(reread.Faces()), exportacion=exported)
    else:
        raise ValueError('Método de construcción desconocido')
    if sha(source) != before:
        raise ValueError('La propuesta modificó la referencia')
    escribir_json(output / 'inventario.json', inventory)
    return candidate, operations
