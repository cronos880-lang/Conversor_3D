"""Última conversión R18 completa, protegida antes de las propuestas R19."""
from pathlib import Path
import copy
import json
import os
from contratos_r19 import sha, copiar_nuevo, escribir_json
from respaldo_conversion import calidad_aprobada

REVISION = 'R19_BASE_COMPLETA_INMUTABLE_V1'


def rutas(destination):
    destination = Path(destination)
    return (destination.with_name(destination.name + '.r19_base_validada.step'),
            destination.with_name(destination.name + '.r19_base_validada.json'))


def guardar(source, destination, payload):
    step, report = rutas(destination)
    if step.exists() or report.exists():
        raise ValueError('Ya existe un respaldo R19')
    source_hash = sha(source)
    if not calidad_aprobada(payload) or payload.get('preprocesamiento', {}).get('original_sha256') != source_hash:
        raise ValueError('No hay una conversión completa vinculada al original')
    copied = copiar_nuevo(destination, step)
    record = dict(revision=REVISION, source_sha256=source_hash, step_sha256=copied,
                  perfil=payload['resultado']['calidad']['perfil_validacion']['id'], payload=copy.deepcopy(payload))
    escribir_json(report, record)
    if sha(source) != source_hash or sha(destination) != copied:
        raise ValueError('Una entrada cambió al respaldar')
    return record


def recuperar(source, destination, *, perfil, motivo, cancelado=False):
    if cancelado:
        return None
    source, destination = map(Path, (source, destination))
    step, report = rutas(destination)
    try:
        record = json.loads(report.read_text(encoding='utf-8'))
        payload = record['payload']
        if (record.get('revision') != REVISION or record['perfil'] != perfil
                or record['source_sha256'] != sha(source) or record['step_sha256'] != sha(step)
                or not calidad_aprobada(payload)
                or payload['preprocesamiento']['original_sha256'] != record['source_sha256']
                or payload['resultado']['calidad']['perfil_validacion']['id'] != perfil):
            return None
        temporary = destination.with_name(destination.name + '.recuperando_r19.tmp')
        copiar_nuevo(step, temporary)
        if sha(source) != record['source_sha256']:
            temporary.unlink()
            return None
        os.replace(temporary, destination)
        result = copy.deepcopy(payload)
        result['recuperacion_respaldo'] = dict(aplicado=True, revision=REVISION, perfil=perfil,
                                               step_sha256=record['step_sha256'])
        result['mejora_superficies'] = dict(aplicado=False, estado='conservada_conversion_validada', motivo=str(motivo))
        return result
    except (OSError, ValueError, KeyError, TypeError):
        from respaldo_conversion import recuperar as legacy
        return legacy(source, destination, perfil=perfil, motivo=motivo, cancelado=cancelado)
