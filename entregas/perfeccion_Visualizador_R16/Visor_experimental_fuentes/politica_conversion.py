"""Tiempo por número de triángulos, con ampliación acotada si hay actividad CPU."""
import struct
import re


def presupuesto_conversion(data):
    count=0
    if len(data)>=84:
        declared=struct.unpack_from('<I',data,80)[0]
        if declared and 84+50*declared<=len(data):count=declared
    if not count:
        count=len(re.findall(rb'\bfacet\s+normal\b',data,flags=re.I))
    # No confundir un STL ASCII con uno binario ni equiparar bytes a dificultad.
    if not count:raise ValueError('No se reconoce una malla STL con triángulos.')
    initial=420 if count<=5000 else 600 if count<=20000 else 900 if count<=100000 else 1200
    # R14: las operaciones CAD de entradas >100k necesitan también
    # exportación exacta, tres mallados y contraste del original.
    # Sólo cambia el presupuesto de tiempo, no un límite geométrico.
    # Se conserva el plazo inicial y sólo se amplía con actividad CPU.
    return {'triangulos':count,'inicial_s':initial,'maximo_s':3600 if count>100000 else min(2400,max(1800,initial*2)),
            'ampliar_si_cpu_activa':True,'incremento_s':30,
            'criterio':'Triángulos y actividad CPU; nunca superar el máximo absoluto.'}
