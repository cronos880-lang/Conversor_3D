"""STEP en milímetros, exportación nueva y relectura obligatoria."""
from pathlib import Path
import cadquery as cq
from contratos_r19 import sha
from topologia_r19 import exigir_solido


def exportar(shape, destination, *, backend='ocp'):
    destination = Path(destination)
    if destination.exists():
        raise ValueError('No se sobrescribe un STEP existente')
    exigir_solido(shape)
    if backend == 'ocp':
        from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs
        from OCP.Interface import Interface_Static
        from OCP.IFSelect import IFSelect_RetDone
        # Cada propuesta se exporta en su proceso aislado. Estas opciones de
        # OCCT son globales y no se cambian en el servidor concurrente.
        writer = STEPControl_Writer()
        Interface_Static.SetCVal_s('write.step.schema', 'AP214IS')
        Interface_Static.SetCVal_s('write.step.unit', 'MM')
        if writer.Transfer(shape.wrapped, STEPControl_AsIs) != IFSelect_RetDone:
            raise ValueError('Transferencia STEP rechazada')
        if writer.Write(str(destination)) != IFSelect_RetDone:
            raise ValueError('Escritura STEP rechazada')
    elif backend == 'cadquery':
        cq.exporters.export(shape, str(destination))
    else:
        raise ValueError('Exportador no reconocido')
    before = sha(destination)
    reread = cq.importers.importStep(str(destination)).val()
    report = exigir_solido(reread)
    if sha(destination) != before:
        raise ValueError('El STEP cambió durante su lectura')
    return reread, dict(backend=backend, esquema='AP214', unidades='mm', step_sha256=before,
                        reimportado=True, estructura=report)
