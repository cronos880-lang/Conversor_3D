"""Entrada compatible con el servidor del Visor; último renglón siempre JSON."""
import json
import sys
import traceback
from pipeline_r19 import convertir


def main():
    try:
        if len(sys.argv) != 3:
            raise ValueError('Uso: motor_r19.py entrada.stl salida_nueva.step')
        result = convertir(*sys.argv[1:])
    except Exception as exc:
        traceback.print_exc()
        result = dict(ok=False, error=str(exc), tipo_error='pipeline_r19_rechazado')
    print(json.dumps(result, ensure_ascii=True))
    return 0 if result.get('ok') is True else 2


if __name__ == '__main__':
    raise SystemExit(main())
