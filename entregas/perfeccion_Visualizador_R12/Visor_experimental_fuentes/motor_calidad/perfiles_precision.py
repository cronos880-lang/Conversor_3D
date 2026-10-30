"""Perfiles explícitos: el perfil histórico sigue siendo el predeterminado.

Impresión es un presupuesto de error CAD, no una garantía de precisión de una
impresora. Los controles de material, cavidades y topología no se desactivan.
"""
import os

PERFILES = {
    'precision': {'nombre': 'Precisión', 'caja_mm': .020, 'p95_mm': None,
                  'max_mm': .060, 'volumen_pct': .5},
    'impresion': {'nombre': 'Impresión 0,08 mm', 'caja_mm': .040, 'p95_mm': .040,
                  'max_mm': .080, 'volumen_pct': .5},
}


def obtener_perfil(nombre=None):
    key = os.environ.get('VISOR_PERFIL', 'precision') if nombre is None else nombre
    if key not in PERFILES:
        raise ValueError('Perfil desconocido; elige precision o impresion.')
    return {'id': key, **PERFILES[key]}
