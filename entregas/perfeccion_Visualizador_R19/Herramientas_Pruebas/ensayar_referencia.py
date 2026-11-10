"""Postprocesar una referencia CAD validada; NO simula una conversión nueva.

Uso: python ensayar_referencia.py entrada.stl base.step base.run.json carpeta_nueva
"""
from pathlib import Path
import json
import os
import sys

ROOT = Path(__file__).resolve().parents[1] / 'Visor_experimental_fuentes'
sys.path.insert(0, str(ROOT))
from contratos_r19 import sha, escribir_json, copiar_nuevo
from certificado_calidad_r15 import firma_motor
from pipeline_r19 import trabajador, elegir


def run(source, baseline, baseline_run, output):
    source, baseline, baseline_run, output = map(lambda p: Path(p).resolve(), (source, baseline, baseline_run, output))
    old = json.loads(baseline_run.read_text(encoding='utf-8'))
    before = sha(source), sha(baseline)
    if old['source_sha256'] != before[0] or old['step_sha256'] != before[1]:
        raise ValueError('Referencia incompatible con sus hashes')
    if old.get('returncode') != 0 or old.get('payload', {}).get('ok') is not True:
        raise ValueError('Falta una referencia aprobada')
    output.mkdir(exist_ok=False)
    env = {**os.environ, 'VISOR_PERFIL': old['payload']['resultado']['calidad']['perfil_validacion']['id'],
           'PYTHONDONTWRITEBYTECODE': '1', 'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1'}
    os.environ['VISOR_PERFIL'] = env['VISOR_PERFIL']
    fingerprint = firma_motor(ROOT)
    ingestion = trabajador(dict(method='ingesta', source=str(source), motor_sha256=fingerprint), output, 'ingesta', env, 90)
    reports = []
    for method in ('planos', 'costuras'):
        reports.append(trabajador(dict(method=method, source=str(source), baseline=str(baseline),
                                      baseline_run=str(baseline_run), motor_sha256=fingerprint,
                                      input_report=ingestion.get('ingesta', dict(optimizacion_admisible=False))),
                                   output, method, env, 720))
    selected = elegir(source, baseline, baseline_run, reports)
    chosen = selected[1] if selected else baseline
    quality = selected[2] if selected else old['payload']['resultado']['calidad']
    selected_hash = copiar_nuevo(chosen, output / 'seleccion.step')
    if (sha(source), sha(baseline)) != before or firma_motor(ROOT) != fingerprint:
        raise ValueError('Una referencia o el programa cambió')
    result = dict(origin='Postproceso de referencia CAD; no conversión STL completa nueva',
                  input_origin=old.get('origin', 'Referencia de conversión R18'),
                  selected_method=selected[3]['method'] if selected else 'r18',
                  faces_before=old['payload']['resultado']['calidad']['caras_step'],
                  faces_after=quality['caras_step'], verified_max_mm=quality['desviacion_max_verificada_mm'],
                  baseline_preserved=True, source_sha256=before[0], baseline_sha256=before[1],
                  selected_sha256=selected_hash, motor_sha256=fingerprint, quality=quality,
                  reports=reports, ingestion=ingestion)
    escribir_json(output / 'resultado.json', result)
    return result


if __name__ == '__main__':
    result = run(*sys.argv[1:])
    print(json.dumps({k: v for k, v in result.items() if k not in ('quality', 'reports', 'ingestion')}, indent=2))
