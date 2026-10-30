"""Proponer una limpieza bajo la resolución CAD, sólo después de reparar.

No modifica STL sanos en el paso directo. No relaja los controles de la
reparación ni del STEP. Un rechazo conserva la malla anterior íntegra.
"""
from pathlib import Path
import tempfile
import numpy as np
import trimesh

LIMITE_PROPUESTA_MM=1e-7


def normalizar(mesh):
    record=dict(aplicado=False,limite_propuesta_mm=LIMITE_PROPUESTA_MM,
                cambia_limites_reparacion=False,cambia_limites_step=False)
    if len(mesh.faces)>20000 or not np.any(mesh.edges_unique_length<2e-7):
        return mesh,record
    try:
        from preprocesador_stl import _manifold
        from reparador_exacto_aislado import ControlExacto,medidas_superficie,validar_material
        from topologia_vertices import inspeccionar_vertices
        if not mesh.is_watertight or not mesh.is_winding_consistent or inspeccionar_vertices(mesh)['vertices_no_manifold']:
            raise ValueError('La normalización requiere una frontera ya reparada')
        if len(mesh.split(only_watertight=False))!=1:raise ValueError('La normalización no actúa sobre varios cuerpos')
        with tempfile.TemporaryDirectory(prefix='visor_microcaras_') as tmp:
            tmp=Path(tmp)
            if ControlExacto(mesh,tmp/'antes.off').pares():raise ValueError('La referencia conserva cruces')
            data=_manifold(mesh).simplify(LIMITE_PROPUESTA_MM).to_mesh64()
            points,inverse=np.unique(data.vert_properties[:,:3],axis=0,return_inverse=True)
            candidate=trimesh.Trimesh(points,inverse[data.tri_verts],process=False)
            if (not candidate.is_watertight or not candidate.is_winding_consistent or
                candidate.euler_number!=mesh.euler_number or len(candidate.split(only_watertight=False))!=1 or
                inspeccionar_vertices(candidate)['vertices_no_manifold'] or ControlExacto(candidate,tmp/'despues.off').pares()):
                raise ValueError('La limpieza no conserva topología, orientación o ausencia de cruces')
            from reparacion_contactos_locales import compactar_aristas_cortas
            def enlace_valido(proposal):
                return (len(proposal.split(only_watertight=False))==1 and
                        not inspeccionar_vertices(proposal)['vertices_no_manifold'] and
                        not ControlExacto(proposal,tmp/'enlace.off').pares())
            candidate,links=compactar_aristas_cortas(candidate,limite_mm=LIMITE_PROPUESTA_MM,
                                                   validar=enlace_valido,max_colapsos=64,probar_punto_medio=True)
            if len(candidate.faces)>=len(mesh.faces):return mesh,record
            if candidate.euler_number!=mesh.euler_number:raise ValueError('La compactación cambia la topología')
            record['compactacion_enlace']=links
            proof=medidas_superficie(mesh,candidate)
            box=float(np.abs(candidate.bounds-mesh.bounds).max())
            volume_error=100*abs(candidate.volume/mesh.volume-1) if mesh.volume>0 else float('inf')
            # La cota de simplificación no sustituye a esta medición independiente.
            if proof['max_mm']>LIMITE_PROPUESTA_MM or box>LIMITE_PROPUESTA_MM or volume_error>.001:
                raise ValueError('La propuesta sale de su banda nanométrica')
            material=validar_material(mesh,candidate,[])
            record.update(aplicado=True,caras_antes=len(mesh.faces),caras_despues=len(candidate.faces),
                          geometria=proof,caja_error_mm=box,euler_antes=int(mesh.euler_number),euler_despues=int(candidate.euler_number),
                          volumen_error_pct=volume_error,material=material,
                          intersecciones_exactas_antes=0,intersecciones_exactas_despues=0,
                          referencia='Malla reparada anterior; muestreo independiente, no prueba global de Hausdorff')
            return candidate,record
    except (ValueError,RuntimeError) as exc:
        record['rechazo']=str(exc)
        return mesh,record
