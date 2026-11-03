"""Reutilización de soportes medidos sólo tras dividir una región libre.

Se comprueban la malla completa, los objetos geométricos y la pertenencia
exacta de cada triángulo nativo. Cualquier cambio invalida la reutilización.
"""
import hashlib,numpy as np

def huella(mesh):
    return hashlib.sha256(np.asarray(mesh.vertices).tobytes()+np.asarray(mesh.faces).tobytes()).hexdigest()

def certificar(mesh,labels,surfaces,primary):
    return dict(malla=huella(mesh),primitivas={int(r):(surfaces[r],np.flatnonzero(labels==r)) for r in primary})

def valida(mesh,labels,surfaces,certificate):
    if not certificate or certificate['malla']!=huella(mesh):return False
    for region,(surface,ids) in certificate['primitivas'].items():
        if surfaces.get(region) is not surface or not np.array_equal(ids,np.flatnonzero(labels==region)):return False
    return True
