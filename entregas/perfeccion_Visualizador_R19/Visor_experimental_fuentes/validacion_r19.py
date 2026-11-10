"""Puerta de aprobación: núcleo frío original y controles adicionales."""
from pathlib import Path
import json
import os
import secrets
import sys
import cadquery as cq
from contratos_r19 import ROOT, sha, escribir_json
from procesos_r19 import ejecutar


def maximo(quality):
    values = [quality.get('desviacion_max_verificada_mm', 0.)]
    for name in ('distancia_stl_step_mm', 'distancia_step_stl_mm'):
        values.append(quality.get(name, {}).get('max_muestreado', 0.))
    for name in ('stl_a_cad', 'cad_a_stl'):
        values.append(quality.get('inspeccion_densa', {}).get(name, {}).get('max_mm', 0.))
    return max(values)


def validar(source, candidate, baseline, baseline_run, evidence):
    from certificado_calidad_r15 import verificar
    from motor_v2 import _comparar_candidatos_cad
    from cilindros_contiguos import certificar_recortes
    from preprocesador_stl import cargar_exacto
    from validacion_local import _distancias_cad
    import numpy as np
    import trimesh
    evidence = Path(evidence)
    old = json.loads(Path(baseline_run).read_text(encoding='utf-8'))
    hashes = tuple(map(sha, (source, candidate, baseline, baseline_run)))
    if old['source_sha256'] != hashes[0] or old['step_sha256'] != hashes[2]:
        raise ValueError('La referencia no coincide con sus hashes')
    shape = cq.importers.importStep(str(candidate)).val()
    reference = cq.importers.importStep(str(baseline)).val()
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder
    has_cylinders = lambda s: any(BRepAdaptor_Surface(f.wrapped).GetType() == GeomAbs_Cylinder for f in s.Faces())
    # El certificado de recortes cilíndricos exige cilindros. En una pieza
    # enteramente planar siguen siendo obligatorios todos los demás controles.
    domains = certificar_recortes(reference, shape) if has_cylinders(reference) or has_cylinders(shape) else []
    nonce = secrets.token_hex(24)
    final_path = evidence / 'validacion_fria.json'
    env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'OPENBLAS_NUM_THREADS': '1',
           'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1'}
    code = ejecutar([sys.executable, str(ROOT / 'validacion_fria_r19.py'), str(source), str(candidate),
                     str(baseline_run), nonce, str(final_path)], cwd=ROOT, env=env,
                    stdout=evidence / 'validacion.stdout.txt', stderr=evidence / 'validacion.stderr.txt', timeout=450)
    if code:
        raise ValueError('El STEP no supera el control frío original')
    final = json.loads(final_path.read_text(encoding='utf-8'))
    quality = verificar(final, source, candidate, nonce, ROOT)
    better, reason = _comparar_candidatos_cad(old['payload']['resultado'], dict(calidad=quality))
    if not better:
        raise ValueError(reason)
    before = old['payload']['resultado']['calidad']
    if maximo(quality) > maximo(before) + 1e-6:
        raise ValueError('Aumenta el máximo verificado de desviación')
    for key in ('tolerancia_max_mm', 'tolerancia_p95_mm'):
        if quality['integridad_cad'][key] > before['integridad_cad'][key] + 1e-9:
            raise ValueError('Aumentan las tolerancias del B-Rep')
    original = cargar_exacto(source)
    samples, _ = trimesh.sample.sample_surface(original, 1000, seed=20261023)
    points = np.vstack((original.vertices, original.triangles_center, samples))
    d0, d1 = _distancias_cad(reference, points), _distancias_cad(shape, points)
    extra = dict(muestras=len(points), maximo_base_mm=float(d0.max()), maximo_candidato_mm=float(d1.max()),
                 aumento_maximo_mm=float((d1 - d0).max()), regresiones_sobre_00001_mm=int(np.count_nonzero(d1 > d0 + .0001)),
                 source_sha256=hashes[0], baseline_sha256=hashes[2], candidate_sha256=hashes[1])
    escribir_json(evidence / 'contraste_comun.json', extra)
    if extra['regresiones_sobre_00001_mm']:
        raise ValueError('La comparación sobre puntos comunes detecta regresiones locales')
    if tuple(map(sha, (source, candidate, baseline, baseline_run))) != hashes:
        raise ValueError('Una entrada cambió durante la validación')
    return dict(accepted=True, validated=True, source_sha256=hashes[0], candidate_sha256=hashes[1],
                baseline_sha256=hashes[2], calidad=quality, final_validation=final, nonce=nonce,
                cilindros=domains, contraste_comun=extra, selection_reason=reason)
