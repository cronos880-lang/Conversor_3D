"""Unir regiones suaves mediante un único campo de alturas medido del STL.

Se conservan las primitivas analíticas ya respaldadas y todas las aristas
fuente de más de 15 grados. Sólo se proponen dominios que son grafos suaves.
La aceptación geométrica y CAD completa sigue siendo externa.
"""
import numpy as np
from OCP.Geom import Geom_Plane,Geom_BSplineSurface,Geom_CylindricalSurface,Geom_SurfaceOfLinearExtrusion
from restos_planos import componentes,plano_exacto,altura_medida

def proponer(mesh,labels,surfaces):
    import meshfit_brep as base
    labels=labels.copy();out=dict(surfaces);groups=base._groups(labels)
    protected=np.zeros(len(mesh.faces),bool);candidates=[];sweep_axes=[]
    for surface in surfaces.values():
        if isinstance(surface,(Geom_CylindricalSurface,Geom_SurfaceOfLinearExtrusion)):
            a=np.array(surface.Axis().Direction().Coord()) if isinstance(surface,Geom_CylindricalSurface) else np.array(surface.Direction().Coord())
            if not any(abs(a@b)>.999999 for b in sweep_axes):sweep_axes.append(a)
        elif isinstance(surface,Geom_Plane):
            a=np.array(surface.Axis().Direction().Coord())
            if not any(abs(a@b)>.999999 for b in sweep_axes):sweep_axes.append(a)
    for l,ids in groups.items():
        s=surfaces[l]
        if id(s) in getattr(mesh,"hipotesis_no_primarias",set()):
            protected[ids]=True;continue
        if isinstance(s,Geom_Plane):
            if len(ids)>=2:
                candidates.append((float(mesh.area_faces[ids].sum()),np.array(s.Axis().Direction().Coord())))
                P=mesh.vertices[np.unique(mesh.faces[ids])];n=np.array(s.Axis().Direction().Coord());origin=np.array(s.Location().Coord())
                if np.max(abs((P-origin)@n))<=1e-4:protected[ids]=True
        elif not isinstance(s,Geom_BSplineSurface):
            P=np.vstack([mesh.vertices[np.unique(mesh.faces[ids])],mesh.triangles_center[ids]])
            error=np.linalg.norm((__import__("proyector_perfil",fromlist=["ProyectorPerfil"]).ProyectorPerfil(s) if isinstance(s,Geom_SurfaceOfLinearExtrusion) else base._Proj(s)).batch(P)-P,axis=1)
            if np.isfinite(error).all() and error.max()<=.008:protected[ids]=True
    axes=[]
    for weight,n in sorted(candidates,key=lambda p:-p[0]):
        if any(abs(n@other)>.999 for other in axes):continue
        axes.append(n)
        if len(axes)>=12:break
    proof={};next_label=int(labels.max())+1
    # Medir ambos lados; una placa puede tener dos superficies distintas.
    for axis in axes:
        for sign in (1.,-1.):
            n=axis*sign;ids=np.flatnonzero((mesh.face_normals@n>np.cos(np.radians(20)))&~protected)
            for part in sorted(componentes(mesh,ids),key=lambda f:-mesh.area_faces[f].sum()):
                if len(part)<12 or len(part)>10000 or mesh.area_faces[part].sum()<.1:continue
                exact=plano_exacto(mesh,part);native=None;native_proof=None
                if exact is None:
                    try:
                        from barridos_medidos import ajustar
                        from proyector_perfil import ProyectorPerfil
                        proposal,indices,native_proof=ajustar(None,None,mesh,sweep_axes,source_ids=part)
                        if len(indices)!=len(part):raise ValueError('El perfil no cubre el campo completo')
                        P=np.vstack([mesh.vertices[np.unique(mesh.faces[part])],mesh.triangles_center[part]])
                        maximum=float(np.linalg.norm(ProyectorPerfil(proposal).batch(P)-P,axis=1).max())
                        if maximum>.003:raise ValueError('El perfil no conserva todos los testigos del campo')
                        native=proposal;native_proof.update(max_testigos_campo_mm=maximum)
                    except Exception as exc:
                        print("CAMPO: PERFIL DESCARTADO",str(exc),flush=True);native=None
                fit=None if exact is not None or native is not None else altura_medida(mesh,part)
                if exact is None and native is None and fit is None:continue
                old=np.unique(labels[part])
                if exact is not None and len(old)==1:continue
                surface=exact if exact is not None else (native if native is not None else fit[0])
                labels[part]=next_label;out[next_label]=surface;protected[part]=True
                if fit is not None:proof[next_label]=fit[1]
                print('CAMPO FUENTE',dict(region=next_label,regiones_fuente=len(old),triangulos=len(part),tipo=type(surface).__name__,prueba=fit[1] if fit else native_proof),flush=True)
                next_label+=1
    mesh.parches_altura_medidos=proof
    return labels,out
