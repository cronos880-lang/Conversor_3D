"""Construcción/validación aislada. Sólo escribe dentro del trabajo nuevo."""
from pathlib import Path
import json
import os
import sys
import time
import traceback
from contratos_r19 import ROOT, sha, escribir_json, MAX_CARAS_CAD


def run(spec_path, output, report_path):
    output, report_path = map(Path, (output, report_path))
    if output.exists() or report_path.exists():
        raise ValueError('Las salidas del trabajador deben ser nuevas')
    job = json.loads(Path(spec_path).read_text(encoding='utf-8'))
    start = time.monotonic()
    record = dict(method=job['method'], accepted=False, validated=False)
    try:
        from certificado_calidad_r15 import firma_motor
        if firma_motor(ROOT) != job['motor_sha256']:
            raise ValueError('El programa cambió desde el inicio del trabajo')
        if job['method'] == 'ingesta':
            from ingesta_r19 import evaluar
            record.update(ok=True, ingesta=evaluar(job['source']))
            record['seconds'] = time.monotonic() - start
            escribir_json(report_path, record)
            return 0
        old = json.loads(Path(job['baseline_run']).read_text(encoding='utf-8'))
        source, baseline = Path(job['source']), Path(job['baseline'])
        if old.get('returncode') != 0 or old.get('payload', {}).get('ok') is not True:
            raise ValueError('Falta la referencia aprobada')
        if sha(source) != old['source_sha256'] or sha(baseline) != old['step_sha256']:
            raise ValueError('Hashes incompatibles con la referencia')
        os.environ['VISOR_PERFIL'] = old['payload']['resultado']['calidad']['perfil_validacion']['id']
        if old['payload'].get('preprocesamiento', {}).get('reparado'):
            raise ValueError('Se conserva el tratamiento original de entradas reparadas')
        if not job['input_report'].get('optimizacion_admisible'):
            raise ValueError('Entrada fuera del contrato acotado de optimización')
        output.mkdir()
        from optimizacion_r19 import construir
        candidate, operations = construir(baseline, output / 'construccion', job['method'])
        import cadquery as cq
        n0 = old['payload']['resultado']['calidad']['caras_step']
        n1 = len(cq.importers.importStep(str(candidate)).val().Faces())
        record.update(candidate=str(candidate), candidate_sha256=sha(candidate),
                      caras_antes=n0, caras_despues=n1, construccion=operations)
        # Preselección de coste. La aceptación exige después el comparador
        # original con calidad medida, nunca métricas inventadas.
        if n1 >= n0 - max(4, int(n0 * .05)):
            raise ValueError('La reducción preliminar es insuficiente')
        from validacion_r19 import validar
        record.update(validar(source, candidate, baseline, job['baseline_run'], output))
        if firma_motor(ROOT) != job['motor_sha256']:
            raise ValueError('El programa cambió durante la validación')
    except Exception as exc:
        record.update(accepted=False, validated=False, error=str(exc))
        traceback.print_exc()
    record['seconds'] = time.monotonic() - start
    escribir_json(report_path, record)
    return 0 if record['accepted'] else 2


if __name__ == '__main__':
    raise SystemExit(run(*sys.argv[1:]))
