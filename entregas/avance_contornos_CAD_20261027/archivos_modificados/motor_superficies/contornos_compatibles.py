"""Construcción experimental de encuentros compartidos, con geometría compatible.

No modifica la entrada ni los límites de aceptación del Visor. Debe ejecutarse en
el trabajador vigilado y superar la validación externa de la conversión.
"""
import math,time,collections
import numpy as np
from OCP.gp import gp_Pnt,gp_Pnt2d,gp_Pln,gp_Dir,gp_Ax2
from OCP.Geom import Geom_Plane,Geom_BSplineSurface,Geom_TrimmedCurve,Geom_CylindricalSurface,Geom_Ellipse
from OCP.GeomAPI import GeomAPI_IntSS,GeomAPI_ProjectPointOnCurve,GeomAPI_Interpolate
from OCP.Geom2dAPI import Geom2dAPI_Interpolate
from OCP.TColgp import TColgp_HArray1OfPnt,TColgp_HArray1OfPnt2d,TColgp_Array1OfPnt
from OCP.TColStd import TColStd_HArray1OfReal,TColStd_Array1OfReal,TColStd_Array1OfInteger
from OCP.BRep import BRep_Builder,BRep_Tool
from OCP.BRepLib import BRepLib
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
from OCP.TopoDS import TopoDS,TopoDS_Edge,TopoDS_Vertex,TopoDS_Face,TopoDS_Wire,TopoDS_Shell
from OCP.TopAbs import TopAbs_FORWARD,TopAbs_REVERSED
from OCP.GeomConvert import GeomConvert,GeomConvert_CompCurveToBSplineCurve
from OCP.GeomFill import GeomFill_BSplineCurves,GeomFill_StretchStyle
from OCP.GeomAdaptor import GeomAdaptor_Curve
from OCP.GeomPlate import GeomPlate_BuildPlateSurface,GeomPlate_CurveConstraint,GeomPlate_PointConstraint,GeomPlate_MakeApprox

def _point(p):return gp_Pnt(*map(float,p))

def acondicionar_conica(curve,first,last):
    if not isinstance(curve,Geom_Ellipse) or curve.MajorRadius()/curve.MinorRadius()<1000 or last-first>.01:
        return curve,first,last
    # Cono racional cuadrático de tres polos. Evaluar la elipse con mayor
    # precisión evita restar dos coordenadas de cientos de millones de mm.
    center=np.array(curve.Location().Coord(),dtype=np.longdouble)
    x=np.array(curve.Position().XDirection().Coord(),dtype=np.longdouble)
    y=np.array(curve.Position().YDirection().Coord(),dtype=np.longdouble)
    major=np.longdouble(curve.MajorRadius());minor=np.longdouble(curve.MinorRadius())
    lo,hi=np.longdouble(first),np.longdouble(last);mid=(lo+hi)/2;half=(hi-lo)/2
    def value(t):return center+major*np.cos(t)*x+minor*np.sin(t)*y
    p0,p2,pm=value(lo),value(hi),value(mid);weight=np.cos(half)
    p1=pm+(pm-(p0+p2)/2)/weight
    poles=TColgp_Array1OfPnt(1,3);weights=TColStd_Array1OfReal(1,3)
    for i,(point,w) in enumerate(zip((p0,p1,p2),(1,weight,1))):poles.SetValue(i+1,_point(point));weights.SetValue(i+1,float(w))
    knots=TColStd_Array1OfReal(1,2);mult=TColStd_Array1OfInteger(1,2)
    knots.SetValue(1,0.);knots.SetValue(2,1.);mult.SetValue(1,3);mult.SetValue(2,3)
    from OCP.Geom import Geom_BSplineCurve
    result=Geom_BSplineCurve(poles,weights,knots,mult,2,False)
    maximum=0.
    for fraction in np.linspace(0,1,129):
        t=lo+(hi-lo)*np.longdouble(fraction)
        u=(1+np.tan((t-mid)/2)/np.tan(half/2))/2
        maximum=max(maximum,float(np.linalg.norm(np.array(result.Value(float(u)).Coord(),dtype=np.longdouble)-value(t))))
    if maximum>5e-8:raise ValueError('La representación local de la cónica no conserva su geometría.')
    print('[contornos] cónica condicionada',curve.MajorRadius(),curve.MinorRadius(),'error_mm',maximum,flush=True)
    return result,0.,1.

def _residual_normal(projector,points):
    if projector.kind=='plane':
        return (points-projector.q)@projector.a,np.broadcast_to(projector.a,points.shape)
    if projector.kind in ('cyl','sph'):
        radial=points-projector.q
        if projector.kind=='cyl':radial-=np.outer(radial@projector.a,projector.a)
        distance=np.linalg.norm(radial,axis=1)
        return distance-projector.R,radial/np.maximum(distance[:,None],1e-15)
    displacement=points-projector.batch(points);distance=np.linalg.norm(displacement,axis=1)
    return distance,displacement/np.maximum(distance[:,None],1e-15)

def refinar_interseccion(curve,first,last,sa,sb,max_move):
    """Corregir la aproximación3D del intersector, sin modificar sus soportes."""
    import meshfit_brep as base
    projectors=[base._Proj(s) for s in (sa,sb)]
    if any(p.kind not in ('plane','cyl','sph') for p in projectors):return curve,first,last
    if all(p.kind=='plane' for p in projectors):return curve,first,last
    initial=np.array([curve.Value(float(t)).Coord() for t in np.linspace(first,last,257)])
    if max(np.max(np.abs(_residual_normal(p,initial)[0])) for p in projectors)<=1e-10:
        return curve,first,last
    closed=curve.Value(first).Distance(curve.Value(last))<1e-7
    parameters=np.linspace(first,last,65)
    working=curve;total_movement=0.
    for iteration in range(10):
        reference=np.array([working.Value(float(t)).Coord() for t in parameters]);points=reference.copy()
        for _ in range(15):
            f,n=_residual_normal(projectors[0],points);g,m=_residual_normal(projectors[1],points)
            if max(np.max(np.abs(f)),np.max(np.abs(g)))<1e-11:break
            dot=np.einsum('ij,ij->i',n,m);det=1-dot**2
            bad=(det<1e-10)&(np.maximum(np.abs(f),np.abs(g))>1e-10)
            if bad.any():raise ValueError('La intersección tangente no admite una corrección estable.')
            det=np.maximum(det,1e-10)
            da=(f-dot*g)/det;db=(g-dot*f)/det
            points-=da[:,None]*n+db[:,None]*m
        total_movement+=float(np.linalg.norm(points-reference,axis=1).max())
        if total_movement>max_move:
            raise ValueError('La intersección refinada requiere desplazar demasiado el contorno.')
        if closed:points[-1]=points[0]
        if iteration==0:
            parameters=np.r_[0.,np.cumsum(np.linalg.norm(np.diff(points,axis=0),axis=1))]
            parameters/=parameters[-1];first,last=0.,1.
        count=len(points)-int(closed);array=TColgp_HArray1OfPnt(1,count)
        params=TColStd_HArray1OfReal(1,len(parameters))
        for i,p in enumerate(points[:count]):array.SetValue(i+1,_point(p))
        for i,t in enumerate(parameters):params.SetValue(i+1,float(t))
        interpolation=GeomAPI_Interpolate(array,params,closed,1e-12);interpolation.Perform()
        if not interpolation.IsDone():raise ValueError('No se aproxima la intersección común refinada.')
        result=interpolation.Curve()
        probes=np.concatenate([a+(b-a)*np.linspace(0,1,9) for a,b in zip(parameters[:-1],parameters[1:])])
        values=np.array([result.Value(float(t)).Coord() for t in probes])
        errors=np.maximum(np.abs(_residual_normal(projectors[0],values)[0]),np.abs(_residual_normal(projectors[1],values)[0]))
        print('[contornos] refinamiento3D',iteration,len(parameters),'puntos, error',float(errors.max()),flush=True)
        if errors.max()<=3e-8:return result,first,last
        # Refinar sólo los intervalos que no cumplen la precisión numérica.
        bad=np.flatnonzero(errors.reshape(-1,9).max(axis=1)>3e-8)
        parameters=np.sort(np.r_[parameters,(parameters[bad]+parameters[bad+1])*.5])
        working=result
        if len(parameters)>4097:break
    raise ValueError('La curva3D de intersección no alcanza la precisión numérica requerida.')

def _interseccion(sa,sb,points,max_move,closed):
    operation=GeomAPI_IntSS(sa,sb,1e-8)
    candidates=[];diagnostic=[]
    if not operation.IsDone():raise ValueError('La intersección entre superficies no converge.')
    samples=points[np.linspace(0,len(points)-1,min(17,len(points))).astype(int)]
    lines=[operation.Line(index) for index in range(1,operation.NbLines()+1)]
    planes=[s for s in (sa,sb) if isinstance(s,Geom_Plane)]
    cylinders=[s for s in (sa,sb) if isinstance(s,Geom_CylindricalSurface)]
    if len(planes)==len(cylinders)==1:
        # Fórmula exacta: el intersector puede aproximar por un círculo una
        # sección levemente oblicua. Mantener la oblicuidad medida en el STL.
        plane=planes[0].Pln();cylinder=cylinders[0]
        n=np.array(plane.Axis().Direction().Coord());p=np.array(plane.Location().Coord())
        a=np.array(cylinder.Axis().Direction().Coord());q=np.array(cylinder.Location().Coord())
        if abs(n@a)>1e-4:
            x=np.array(cylinder.Position().XDirection().Coord());y=np.array(cylinder.Position().YDirection().Coord())
            center=q+a*((n@(p-q))/(n@a))
            matrix=cylinder.Radius()*np.column_stack((x-a*(n@x)/(n@a),y-a*(n@y)/(n@a)))
            directions,radii,_=np.linalg.svd(matrix,full_matrices=False)
            normal=np.cross(directions[:,0],directions[:,1])
            axes=gp_Ax2(_point(center),gp_Dir(*map(float,normal)),gp_Dir(*map(float,directions[:,0])))
            lines=[Geom_Ellipse(axes,float(radii[0]),float(radii[1]))]
    # El intersector puede devolver un bucle como varios arcos no periódicos.
    # Unir sólo extremos coincidentes, manteniendo las curvas de intersección.
    additions=[]
    for index,initial in enumerate(lines):
        if initial.IsClosed() or not math.isfinite(initial.FirstParameter()) or abs(initial.FirstParameter())>1e20:continue
        current=initial;used={index}
        for _ in range(min(len(lines),16)):
            endpoint=current.Value(current.LastParameter());matches=[]
            for j,c in enumerate(lines):
                if j in used or c.IsClosed() or abs(c.FirstParameter())>1e20 or abs(c.LastParameter())>1e20:continue
                if endpoint.Distance(c.Value(c.FirstParameter()))<=1e-7:matches.append((j,c))
                elif endpoint.Distance(c.Value(c.LastParameter()))<=1e-7:matches.append((j,c.Reversed()))
            if len(matches)!=1:break
            j,following=matches[0]
            join=GeomConvert_CompCurveToBSplineCurve(Geom_TrimmedCurve(current,current.FirstParameter(),current.LastParameter()))
            if not join.Add(Geom_TrimmedCurve(following,following.FirstParameter(),following.LastParameter()),1e-7,True,True,0):break
            current=join.BSplineCurve();used.add(j)
            if current.IsClosed():break
        if len(used)>1:additions.append(current)
    for curve in lines+additions:
        if isinstance(curve,Geom_TrimmedCurve) and curve.BasisCurve().IsPeriodic():curve=curve.BasisCurve()
        if curve.IsClosed() and not curve.IsPeriodic() and hasattr(curve,'SetPeriodic'):
            old=curve;curve=curve.Copy();curve.SetPeriodic()
            if any(old.Value(float(t)).Distance(curve.Value(float(t)))>1e-7
                   for t in np.linspace(old.FirstParameter(),old.LastParameter(),65)):
                raise ValueError('La representación periódica altera la intersección.')
        projections=[GeomAPI_ProjectPointOnCurve(_point(p),curve) for p in samples]
        if any(p.NbPoints()==0 for p in projections):continue
        error=max(p.LowerDistance() for p in projections)
        parameters=np.array([p.LowerDistanceParameter() for p in projections])
        if curve.IsPeriodic():parameters=np.unwrap(parameters,period=curve.Period())
        diagnostic.append({'tipo':type(curve).__name__,'error':error,'parametros':parameters.tolist()})
        if np.any(np.diff(parameters)>1e-7) and np.any(np.diff(parameters)<-1e-7):continue
        first,last=map(float,(parameters[0],parameters[-1]))
        if closed and curve.IsPeriodic():last=first+math.copysign(curve.Period(),last-first)
        if error<=max_move and abs(last-first)>1e-14:candidates.append((error,curve,first,last))
    if not candidates:raise ValueError('Las superficies analíticas no admiten un encuentro próximo y continuo. '+str(diagnostic))
    _,curve,first,last=min(candidates,key=lambda row:row[0])
    if last<first:
        first,last=curve.ReversedParameter(first),curve.ReversedParameter(last);curve=curve.Reversed()
    curve,first,last=acondicionar_conica(curve,first,last)
    return refinar_interseccion(curve,first,last,sa,sb,max_move)

def _interpolar(points,closed=False):
    array=TColgp_HArray1OfPnt(1,len(points))
    for i,p in enumerate(points):array.SetValue(i+1,_point(p))
    interp=GeomAPI_Interpolate(array,closed,1e-10);interp.Perform()
    if not interp.IsDone():raise ValueError('No se obtiene un contorno continuo.')
    return interp.Curve()

def _sobre_superficie(surface,points,closed,projector):
    from OCP.ShapeAnalysis import ShapeAnalysis_Surface
    sas=ShapeAnalysis_Surface(surface);uv=np.array([sas.ValueOfUV(_point(p),1e-9).Coord() for p in points])
    for dim,periodic in [(0,surface.IsUPeriodic()),(1,surface.IsVPeriodic())]:
        if periodic:uv[:,dim]=np.unwrap(uv[:,dim],period=surface.UPeriod() if dim==0 else surface.VPeriod())
    if closed:
        # Se permite una costura paramétrica de2pi con el mismo vértice físico.
        end=uv[0].copy()
        for dim,periodic in [(0,surface.IsUPeriodic()),(1,surface.IsVPeriodic())]:
            if periodic:
                period=surface.UPeriod() if dim==0 else surface.VPeriod()
                end[dim]+=round((uv[-1,dim]-uv[0,dim])/period)*period
        uv=np.vstack((uv,end))
    keep=np.r_[True,np.linalg.norm(np.diff(uv,axis=0),axis=1)>1e-10];uv=uv[keep]
    if len(uv)<2:raise ValueError('Contorno UV degenerado.')
    # Conservar cada esquina del contorno original: no suavizar entre
    # puntos de un STL. Cada segmento UV se aproxima por separado.
    if isinstance(surface,Geom_Plane):
        import meshfit_brep as base
        mapped=np.array([surface.Value(float(q[0]),float(q[1])).Coord() for q in uv])
        return base._polyline_curve(mapped)
    segments=[]
    for a,b in zip(uv[:-1],uv[1:]):
        parameters=np.linspace(0.,1.,9)
        def mapped(t):
            q=a+(b-a)*t;return surface.Value(float(q[0]),float(q[1]))
        for iteration in range(9):
            points3=TColgp_HArray1OfPnt(1,len(parameters));params3=TColStd_HArray1OfReal(1,len(parameters))
            for i,t in enumerate(parameters):points3.SetValue(i+1,mapped(t));params3.SetValue(i+1,float(t))
            fit=GeomAPI_Interpolate(points3,params3,False,1e-12);fit.Perform()
            if not fit.IsDone():raise ValueError('No se interpola el segmento sobre el soporte.')
            curve=fit.Curve();bad=[]
            for i,(lo,hi) in enumerate(zip(parameters[:-1],parameters[1:])):
                if max(curve.Value(float(t)).Distance(mapped(t)) for t in np.linspace(lo,hi,9))>1e-8:bad.append(i)
            if not bad:break
            bad=np.asarray(bad,dtype=int);parameters=np.sort(np.r_[parameters,(parameters[bad]+parameters[bad+1])*.5])
            if len(parameters)>1025:raise ValueError('El segmento no alcanza la precisión numérica.')
        else:raise ValueError('El segmento no alcanza la precisión numérica.')
        segments.append(curve)
    result=segments[0]
    for next_curve in segments[1:]:
        join=GeomConvert_CompCurveToBSplineCurve(result)
        if not join.Add(next_curve,1e-10,True,True,0):raise ValueError('No se unen los segmentos del contorno.')
        result=join.BSplineCurve()
    return result,result.FirstParameter(),result.LastParameter()

def _superficie_libre(original,edges,points):
    """Ajustar el interior a su soporte y fijar todos los contornos comunes."""
    from OCP.GeomAPI import GeomAPI_ProjectPointOnSurf
    started=time.monotonic()
    if len(edges) in (3,4):
        try:
            curves=[GeomConvert.CurveToBSplineCurve_s(Geom_TrimmedCurve(c,a,b)) for c,a,b in edges]
            candidate=GeomFill_BSplineCurves(*curves,GeomFill_StretchStyle).Surface()
            maximum=max(GeomAPI_ProjectPointOnSurf(_point(p),candidate).LowerDistance() for p in points)
            from pcurvas_compartidas import _iso_comun
            exact_boundaries=all(_iso_comun(c,a,b,candidate) is not None for c,a,b in edges)
            if maximum<=.006 and exact_boundaries:
                print('[contornos] transfinito',round(time.monotonic()-started,3),'s ajuste',maximum,'isocurvas verificadas',flush=True)
                return candidate
            print('[contornos] transfinito descartado, interior',maximum,'isocurvas',exact_boundaries,flush=True)
        except Exception as exc:print('[contornos] transfinito fallido:',str(exc),flush=True)
    plate=GeomPlate_BuildPlateSurface(original,3,20,4,1e-8,2e-7,.01,.1,False)
    for curve,first,last in edges:
        plate.Add(GeomPlate_CurveConstraint(GeomAdaptor_Curve(curve,first,last),0,30,2e-7))
    # Puntos interiores originales, con reparto determinista. No alterar sus medidas.
    for p in points[np.linspace(0,len(points)-1,min(20,len(points))).astype(int)]:
        plate.Add(GeomPlate_PointConstraint(_point(p),0,1e-5))
    plate.Perform()
    if not plate.IsDone():raise ValueError('No converge la superficie con contornos compartidos.')
    approximation=GeomPlate_MakeApprox(plate.Surface(),2e-7,100,8,plate.G0Error(),0)
    print('[contornos] Plate',round(time.monotonic()-started,3),'s G0',plate.G0Error(),flush=True)
    return approximation.Surface()

def separar_planos_aproximados(mesh,labels,surfaces):
    """Una tolerancia de región no convierte un redondeo en un plano exacto.

    Mantener el núcleo coplanar y reconstruir aparte los triángulos del borde
    absorbidos por el detector. No retirar triángulos ni alterar sus vértices.
    """
    import meshfit_brep as base
    labels=labels.copy();surfaces=dict(surfaces);groups=base._groups(labels)
    next_label=int(labels.max())+1;separated=0
    for l,ids in groups.items():
        surface=surfaces[l]
        if not isinstance(surface,Geom_Plane) or len(ids)<3:continue
        vertices=np.asarray(mesh.vertices[mesh.faces[ids]])
        candidates=[surface]+[base._facet_surface(mesh,int(i)) for i in ids[np.argsort(-mesh.area_faces[ids])[:24]]]
        best=None
        for candidate in candidates:
            if candidate is None:continue
            plane=candidate.Pln();normal=np.array(plane.Axis().Direction().Coord());origin=np.array(plane.Location().Coord())
            error=np.max(np.abs((vertices-origin)@normal),axis=1)
            core=error<=1e-5;weight=float(mesh.area_faces[ids[core]].sum())
            if best is None or weight>best[0]*(1+1e-4)+1e-12:best=(weight,candidate,core)
        _,candidate,core=best
        if core.sum()<2:continue
        surfaces[l]=candidate
        other=ids[~core]
        if not len(other):continue
        # Cada resto se conserva primero como una faceta. Las que siguen
        # coplanares se pueden unir en un desarrollo posterior; no se ocultan.
        for face in other:
            labels[face]=next_label;surfaces[next_label]=base._facet_surface(mesh,int(face));next_label+=1
        separated+=len(other)
    comp=base._split_connected(mesh,labels);result={}
    for c in np.unique(comp):
        index=int(np.flatnonzero(comp==c)[0]);result[int(c)]=surfaces[int(labels[index])]
    print('[contornos] triángulos separados de planos aproximados:',separated,flush=True)
    return comp,result

def subdividir_parches_complejos(mesh,labels,surfaces,primary,triangulos_libres=None):
    """Parches libres de más de cuatro lados: pares de triángulos conservados.

    No pedir a una superficie aproximada que resuelva a la vez contornos
    incompatibles o agujeros. Los recortes salen de la topología original.
    """
    import meshfit_brep as base
    import os
    single=(os.environ.get('VISOR_TRIANGULOS_LIBRES')=='1' if triangulos_libres is None else bool(triangulos_libres))
    _,loops,_=base._boundary_chains(mesh,labels)
    targets={l for l,lps in loops.items() if l not in primary and
             (len(lps)>1 or sum(map(len,lps))>4 or int((labels==l).sum())>(1 if single else 2))}
    if not targets:return
    groups=base._groups(labels);next_label=int(labels.max())+1
    adj=mesh.face_adjacency;edges=[]
    for a,b in adj:
        if single:break
        l=int(labels[a])
        if l not in targets or labels[b]!=l or mesh.face_normals[a]@mesh.face_normals[b]<np.cos(np.radians(10)):continue
        shared=np.intersect1d(mesh.faces[a],mesh.faces[b])
        if len(shared)!=2:continue
        # Emparejar por la diagonal más larga; preferir cuadriláteros convexos.
        union=np.unique(np.r_[mesh.faces[a],mesh.faces[b]])
        if len(union)!=4:continue
        P=mesh.vertices[union];center=P.mean(0);_,_,vt=np.linalg.svd(P-center,full_matrices=False)
        q=(P-center)@vt[:2].T
        from scipy.spatial import ConvexHull
        try:
            if len(ConvexHull(q).vertices)!=4:continue
        except Exception:continue
        edges.append((float(np.linalg.norm(mesh.vertices[shared[0]]-mesh.vertices[shared[1]])),int(a),int(b),l))
    pairs={};used=set()
    for _,a,b,l in sorted(edges,reverse=True):
        if a in used or b in used:continue
        pairs[a]=b;used.update((a,b))
    for l in targets:
        ids=groups[l];visited=set();first=True
        for a in ids:
            a=int(a)
            if a in visited:continue
            group=[a]
            if a in pairs:group.append(pairs[a])
            elif a in used:
                # El compañero de un par se atiende desde su primera cara.
                continue
            visited.update(group);label=l if first else next_label
            if not first:next_label+=1
            first=False;labels[group]=label;surfaces[label]=surfaces[l]
    if len(surfaces)>3000:raise ValueError('La reconstrucción de contornos excede el presupuesto de3000caras.')
    print('[contornos] parches libres subdivididos:',len(targets),'superficies totales:',len(surfaces),flush=True)

def construir(mesh,labels,comp_surf,tol,max_move,smooth_len=0.,parches_regulares=None,triangulos_libres=None):
    import meshfit_brep as base
    from scipy.optimize import least_squares
    import os
    regular=(os.environ.get('VISOR_PARCHES_REGULARES')=='1' if parches_regulares is None else bool(parches_regulares))
    corrected_labels,corrected_surfaces=separar_planos_aproximados(mesh,labels,comp_surf)
    labels[:]=corrected_labels;comp_surf.clear();comp_surf.update(corrected_surfaces)
    begin=time.monotonic();groups=base._groups(labels)
    projectors={l:base._Proj(s) for l,s in comp_surf.items()}
    primary=set()
    for l,s in comp_surf.items():
        if isinstance(s,Geom_BSplineSurface):continue
        ids=groups[l]
        if isinstance(s,Geom_Plane) and len(ids)<=1:continue
        pts=np.vstack((mesh.vertices[np.unique(mesh.faces[ids])],mesh.triangles_center[ids]))
        error=float(np.linalg.norm(projectors[l].batch(pts)-pts,axis=1).max())
        limit=1e-5 if isinstance(s,Geom_Plane) else .008
        if error<=limit:primary.add(l)
    # Facetas casi tangentes a un plano extenso no fijan una esquina mecánica
    # independiente. Mantener su geometría como parche evita que pequeñas
    # diferencias de coma flotante extrapolen una intersección lejana.
    incident_all=collections.defaultdict(set)
    for face,label in zip(mesh.faces,labels):
        if int(label) in primary:
            for v in face:incident_all[int(v)].add(int(label))
    demoted=set();areas={l:float(mesh.area_faces[ids].sum()) for l,ids in groups.items()}
    for regions in incident_all.values():
        planes=[l for l in regions if isinstance(comp_surf[l],Geom_Plane)]
        for a in planes:
            for b in planes:
                if a==b or areas[b]<=4*areas[a]:continue
                na=np.array(comp_surf[a].Pln().Axis().Direction().Coord())
                nb=np.array(comp_surf[b].Pln().Axis().Direction().Coord())
                if abs(na@nb)>np.cos(np.radians(5)):
                    demoted.add(a)
    primary-=demoted
    if demoted:print('[contornos] facetas tangentes reconstruidas aparte:',len(demoted),flush=True)
    print('[contornos] superficies confirmadas:',len(primary),'de',len(comp_surf),flush=True)
    subdividir_parches_complejos(mesh,labels,comp_surf,primary,triangulos_libres=triangulos_libres)
    groups=base._groups(labels)
    mesh.esquinas_contorno_compartido={int(v) for l,ids in groups.items() if l not in primary
                                      for v in mesh.faces[ids].ravel()}
    projectors={l:base._Proj(s) for l,s in comp_surf.items()}
    chains,loops,corners=base._boundary_chains(mesh,labels)
    positions={v:mesh.vertices[v].copy() for ch in chains.values() for v in ch['verts']}
    incident=collections.defaultdict(set)
    for ch in chains.values():
        for v in ch['verts']:incident[v].update(l for l in ch['pair'] if l in primary)
    # Sólo se imponen superficies analíticas a las que pertenece el vértice.
    # Las zonas libres se reconstruyen después para compartir esos extremos.
    for v,regions in incident.items():
        if not regions:continue
        p=np.asarray(mesh.vertices[v]);prs=[projectors[l] for l in sorted(regions)]
        def residual(q):
            values=[]
            for pr in prs:
                if pr.kind=='plane':values.append((q-pr.q)@pr.a)
                elif pr.kind=='cyl':values.append(np.linalg.norm(np.cross(q-pr.q,pr.a))-pr.R)
                elif pr.kind=='sph':values.append(np.linalg.norm(q-pr.q)-pr.R)
                else:values.extend(pr.batch(np.array([q]))[0]-q)
            return np.asarray(values)
        def objective(q):return np.r_[residual(q),(q-p)*1e-5]
        fit=least_squares(objective,p,xtol=1e-12,ftol=1e-12,gtol=1e-12,max_nfev=80)
        if np.max(np.abs(residual(fit.x)))>2e-7 or np.linalg.norm(fit.x-p)>max_move:
            raise ValueError('Esquina incompatible con las superficies confirmadas; no se desplaza silenciosamente. '+
                             str({'vertice':v,'regiones':[(l,type(comp_surf[l]).__name__,len(groups[l])) for l in sorted(regions)],
                                  'residual':float(np.max(np.abs(residual(fit.x)))),'movimiento':float(np.linalg.norm(fit.x-p))}))
        positions[v]=fit.x
    builder=BRep_Builder();vertices={};edge_shapes={};edge_curves={}
    def vertex(v):
        if v not in vertices:
            result=TopoDS_Vertex();builder.MakeVertex(result,_point(positions[v]),1e-7);vertices[v]=result
        return vertices[v]
    for key,ch in chains.items():
        points=np.array([positions[v] for v in ch['verts']]);fixed=[l for l in ch['pair'] if l in primary]
        if len(fixed)==2:
            p=np.vstack((points,points[:1])) if ch['closed'] else points
            try:curve,first,last=_interseccion(*[comp_surf[l] for l in fixed],p,max_move,ch['closed'])
            except Exception as exc:
                raise ValueError(str(exc)+' '+str({'regiones':[(l,type(comp_surf[l]).__name__,len(groups[l])) for l in fixed],
                                                  'cerrada':ch['closed'],'puntos':len(points)})) from exc
        elif len(fixed)==1:
            l=fixed[0];curve,first,last=_sobre_superficie(comp_surf[l],points,ch['closed'],projectors[l])
        else:
            p=np.vstack((points,points[:1])) if ch['closed'] else points
            curve,first,last=base._polyline_curve(p)
        if regular and any(l not in primary for l in ch['pair']):
            from parches_triangulares import bezier_local
            curve,first,last=bezier_local(curve,first,last,positions[ch['verts'][0]],positions[ch['verts'][0] if ch['closed'] else ch['verts'][-1]])
        edge=TopoDS_Edge();builder.MakeEdge(edge,curve,1e-7)
        v0=vertex(ch['verts'][0]);v1=v0 if ch['closed'] else vertex(ch['verts'][-1])
        for v,p in [(v0,curve.Value(first)),(v1,curve.Value(last))]:
            distance=BRep_Tool.Pnt_s(v).Distance(p)
            if distance>2e-6:raise ValueError('El contorno nuevo no coincide con su vértice compartido.')
            builder.UpdateVertex(v,max(BRep_Tool.Tolerance_s(v),distance*1.01+1e-7))
        builder.Add(edge,v0.Oriented(TopAbs_FORWARD));builder.Add(edge,v1.Oriented(TopAbs_REVERSED));builder.Range(edge,first,last)
        edge_shapes[key]=edge;edge_curves[key]=(curve,first,last)
    print('[contornos] curvas comunes:',len(chains),'en',round(time.monotonic()-begin,2),'s',flush=True)
    faces={}
    for l,lps in loops.items():
        uv_known=None
        surface=comp_surf[l];ids=groups[l]
        ks=ids[np.argsort(-mesh.area_faces[ids])[:30]];votes=0.
        for k in ks:
            normal=projectors[l].normal(mesh.triangles_center[k])
            if normal is not None:votes+=np.sign(float(normal@mesh.face_normals[k]))*mesh.area_faces[k]
        inward=votes<0
        if l not in primary:
            constraints=[]
            for lp in lps:
                for key,forward in lp:
                    curve,first,last=edge_curves[key]
                    if not forward:
                        trimmed=Geom_TrimmedCurve(curve,first,last).Reversed()
                        constraints.append((trimmed,trimmed.FirstParameter(),trimmed.LastParameter()))
                    else:constraints.append((curve,first,last))
            points=np.asarray(mesh.triangles_center[ids])
            print('[contornos] ajustando región',l,type(surface).__name__,len(constraints),'aristas',flush=True)
            if regular and len(lps)==1 and len(lps[0])==3:
                from parches_triangulares import superficie_triangular
                surface=superficie_triangular(constraints,np.average(points,axis=0,weights=mesh.area_faces[ids]))
                uv_known={key:ends if forward else tuple(reversed(ends)) for (key,forward),ends in
                          zip(lps[0],[((0.,0.),(1.,0.)),((1.,0.),(0.,1.)),((0.,1.),(0.,0.))])}
            else:surface=_superficie_libre(surface,constraints,points)
            projected=base._Proj(surface);votes=0.
            for k in ks:
                normal=projected.normal(mesh.triangles_center[k])
                if normal is not None:votes+=np.sign(float(normal@mesh.face_normals[k]))*mesh.area_faces[k]
            inward=votes<0
        face=TopoDS_Face();builder.MakeFace(face,surface,1e-7)
        from pcurvas_compartidas import crear_pcurva
        for lp in lps:
            for key,_ in lp:
                curve,first,last=edge_curves[key]
                try:
                    if uv_known is not None:
                        from pcurvas_compartidas import _lineal_uv,_error
                        uv=_lineal_uv(first,last,*uv_known[key])
                        if _error(curve,uv,surface,first,last)>5e-8:raise ValueError('La curvaUV conocida no supera el control.')
                    else:uv,proof=crear_pcurva(curve,first,last,surface)
                except Exception as exc:
                    import os,io
                    debug=os.environ.get('VISOR_DEPURAR_CONTORNOS')
                    if debug:
                        from pathlib import Path
                        from OCP.GeomTools import GeomTools
                        p=Path(debug);p.mkdir(parents=True,exist_ok=True)
                        for name,obj in [('curva',curve),('superficie',surface)]:
                            data=io.BytesIO();GeomTools.Write_s(obj,data);(p/(name+'.geom')).write_bytes(data.getvalue())
                        (p/'intervalo.txt').write_text(f'{first} {last}')
                    raise ValueError(str(exc)+' '+str({'region':l,'tipo':type(surface).__name__,'curva':type(curve).__name__,
                                                       'primaria':l in primary,'intervalo':[first,last]})) from exc
                builder.UpdateEdge(edge_shapes[key],uv,face,1e-7)
                builder.Range(edge_shapes[key],face,first,last)
                builder.SameRange(edge_shapes[key],True);builder.SameParameter(edge_shapes[key],True)
        for lp in lps:
            wire=TopoDS_Wire();builder.MakeWire(wire)
            for key,forward in lp:builder.Add(wire,edge_shapes[key].Oriented(TopAbs_FORWARD if forward else TopAbs_REVERSED))
            builder.Add(face,wire.Reversed() if inward else wire)
        faces[l]=face.Reversed() if inward else face
    shell=TopoDS_Shell();builder.MakeShell(shell)
    for face in faces.values():builder.Add(shell,face)
    import os
    debug=os.environ.get('VISOR_DEPURAR_CONTORNOS')
    if debug:
        from pathlib import Path
        target=Path(debug);target.mkdir(parents=True,exist_ok=True)
        np.savez_compressed(target/'mapa_regiones.npz',vertices=mesh.vertices,triangulos=mesh.faces,
                            etiquetas=labels,orden_caras=np.array(list(faces)))
    print('[contornos] shell construido',len(faces),'caras en',round(time.monotonic()-begin,3),'s',flush=True)
    return shell,faces
