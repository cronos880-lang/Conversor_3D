"""Reparación sin abrir la UI, conservando el STL original.

python preparar_stl.py original.stl preparado.stl
python preparar_stl.py abierto.stl preparado.stl --referencia-cierre cerrado.stl
El cierre local exige una referencia cerrada explícita con los mismos vértices.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from preprocesador_stl import cargar_exacto, preparar, reparar_agujero_local, diagnosticar, ReparacionRechazada


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('entrada', type=Path)
    parser.add_argument('salida', type=Path)
    parser.add_argument('--referencia-cierre', type=Path)
    args = parser.parse_args()
    if args.entrada.resolve() == args.salida.resolve():
        parser.error('La salida debe ser distinta: el original se conserva.')
    if args.salida.exists():
        parser.error('La salida ya existe; elige otro nombre para conservarla.')
    report, code = {}, 0
    try:
        if args.referencia_cierre:
            original = cargar_exacto(args.entrada)
            reference = cargar_exacto(args.referencia_cierre)
            candidate, validation = reparar_agujero_local(original, reference)
            candidate.export(str(args.salida))
            reread = cargar_exacto(args.salida)
            if diagnosticar(reread)['ruta'] != 'paso_directo':
                raise ValueError('La serialización no conserva el cierre.')
            report = {'reparado': True, 'ruta_seleccionada': 'cierre_local_referencia_explicita',
                      'entrada': diagnosticar(original), 'salida': diagnosticar(reread),
                      'validacion': validation,
                      'original_sha256': hashlib.sha256(args.entrada.read_bytes()).hexdigest(),
                      'referencia_sha256': hashlib.sha256(args.referencia_cierre.read_bytes()).hexdigest()}
        else:
            selected, report = preparar(args.entrada, args.salida)
            if selected == args.entrada:
                shutil.copyfile(selected, args.salida)
    except Exception as exc:
        args.salida.unlink(missing_ok=True)
        report = exc.informe if isinstance(exc, ReparacionRechazada) else report
        report.update(ok=False, error=str(exc))
        code = 2
    report.setdefault('ok', True)
    report_path = args.salida.with_suffix('.reparacion.json')
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
