"""Ejecuta el motor Easymeshfit V2.2 ORIGINAL (aislado de motor_superficies).

El proceso principal comprueba la geometría del candidato CAD generado y
solo acepta sólidos auténticos y geométricamente válidos.
"""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
os.environ['OMP_NUM_THREADS']='1'
os.environ['MKL_NUM_THREADS']='1'
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / 'motor_original_amigo'))
from meshfit_detect import detect
from meshfit_step import export_step
import meshfit_step
from avance_conversion import avance

def main():
    if len(sys.argv)!=3:
        raise SystemExit('Uso: motor_amigo_aislado.py origen.stl destino.step')
    src, dst = sys.argv[1:]
    recuperar = os.environ.get('VISOR_AVANCE_RECUPERACION') == '1'
    avance(82 if recuperar else 25, 'Detectando regiones con Easymeshfit original')
    res, mesh = detect(src, angle_tol_deg=32.0, rms_tol_rel=0.01,
                       flat_tol_deg=8.0, scan_mode=False)
    types = {}
    for prim in res['primitives']:
        types[prim['type']] = types.get(prim['type'],0) + 1
    print(f'[Easymeshfit original] regiones={len(res["primitives"])} '
          f'libres={len(res.get("freeform_regions",[]))} tipos={types}',flush=True)
    avance(85 if recuperar else 48, 'Construyendo el B-Rep con Easymeshfit')
    export_step(res,mesh,dst,organic=True,solid=True,organic_smooth=0.,ajuste_ia=False)
    avance(89 if recuperar else 70, 'B-Rep generado; pendiente de validación CAD')
    info = meshfit_step.LAST_INFO
    print(f'[Easymeshfit original] resultado B-Rep={info}',flush=True)
    if not (info.get('solid') and info.get('valid') and Path(dst).exists()):
        # El exportador original escribe un shell cuando falla el B-Rep;
        # JAMÁS aceptarlo silenciosamente como STEP definitivo.
        Path(dst).unlink(missing_ok=True)
        raise SystemExit(2)

if __name__ == '__main__':
    main()
