"""Reproducir las costuras certificadas y la lectura heredada sin tapar huecos."""
import numpy as np
import trimesh

def normalizar_cierre(mesh):
    if mesh.is_watertight and mesh.is_winding_consistent:return mesh,None
    from saneamiento_malla import quitar_redundancias,resolver_costuras
    candidate,cleaning=quitar_redundancias(mesh)
    candidate,seams=resolver_costuras(candidate)
    proof={'redundancias':cleaning,'costuras':seams,
           'fundamento':'Certificado regenerado desde la referencia; no se añade ninguna tapa.'}
    if (cleaning['aplicado'] or seams['aplicado']) and candidate.is_watertight and candidate.is_winding_consistent:
        return candidate,proof
    # R7 ya admite esta lectura process=True. Aquí se verifica además que sólo
    # reúna coordenadas al redondeo heredado, conservando TODAS las facetas.
    legacy=trimesh.Trimesh(mesh.vertices.copy(),mesh.faces.copy(),process=True,validate=False)
    before=np.asarray(mesh.triangles);after=np.asarray(legacy.triangles)
    limit=float(trimesh.constants.tol.merge)
    if before.shape!=after.shape or not legacy.is_watertight or not legacy.is_winding_consistent:
        raise ValueError('No hay cierre certificado para esta referencia; no se permite tapar un agujero.')
    movement=float(np.max(np.abs(before-after)))
    if movement>limit:
        raise ValueError('La lectura heredada desplaza las facetas más que su redondeo original.')
    from preprocesador_stl import diagnosticar
    if diagnosticar(legacy)['topologia_vertices']['vertices_no_manifold']:
        raise ValueError('El redondeo de la referencia conserva contactos ambiguos entre caras.')
    proof['lectura_heredada']={'aplicado':True,'caras_antes':len(mesh.faces),'caras_despues':len(legacy.faces),
        'max_movimiento_coordenada_mm':movement,'limite_redondeo_heredado_mm':limit,
        'cota_superficie_mm':float(np.max(np.linalg.norm(before-after,axis=2))),
        'sin_caras_de_tapa':True,'caras_eliminadas':0,'limites_aceptacion_modificados':False}
    return legacy,proof
