"""Pipeline del Visor: R18 analítico + propuestas B-Rep + aprobación fría."""
from pathlib import Path
import copy
import json
import os
import sys
import time
from contratos_r19 import ROOT, sha, escribir_json, copiar_nuevo, ultimo_json, rutas_nuevas
from procesos_r19 import ejecutar


def trabajador(job, evidence, name, env, timeout):
    spec, report = evidence / (name + '.job.json'), evidence / (name + '.report.json')
    escribir_json(spec, job)
    try:
        code = ejecutar([sys.executable, str(ROOT / 'trabajador_r19.py'), str(spec), str(evidence / name), str(report)],
                        cwd=ROOT, env=env, stdout=evidence / (name + '.stdout.txt'),
                        stderr=evidence / (name + '.stderr.txt'), timeout=timeout)
        value = json.loads(report.read_text(encoding='utf-8'))
        if not isinstance(value, dict):
            raise ValueError('Informe sin objeto JSON')
        if code:
            value.update(ok=False, accepted=False, validated=False, codigo_trabajador=code)
        return value
    except Exception as exc:
        return dict(method=job['method'], ok=False, accepted=False, validated=False, error=str(exc))


def elegir(source, baseline, baseline_run, proposals):
    """Verifica de nuevo el certificado; los informes no son la autoridad."""
    from certificado_calidad_r15 import verificar
    from motor_v2 import _comparar_candidatos_cad
    from validacion_r19 import maximo
    old = json.loads(Path(baseline_run).read_text(encoding='utf-8'))
    base_hash, source_hash = sha(baseline), sha(source)
    if old['source_sha256'] != source_hash or old['step_sha256'] != base_hash:
        raise ValueError('La referencia cambió antes de la selección')
    candidates = []
    for report in proposals:
        if report.get('accepted') is not True or report.get('validated') is not True:
            continue
        try:
            candidate = Path(report['candidate'])
            if (report['source_sha256'] != source_hash or report['baseline_sha256'] != base_hash
                    or report['candidate_sha256'] != sha(candidate)):
                raise ValueError('La propuesta no coincide con sus archivos')
            quality = verificar(report['final_validation'], source, candidate, report['nonce'], ROOT)
            better, reason = _comparar_candidatos_cad(old['payload']['resultado'], dict(calidad=quality))
            if not better or maximo(quality) > maximo(old['payload']['resultado']['calidad']) + 1e-6:
                raise ValueError(reason)
            if report['contraste_comun']['regresiones_sobre_00001_mm'] != 0:
                raise ValueError('Hay regresiones en puntos comunes')
            candidates.append((quality['caras_step'], candidate, quality, report))
        except Exception as exc:
            report.update(accepted=False, validated=False, error='Selección: ' + str(exc))
    if sha(source) != source_hash or sha(baseline) != base_hash:
        raise ValueError('Las entradas cambiaron durante la selección')
    return min(candidates, key=lambda row: row[0]) if candidates else None


def convertir(source, destination):
    from perfiles_precision import obtener_perfil
    from certificado_calidad_r15 import firma_motor
    from avance_conversion import avance
    from respaldo_r19 import guardar
    from politica_conversion import presupuesto_conversion
    source, destination, evidence = rutas_nuevas(source, destination)
    policy = presupuesto_conversion(source.read_bytes())
    profile = obtener_perfil()
    before, fingerprint = sha(source), firma_motor(ROOT)
    evidence.mkdir()
    start = time.monotonic()
    env = {**os.environ, 'VISOR_PERFIL': profile['id'], 'PYTHONDONTWRITEBYTECODE': '1',
           'PYTHONIOENCODING': 'utf-8', 'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1'}
    audit = dict(version='R19', original_sha256=before, motor_sha256=fingerprint, perfil=profile,
                 etapas=[], estado='ingesta', validadores_modificados=False, presupuesto=policy)
    pipeline_report = destination.with_suffix('.r19_pipeline.json')
    def persist():
        audit['segundos'] = time.monotonic() - start
        escribir_json(pipeline_report, audit)
    def announce(percent, message):
        avance(percent, message)
        with destination.with_suffix('.motor.log').open('a', encoding='utf-8') as stream:
            stream.write('[R19] ' + message + '\n')
    avance(1, 'Evaluación de la malla original')
    ingested = trabajador(dict(method='ingesta', source=str(source), motor_sha256=fingerprint), evidence, 'ingesta', env, 90)
    audit['ingesta'] = ingested
    input_report = ingested.get('ingesta', dict(optimizacion_admisible=False))
    persist()
    # Los hitos R18 se escalan para dejar espacio a la validación R19. No se
    # muestran porcentajes terminales antes de aprobar el STEP definitivo.
    progress = evidence / 'base.avance.jsonl'
    seen = 0
    def tick():
        nonlocal seen
        if progress.exists():
            lines = progress.read_text(encoding='utf-8', errors='replace').splitlines()
            for line in lines[seen:]:
                try:
                    item = json.loads(line)
                    avance(max(2, int(item['porcentaje'] * .8)), item['fase'])
                except (ValueError, KeyError):
                    continue
            seen = len(lines)
    audit['estado'] = 'reconstruccion_analitica_base'
    persist()
    code = ejecutar([sys.executable, str(ROOT / 'motor_v2.py'), str(source), str(destination)], cwd=ROOT,
                    env={**env, 'VISOR_AVANCE_PATH': str(progress)}, stdout=evidence / 'base.stdout.txt',
                    stderr=evidence / 'base.stderr.txt', timeout=policy['maximo_s'], tick=tick)
    payload = ultimo_json(evidence / 'base.stdout.txt')
    if code or payload.get('ok') is not True:
        audit.update(estado='base_rechazada', codigo_base=code)
        persist()
        if code and payload.get('ok') is True:
            return dict(ok=False, error='El motor base terminó con código ' + str(code), tipo_error='base_interrumpida')
        return payload
    if sha(source) != before or firma_motor(ROOT) != fingerprint:
        raise ValueError('El original o el programa cambió durante la conversión')
    # El servidor puede recuperar esta referencia completa si interrumpe una
    # optimización. Una cancelación explícita siempre prevalece.
    guardar(source, destination, payload)
    baseline = evidence / 'base.step'
    base_hash = copiar_nuevo(destination, baseline)
    base_run = evidence / 'base.run.json'
    escribir_json(base_run, dict(returncode=0, payload=payload, source_sha256=before, step_sha256=base_hash))
    audit.update(estado='optimizacion', base_sha256=base_hash, caras_base=payload['resultado']['calidad']['caras_step'])
    persist()
    proposals = []
    enabled = os.environ.get('VISOR_PIPELINE_R19', '1') == '1'
    for method, percent in [('planos', 82), ('costuras', 90)]:
        if not enabled:
            break
        announce(percent, 'Comprobando ' + ('caras planas contiguas' if method == 'planos' else 'costuras cilíndricas'))
        job = dict(method=method, source=str(source), baseline=str(baseline), baseline_run=str(base_run),
                   motor_sha256=fingerprint, input_report=input_report)
        report = trabajador(job, evidence, method, env, 720)
        proposals.append(report)
        audit['etapas'].append(report)
        persist()
    announce(97, 'Selección del STEP validado')
    selected = elegir(source, baseline, base_run, proposals)
    result = copy.deepcopy(payload)
    if selected is not None:
        _, candidate, quality, report = selected
        if sha(source) != before or sha(destination) != base_hash:
            raise ValueError('Una entrada cambió antes de publicar el STEP')
        temporary = destination.with_name(destination.name + '.r19_seleccion.tmp')
        copied_hash = copiar_nuevo(candidate, temporary)
        if copied_hash != report['candidate_sha256']:
            raise ValueError('La selección cambió después de validar')
        os.replace(temporary, destination)
        result['resultado']['calidad'] = quality
        # Conservar el certificado completo junto al STEP realmente elegido.
        final = copy.deepcopy(report['final_validation'])
        final.update(step_sha256=copied_hash, original_sha256=before, metodo_r19=report['method'])
        escribir_json(destination.with_suffix('.r19_nucleo.json'), final)
        method = report['method']
    else:
        if sha(destination) != base_hash:
            raise ValueError('Se alteró la referencia sin una propuesta aprobada')
        method = 'r18'
    improvement = dict(aplicado=selected is not None, metodo='pipeline_brep_r19', etapa_seleccionada=method,
                       caras_antes=audit['caras_base'], caras_despues=result['resultado']['calidad']['caras_step'],
                       base_sha256=base_hash, step_sha256=sha(destination), original_sha256=before,
                       tolerancias_modificadas=False)
    result['resultado']['mejora_superficies'] = improvement
    result['mejora_superficies'] = improvement
    audit.update(estado='terminado', seleccion=improvement)
    persist()
    if sha(source) != before or sha(baseline) != base_hash or firma_motor(ROOT) != fingerprint:
        raise ValueError('Una entrada o el programa cambió antes del resultado final')
    announce(99, 'STEP final comprobado')
    return result
