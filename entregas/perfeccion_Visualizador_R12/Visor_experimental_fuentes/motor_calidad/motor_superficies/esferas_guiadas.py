"""Esferas verificadas mediante cotas de TODOS los interiores triangulares.

La norma máxima sobre un triángulo está en sus vértices. La mínima se calcula
como distancia exacta del centro al triángulo, incluyendo su interior.
"""
import numpy as np,trimesh
from OCP.BRep import BRep_Tool
from OCP.Geom import Geom_SphericalSurface
from OCP.gp import gp_Ax3,gp_Pnt,gp_Dir

def cota_triangulos(mesh,centro,radio):
    T=mesh.triangles;c=np.asarray(centro,float)
    maximum=np.linalg.norm(T-c,axis=2).max(axis=1)
    closest=trimesh.triangles.closest_point(T,np.repeat(c[None,:],len(T),axis=0))
    minimum=np.linalg.norm(closest-c,axis=1)
    return np.maximum(maximum-radio,radio-minimum)

def propuestas(faces,mesh,required):
    out=[];proof=[];total=float(mesh.area_faces.sum());used=[]
    for i,face in enumerate(faces):
        s=BRep_Tool.Surface_s(face.wrapped)
        if not isinstance(s,Geom_SphericalSurface) or face.Area()<total*.001:continue
        c=np.array(s.Location().Coord());rad=float(s.Radius())
        if any(abs(rad-r)<1e-7 and np.linalg.norm(c-q)<1e-7 for q,r in used):continue
        error=cota_triangulos(mesh,c,rad);C=mesh.triangles_center;D=C-c;N=D/np.maximum(np.linalg.norm(D,axis=1)[:,None],1e-300)
        bb=face.BoundingBox();lo=np.array([bb.xmin,bb.ymin,bb.zmin]);hi=np.array([bb.xmax,bb.ymax,bb.zmax])
        mask=(error<=.003)&(abs(np.sum(N*mesh.face_normals,axis=1))>np.cos(np.radians(15)))&np.all((C>=lo-.001)&(C<=hi+.001),axis=1)
        ids=np.flatnonzero(mask)
        if len(ids)<12 or mesh.area_faces[ids].sum()<max(.5*face.Area(),total*.001):continue
        # Parametrización coaxial cuando la propia fuente confirma un eje.
        candidates=[r for r in required if r['radio']<=rad+.008 and np.linalg.norm(np.cross(c-r['centro'],r['eje']))<1e-5]
        axis=np.array(max(candidates,key=lambda r:r['radio'])['eje']) if candidates else np.array(s.Axis().Direction().Coord())
        surface=Geom_SphericalSurface(gp_Ax3(gp_Pnt(*map(float,c)),gp_Dir(*map(float,axis))),rad)
        out.append((ids,surface));used.append((c,rad))
        rec=dict(cara_hipotesis=i,radio=rad,centro=c.tolist(),eje_parametrico=axis.tolist(),triangulos=len(ids),area_fuente_mm2=float(mesh.area_faces[ids].sum()),cota_triangulos_mm=float(error[ids].max()),limite_mm=.003)
        proof.append(rec);print('ESFERA GUIADA CERTIFICADA',rec,flush=True)
    return out,proof
