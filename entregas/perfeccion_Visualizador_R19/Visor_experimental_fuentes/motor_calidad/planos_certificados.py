"""Reconocer soportes B-spline planos con cota de todos sus polos.

Sólo investigación: las curvas 3D, agujeros y tolerancias de aristas se
conservan. La aceptación final contra el STL es independiente y obligatoria.
"""
from pathlib import Path
import sys,json,hashlib,time
import numpy as np
import cadquery as cq
from OCP.Geom import Geom_BSplineSurface,Geom_Plane
from OCP.GeomAPI import GeomAPI
from OCP.BRep import BRep_Tool,BRep_Builder
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepBuilderAPI import BRepBuilderAPI_Sewing,BRepBuilderAPI_MakeSolid
from OCP.BRepLib import BRepLib
from OCP.TopoDS import TopoDS_Face
from OCP.gp import gp_Ax3,gp_Pnt,gp_Dir
from OCP.ShapeFix import ShapeFix_Face
from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain

LIMITE_POLOS_MM=2e-8
LIMITE_PCURVA_MM=5e-8

def soporte_plano(surface):
    if not isinstance(surface,Geom_BSplineSurface):return None
    points=np.array([surface.Pole(i,j).Coord() for i in range(1,surface.NbUPoles()+1) for j in range(1,surface.NbVPoles()+1)])
    weights=np.array([surface.Weight(i,j) for i in range(1,surface.NbUPoles()+1) for j in range(1,surface.NbVPoles()+1)])
    if not np.isfinite(points).all() or np.any(weights<=0):return None
    origin=points.mean(0);_,s,V=np.linalg.svd(points-origin,full_matrices=False)
    if len(s)<3 or s[1]<1e-10:return None
    error=float(abs((points-origin)@V[-1]).max())
    if error>LIMITE_POLOS_MM:return None
    plane=Geom_Plane(gp_Ax3(gp_Pnt(*origin),gp_Dir(*V[-1]),gp_Dir(*V[0])))
    return plane,error

def exacto(shape):
    a=BRepCheck_Analyzer(shape,True);a.SetExactMethod(True);return bool(a.IsValid())

def convertir(shape,module_dir):
    sys.path[:0]=[str(module_dir.parent),str(module_dir)]
    from pcurvas_compartidas import _error
    faces=shape.Faces();new=[];records=[]
    for i,old in enumerate(faces):
        surface=BRep_Tool.Surface_s(old.wrapped);proposal=soporte_plano(surface)
        if proposal is None:new.append(old);continue
        plane,bound=proposal;info=dict(cara=i,cota_convexa_polos_mm=bound,ok=False)
        try:
            face=TopoDS_Face();builder=BRep_Builder();builder.MakeFace(face,plane,1e-7)
            for wire in old.Wires():builder.Add(face,wire.wrapped)
            maximum=0.
            for edge in old.Edges():
                curve=BRep_Tool.Curve_s(edge.wrapped,0.,0.);lo,hi=BRep_Tool.Range_s(edge.wrapped)
                uv=GeomAPI.To2d_s(curve,plane.Pln());error=_error(curve,uv,plane,lo,hi)
                maximum=max(maximum,error)
                if error>LIMITE_PCURVA_MM:raise ValueError('La curva frontera no pertenece al plano: '+str(error))
                builder.UpdateEdge(edge.wrapped,uv,face,BRep_Tool.Tolerance_s(edge.wrapped))
                builder.Range(edge.wrapped,face,lo,hi)
            fix=ShapeFix_Face(face);fix.SetPrecision(1e-7);fix.SetMaxTolerance(1e-7);fix.FixOrientation();face=fix.Face();built=cq.Face(face)
            if built.normalAt(old.Center()).dot(old.normalAt(old.Center()))<0:face.Reverse();built=cq.Face(face)
            if not exacto(face):raise ValueError('La cara plana no pasa CAD exacto')
            new.append(built);info.update(ok=True,pcurva_max_mm=maximum,contornos=len(old.Wires()))
        except Exception as exc:new.append(old);info['error']=str(exc)
        records.append(info)
    if not any(r['ok'] for r in records):raise ValueError('No hay parches planos certificados para sustituir')
    sewing=BRepBuilderAPI_Sewing(1e-7,True,True,True,False)
    for f in new:sewing.Add(f.wrapped)
    sewing.Perform();shells=cq.Shape.cast(sewing.SewedShape()).Shells()
    if len(shells)!=1:raise ValueError('La sustitución no conserva un único shell')
    solid=BRepBuilderAPI_MakeSolid(shells[0].wrapped).Solid();BRepLib.OrientClosedSolid_s(solid)
    if not exacto(solid):raise ValueError('La sustitución no conserva CAD exacto')
    unifier=ShapeUpgrade_UnifySameDomain(solid,True,True,False);unifier.SetLinearTolerance(1e-7);unifier.SetAngularTolerance(1e-8)
    # Sólo reunir planos. Los contornos de cilindros y otras primitivas quedan protegidos.
    for f in cq.Shape.cast(solid).Faces():
        if not isinstance(BRep_Tool.Surface_s(f.wrapped),Geom_Plane):
            for edge in f.Edges():unifier.KeepShape(edge.wrapped)
    unifier.Build();result=cq.Shape.cast(unifier.Shape())
    if not exacto(result.wrapped) or len(result.Solids())!=1:raise ValueError('La reunión de planos no conserva un sólido exacto')
    return result,records

if __name__=='__main__':
    source,destination,report,module_dir=map(Path,sys.argv[1:]);start=time.monotonic();record={'ok':False}
    if destination.exists() or len({p.resolve() for p in (source,destination,report)})!=3:raise SystemExit('Las salidas deben ser nuevas y distintas')
    before=hashlib.sha256(source.read_bytes()).hexdigest()
    try:
        shape,proof=convertir(cq.importers.importStep(str(source)).val(),module_dir)
        cq.exporters.export(shape,str(destination));record.update(ok=True,caras=len(shape.Faces()),sustituciones=proof,source_sha256=before,step_sha256=hashlib.sha256(destination.read_bytes()).hexdigest())
    except Exception as exc:
        import traceback;traceback.print_exc();record['error']=str(exc)
    assert before==hashlib.sha256(source.read_bytes()).hexdigest()
    record['segundos']=time.monotonic()-start;report.write_text(json.dumps(record,indent=2));print(record,flush=True)
