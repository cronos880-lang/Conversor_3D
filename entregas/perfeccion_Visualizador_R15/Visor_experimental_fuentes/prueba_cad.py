"""Reutilizar sólo el control CAD ya realizado sobre los mismos bytes STEP.

Las medidas frente al STL y la coherencia exacta se comprueban de nuevo en el
padre. Se evita repetir BOP tras el trabajador aislado y validado.
"""
from dataclasses import dataclass
from pathlib import Path
import hashlib

REVISION='R8_BOP_FRIO_20261027'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

@dataclass(frozen=True)
class PruebaCAD:
    step_sha256:str
    revision:str

def desde_trabajador(record,path):
    quality=record.get('calidad',{})
    if (record.get('ok') is not True or record.get('revision_cad')!=REVISION
            or record.get('brep_exacto') is not True
            or quality.get('interferencias_comprobadas_en_frio') is not True
            or quality.get('autointerferencias_occ') is not False
            or quality.get('control_cad_reutilizado_por_sha256') is not False
            or record.get('step_sha256')!=sha(path)):
        raise ValueError('El resultado del trabajador no demuestra el control CAD de este STEP.')
    return PruebaCAD(record['step_sha256'],REVISION)

def valida(prueba,path):
    return isinstance(prueba,PruebaCAD) and prueba.revision==REVISION and prueba.step_sha256==sha(path)
