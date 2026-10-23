"""Rescate acotado de un B-Rep con interferencias, conservando sus superficies.

Recalcula intersecciones de caras y fusiona aristas cortas con precisión 0,001
mm. Exige un sólido, los controles STL/STEP originales y cero interferencias
tras escribir y releer. Nunca cambia los límites de aceptación del Visor.
"""
from pathlib import Path
import tempfile


class InterferenciasCAD(ValueError):
    def __init__(self, cantidad, calidad):
        super().__init__(f'La reconstrucción presenta defectos topológicos avanzados: '
                         f'{cantidad} posibles interferencias entre caras, aristas o vértices.')
        self.cantidad, self.calidad = cantidad, calidad


def comprobar_interferencias(shape):
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Check
    check=BRepAlgoAPI_Check(shape.wrapped,False,True)
    return check.IsValid(),len(list(check.Result()))


def intentar_sanear(source, step, original, validar):
    import cadquery as cq
    from OCP.BOPAlgo import BOPAlgo_MakerVolume
    from OCP.ShapeFix import ShapeFix_Wireframe
    from calidad_topologica import inspeccionar
    shape=cq.importers.importStep(str(step)).solids().val()
    before=inspeccionar(shape)
    maker=BOPAlgo_MakerVolume()
    maker.SetIntersect(True);maker.SetAvoidInternalShapes(True)
    maker.SetNonDestructive(True);maker.SetFuzzyValue(0.);maker.SetRunParallel(False)
    for face in shape.Faces():maker.AddArgument(face.wrapped)
    maker.Perform()
    if maker.HasErrors():raise ValueError('No se pudieron resolver las intersecciones CAD.')
    rebuilt=cq.Shape.cast(maker.Shape())
    if not rebuilt.isValid() or len(rebuilt.Solids())!=1:
        raise ValueError('El saneamiento no produce un único sólido válido; descartado.')
    # Fusionar segmentos cortos de una forma ya cerrada, sin cerrar agujeros
    # STL ni eliminar cuerpos. El resultado vuelve a medirse íntegramente.
    wire=ShapeFix_Wireframe(rebuilt.wrapped)
    wire.SetPrecision(.001);wire.SetMaxTolerance(.001);wire.SetMinTolerance(1e-7)
    changed=wire.FixSmallEdges()
    healed=cq.Shape.cast(wire.Shape())
    if not healed.isValid() or len(healed.Solids())!=1:
        raise ValueError('El ajuste de aristas deja un B-Rep inválido; descartado.')
    with tempfile.TemporaryDirectory(prefix='visor_saneamiento_') as directory:
        target=Path(directory)/'verificado.step'
        cq.exporters.export(healed,str(target))
        quality=validar(source,target,original)
        back=cq.importers.importStep(str(target)).solids().val()
        ok,count=comprobar_interferencias(back)
        if not ok:raise ValueError(f'El saneamiento conserva {count} interferencias; descartado.')
        from avance_conversion import avance
        from validacion_local import inspeccionar_local
        avance(78,'Verificando aristas y encuentros del CAD saneado frente al STL')
        local=inspeccionar_local(source,back,puntos_stl=700,puntos_cad=3000,tolerancia_max=.060)
        if local['supera_umbral_observado']:
            raise ValueError('Las aristas saneadas superan el máximo geométrico original de 0,060 mm.')
        quality['autointerferencias_occ']=False
        proof={'aplicado':True,'intersecciones_recalculadas':True,
               'fuzzy_booleano_mm':0.,'precision_aristas_mm':.001,
               'aristas_cortas_fusionadas':bool(changed),
               'topologia_antes':before,'topologia_despues':inspeccionar(back),
               'control_local_aristas':local,
               'validacion':'STEP reimportado, mismos límites y sin interferencias OCC'}
        step.write_bytes(target.read_bytes())
        return quality,proof
