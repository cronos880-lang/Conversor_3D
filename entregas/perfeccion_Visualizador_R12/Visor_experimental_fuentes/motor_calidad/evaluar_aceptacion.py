"""Puerta de aceptación: exige las 14 piezas, cubo-carrito y evidencia Windows.

No convierte pruebas ausentes, tiempos agotados ni fallos heredados en éxito.
Cada STEP aceptado se reimporta otra vez de forma independiente.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import cadquery as cq
from OCP.BRepCheck import BRepCheck_Analyzer


def reimportar(path):
    root = cq.importers.importStep(str(path)).val()
    solids = root.Solids()
    valid = bool(BRepCheck_Analyzer(root.wrapped, True).IsValid())
    return {'valido': valid, 'solidos': len(solids), 'caras': len(root.Faces()),
            'volumen_mm3': sum(s.Volume() for s in solids)}


def comparar_quality(before, after):
    reasons = []
    for key in ['caras_step', 'volumen_error_pct', 'caja_error_mm']:
        if after[key] > before[key]+1e-6:
            reasons.append(f'{key}: {before[key]} -> {after[key]}')
    for key in ['tolerancia_max_mm', 'tolerancia_p95_mm']:
        if after['integridad_cad'][key] > before['integridad_cad'][key]+1e-7:
            reasons.append(f'{key} empeora')
    for direction in ['distancia_stl_step_mm', 'distancia_step_stl_mm']:
        for metric in ['p95', 'max_muestreado']:
            if after[direction][metric] > before[direction][metric]+1e-6:
                reasons.append(f'{direction}/{metric} empeora')
    if after['limites_validacion'] != before['limites_validacion']:
        reasons.append('Los límites de validación cambian')
    return reasons


def evaluar(base, experimental, cube, *, pruebas=None, windows=False, onshape=False):
    reasons, rows = [], []
    before = json.loads((base/'bateria.json').read_text())['resultados']
    after = json.loads((experimental/'bateria.json').read_text())['resultados']
    by_name = {r['archivo']: r for r in before}
    if len(before) != 14 or len(after) != 14 or set(by_name) != {r['archivo'] for r in after}:
        reasons.append('Batería incompleta: se exigen las 14 piezas idénticas antes y después.')
    for row in after:
        old = by_name.get(row['archivo'])
        verdict = {'archivo': row['archivo'], 'referencia_ok': bool(old and old['ok']),
                   'experimental_ok': row['ok'], 'regresiones': []}
        if not old or old['sha256'] != row['sha256']:
            verdict['regresiones'].append('No coincide el STL de referencia')
        elif not old['ok'] or not row['ok']:
            reasons.append(row['archivo']+': la conversión completa no pasa en ambas copias.')
        else:
            verdict['regresiones'] = comparar_quality(old['informe_motor']['resultado']['calidad'],
                                                       row['informe_motor']['resultado']['calidad'])
        if row['ok']:
            try:
                step = experimental/(Path(row['archivo']).stem+'.step')
                if hashlib.sha256(step.read_bytes()).hexdigest() != row.get('sha256_step'):
                    verdict['regresiones'].append('El STEP actual no coincide con el que produjo las métricas guardadas.')
                verdict['reimportacion_independiente'] = checked = reimportar(step)
                if not checked['valido'] or checked['solidos'] != 1:
                    verdict['regresiones'].append('La reimportación independiente no es un sólido válido.')
                if checked['caras'] != row['informe_motor']['resultado']['calidad']['caras_step']:
                    verdict['regresiones'].append('El número de caras reimportado no coincide con el validado.')
            except Exception as exc:
                verdict['regresiones'].append('Falló la reimportación: '+str(exc))
        if verdict['regresiones']:
            reasons.append(row['archivo']+': '+', '.join(verdict['regresiones']))
        rows.append(verdict)
    cube_report = None
    if cube and cube.is_file():
        cube_report = json.loads(cube.read_text())
    if not cube_report or not cube_report.get('ok'):
        reasons.append('Cubo-carrito: falta una conversión STEP completa que pase los controles.')
    else:
        cube_step = cube.with_name(cube.name.replace('.resultado.json', '.step'))
        checked = reimportar(cube_step)
        if not checked['valido'] or checked['solidos'] != 1:
            reasons.append('El STEP del cubo-carrito no pasa reimportación independiente.')
    if not windows:
        reasons.append('Pruebas nativas Windows pendientes; disponibilidad de wheels no equivale a ejecución.')
    unit_report = None
    try:
        cases = list(ET.parse(pruebas).getroot().iter('testcase')) if pruebas else []
        unit_report = {'casos': len(cases), 'fallidos': sum(c.find('failure') is not None or c.find('error') is not None for c in cases),
                       'omitidos': sum(c.find('skipped') is not None for c in cases)}
        if len(cases) < 35 or unit_report['fallidos'] or unit_report['omitidos']:
            reasons.append('Faltan 35 pruebas de topología, reparación, rotaciones y API sin fallos ni omisiones.')
    except (OSError, ET.ParseError) as exc:
        reasons.append('No se pudo leer la evidencia de pruebas: '+str(exc))
    return {'apto_para_entrega_validada': not reasons, 'motivos_bloqueo': reasons,
            'comparacion_14': rows, 'windows_ejecutado': windows,
            'pruebas': unit_report,
            'onshape_move_face_ejecutado': onshape,
            'nota_onshape': 'La editabilidad Move face requiere prueba funcional externa.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--referencia', type=Path, required=True)
    parser.add_argument('--experimental', type=Path, required=True)
    parser.add_argument('--cubo', type=Path)
    parser.add_argument('--pruebas', type=Path, help='JUnit XML de las 35 pruebas, incluidos los STL reales')
    parser.add_argument('--salida', type=Path, required=True)
    args = parser.parse_args()
    report = evaluar(args.referencia, args.experimental, args.cubo, pruebas=args.pruebas)
    args.salida.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report['apto_para_entrega_validada'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
