"""Measured solid/annular revolution cores and original planar radial ribs.

Proposal only. The isolated worker must verify the original surface, material,
details, exact B-Rep, exported STEP and three independent fine meshes.
"""
import numpy as np
import cadquery as cq
from shapely.geometry import Polygon,box,LineString
from collections import Counter,defaultdict
from perfiles_planos_r15 import compact,circle
from reconstruccion_axial_medida_r17 import comprobar_detalles,regiones_planas_axiales
from familia_axial_r18 import ejes,base,secciones


def solido_finito(shape):
 """Orient the closed construction BEFORE Boolean material operations."""
 from OCP.BRepLib import BRepLib
 from OCP.BRepClass3d import BRepClass3d_SolidClassifier
 from OCP.TopAbs import TopAbs_OUT
 solids=shape.Solids()
 if len(solids)!=1:raise ValueError('La construcción no tiene un único sólido')
 solid=solids[0]
 if not BRepLib.OrientClosedSolid_s(solid.wrapped):raise ValueError('No se confirma la orientación del sólido cerrado')
 classifier=BRepClass3d_SolidClassifier(solid.wrapped);classifier.PerformInfinitePoint(1e-7)
 if classifier.State()!=TopAbs_OUT:raise ValueError('La construcción describe material infinito')
 return solid








def _perfiles_positivos(section,origin,axis,radial):
 loops=[]
 for P in section.discrete:
  xy=np.c_[(P-origin)@radial,(P-origin)@axis];p=Polygon(xy)
  if not p.is_valid or p.area<=1e-8:raise ValueError('Meridiano no válido')
  loops.append(p)
 parents=[]
 for i,p in enumerate(loops):
  hosts=[j for j,q in enumerate(loops)if j!=i and q.area>p.area and q.covers(p.representative_point())]
  parents.append(min(hosts,key=lambda j:loops[j].area)if hosts else None)
 result=[]
 for i,p in enumerate(loops):
  if parents[i]is not None:continue
  p=Polygon(p.exterior.coords,[q.exterior.coords for j,q in enumerate(loops)if parents[j]==i])
  xmin,zmin,xmax,zmax=p.bounds;margin=max(xmax-xmin,zmax-zmin,1.)
  p=p.intersection(box(0,zmin-margin,max(xmax,0)+margin,zmax+margin))
  for region in ([p]if p.geom_type=='Polygon'else getattr(p,'geoms',[])):
   if region.is_empty or region.area<1e-8:continue
   if region.geom_type!='Polygon'or len(region.interiors):raise ValueError('Meridiano con cavidad cerrada no admitida')
   result.append(region)
 return result


def construir_nucleo(mesh,calibrar_vertices=False):
 errors=[]
 for axis in ejes(mesh)[:3]:
  try:
   origin,u,v,sections=secciones(mesh,axis);Z=np.array([r['z']for r in sections]);C=np.array([r['center']for r in sections])
   fit=np.linalg.lstsq(np.c_[Z,np.ones(len(Z))],C,rcond=None)[0];refined=axis+u*fit[0,0]+v*fit[0,1];refined/=np.linalg.norm(refined)
   if np.linalg.norm(refined-axis)>2e-5:raise ValueError('Eje inestable')
   # The measured cap planes define the axis. Circle-centre drift is a
   # consistency check; replacing that axis amplifies Float32 noise at joins.
   origin=origin+u*fit[1,0]+v*fit[1,1];origin,u,v,sections=secciones(mesh,axis,origin)
   if max(np.linalg.norm(r['center'])for r in sections)>.001:raise ValueError('El centro varía entre estaciones')
   candidates=[];meridian_errors=[];section_cache={}
   def extra_sections(lo,hi):
    extra=[]
    for f in (.3819660112501051,.6180339887498949):
     z=lo+(hi-lo)*f;key=round(z,10)
     if key not in section_cache:
      try:section_cache[key]=secciones(mesh,axis,origin,niveles=[z])[3]
      except ValueError:section_cache[key]=[]
     extra.extend(section_cache[key])
    return extra
   for angle in (0.,.6180339887498949*np.pi,1.2360679774997898*np.pi,1.8541019662496847*np.pi,.4721359549995796*np.pi):
    for sign in (1.,-1.):
     radial=sign*(u*np.cos(angle)+v*np.sin(angle));cut=mesh.section(plane_origin=origin,plane_normal=np.cross(axis,radial))
     if cut is None:continue
     try:
      profiles=_perfiles_positivos(cut,origin,axis,radial)
      if len(profiles)!=1:raise ValueError(f'{len(profiles)} regiones meridianas positivas')
      region=profiles[0]
      if mesh.euler_number==2:
       P=np.asarray(region.exterior.coords)[:-1];height=P[:,1];lo=float(height.min());hi=float(height.max())
       bottom=max(np.flatnonzero(abs(height-lo)<.0001),key=lambda k:P[k,0]);top=max(np.flatnonzero(abs(height-hi)<.0001),key=lambda k:P[k,0]);chains=[]
       for direction in (1,-1):
        ids=[bottom];k=bottom
        while k!=top:k=(k+direction)%len(P);ids.append(k)
        chain=P[ids]
        if np.min(np.diff(chain[:,1]))>=-.0001:chains.append(chain)
       if not chains:raise ValueError('Contorno exterior no monótono')
       chain=max(chains,key=lambda p:np.sum((p[:-1,0]+p[1:,0])*.5*np.diff(p[:,1])))
       region=Polygon(np.vstack([[0,lo],chain,[0,hi]]))
      # Every measured circular section must coincide with the meridian core.
      for row in sections:
       z=row['z'];cross=region.intersection(LineString([(0,z),(np.linalg.norm(mesh.extents),z)]))
       if cross.geom_type!='LineString':raise ValueError('Sección del meridiano no conexa')
       lo,_,hi,_=cross.bounds;expected=[c['radius']for c in row['circles']]
       if max(abs(hi-max(expected)),abs(lo-(min(expected)if len(expected)==2 else 0)))>.012:raise ValueError('El meridiano convierte un refuerzo en un anillo')
      shape,proof=_revolver_perfil_r18(np.asarray(region.exterior.coords),origin,axis,radial,sections,extra_sections,mesh.vertices if calibrar_vertices else None)
      candidates.append((len(shape.Faces()),-shape.Volume(),shape,proof,radial))
     except ValueError as exc:meridian_errors.append(str(exc));continue
   if not candidates:raise ValueError('Ningún meridiano conserva las secciones medidas: '+'; '.join(meridian_errors))
   _,_,shape,profile,radial=min(candidates,key=lambda c:(c[0],c[1]))
   return shape,dict(eje=axis.tolist(),origen=origin.tolist(),direccion_meridiana=radial.tolist(),meridianos_contrastados=len(candidates),perfil=profile,
      secciones=[dict(z=r['z'],circulos=[{k:(v.tolist()if isinstance(v,np.ndarray)else v)for k,v in c.items()}for c in r['circles']])for r in sections])
  except Exception as exc:errors.append(str(exc))
 raise ValueError('; '.join(errors)or'Sin eje confirmado')


def _contorno(mesh,group,normal):
 F=mesh.faces;V=mesh.vertices;points=V[np.unique(F[group])];origin=points.mean(0)
 if abs((points-origin)@normal).max()>.0001:raise ValueError('Plano de refuerzo no confirmado')
 counts=Counter(tuple(sorted((int(a),int(b))))for tri in F[group]for a,b in zip(tri,np.roll(tri,-1)));adj=defaultdict(list)
 for (a,b),count in counts.items():
  if count==1:adj[a].append(b);adj[b].append(a)
 if any(len(a)!=2 for a in adj.values()):raise ValueError('Contorno de refuerzo ramificado')
 first=min(adj);ids=[first];previous=None;current=first
 while True:
  nxt=next(x for x in adj[current]if x!=previous)
  if nxt==first:break
  if nxt in ids:raise ValueError('Contorno repetido')
  ids.append(nxt);previous,current=current,nxt
 if len(ids)!=len(adj):raise ValueError('Refuerzo con varios contornos no admitido')
 P=V[ids];P=P-np.outer((P-origin)@normal,normal);u,v=base(normal);xy=compact(np.c_[(P-origin)@u,(P-origin)@v],tol=.00001)
 if not Polygon(xy).is_valid:raise ValueError('Polígono de refuerzo no válido')
 return origin+xy[:,0,None]*u+xy[:,1,None]*v


def planos_radiales(mesh,axis,origin,radius):
 result=[];seen=set();area=np.asarray(mesh.area_faces);normals=mesh.face_normals
 for seed in sorted(mesh.facets,key=lambda g:-area[g].sum()):
  if area[seed].sum()<mesh.area*.003:break
  if any(int(i)in seen for i in seed):continue
  P=mesh.vertices[np.unique(mesh.faces[seed])];center=P.mean(0);_,_,vt=np.linalg.svd(P-center,full_matrices=False);normal=vt[-1]
  if normal@np.mean(normals[seed],axis=0)<0:normal=-normal
  if abs(normal@axis)>1e-4 or abs((center-origin)@normal)>radius*.65 or abs((P-center)@normal).max()>.0001:continue
  active=(np.max(abs((mesh.triangles-center)@normal),axis=1)<=.0001)&(normals@normal>.9999)
  links=mesh.face_adjacency;valid=active[links].all(axis=1)
  import trimesh
  groups=trimesh.graph.connected_components(links[valid],nodes=np.flatnonzero(active),min_len=1)
  group=next(g for g in groups if int(seed[0])in g);seen.update(map(int,group));weights=area[group]
  perpendicular=normal-axis*(normal@axis);perpendicular/=np.linalg.norm(perpendicular)
  if abs((P-center)@perpendicular).max()<=.0001:normal=perpendicular
  center=np.average(mesh.triangles_center[group],axis=0,weights=weights)
  result.append(dict(group=np.asarray(group),normal=normal,center=center,area=float(weights.sum())))
 return result


def conservar_refuerzos(mesh,shape,proof,unir=True):
 axis=np.asarray(proof['eje']);origin=np.asarray(proof['origen']);radius=float(np.median([max(c['radius']for c in r['circulos'])for r in proof['secciones']]))
 planes=planos_radiales(mesh,axis,origin,radius);used=set();records=[];tools=[]
 from OCP.BRepClass3d import BRepClass3d_SolidClassifier
 from OCP.TopAbs import TopAbs_OUT
 from OCP.gp import gp_Pnt
 classifier=BRepClass3d_SolidClassifier(shape.wrapped)
 external=[]
 for p in planes:
  classifier.Perform(gp_Pnt(*map(float,p['center'])),1e-7)
  if classifier.State()==TopAbs_OUT:external.append(p)
 planes=external
 for i,a in enumerate(planes):
  if i in used:continue
  choices=[]
  for j,b in enumerate(planes):
   if j==i or j in used or a['normal']@b['normal']>-.999999:continue
   D=b['center']-a['center'];delta=float(D@a['normal']);lateral=np.linalg.norm(D-delta*a['normal'])
   if -.95*radius<delta<-.01 and lateral<.02:choices.append((lateral,j,delta))
  if not choices:raise ValueError('Un plano radial no tiene su opuesto medido')
  _,j,delta=min(choices);b=planes[j];used.update([i,j]);P=_contorno(mesh,a['group'],a['normal'])
  # Reuse the measured cap stations at shared joins. Independent projections
  # of the same Float32 vertex otherwise create microscopic sliver faces.
  stations=np.unique(np.asarray(proof['perfil']['profile'])[:,1]);direction=axis-a['normal']*(a['normal']@axis);denominator=float(direction@axis)
  for k in range(len(P)):
   height=float((P[k]-origin)@axis);nearest=float(stations[np.argmin(abs(stations-height))])
   if abs(nearest-height)<=.0001:P[k]+=direction*((nearest-height)/denominator)
  # Canonicalize only source-supported near-horizontal/vertical edges in
  # the measured side plane. This removes Float32 tilts at shared caps.
  radial=np.cross(a['normal'],axis);radial/=np.linalg.norm(radial)
  xy=np.c_[P@radial,P@axis];anchor=P[0]-radial*(P[0]@radial)-axis*(P[0]@axis)
  for dim in range(2):
   parents=list(range(len(xy)-1))
   def find(i):
    while parents[i]!=i:parents[i]=parents[parents[i]];i=parents[i]
    return i
   for k in range(len(xy)-1):
    j=(k+1)%(len(xy)-1)
    if abs(xy[k,dim]-xy[j,dim])<=.0001:parents[find(k)]=find(j)
   for root in set(map(find,range(len(xy)-1))):
    ids=[k for k in range(len(xy)-1)if find(k)==root];xy[ids,dim]=np.mean(xy[ids,dim])
  xy[-1]=xy[0];P=anchor+xy[:,0,None]*radial+xy[:,1,None]*axis
  wire=cq.Wire.makePolygon([cq.Vector(*p)for p in P],close=True)
  tool=solido_finito(cq.Solid.extrudeLinear(wire,[],cq.Vector(*(delta*a['normal']))));buried=[]
  # Extend only already buried profile edges, along their adjacent measured
  # planes. The added volume must remain wholly inside the existing core.
  from OCP.BRepClass3d import BRepClass3d_SolidClassifier
  from OCP.TopAbs import TopAbs_IN,TopAbs_ON
  from OCP.gp import gp_Pnt
  classifier=BRepClass3d_SolidClassifier(shape.wrapped);Q=P[:-1].copy()
  for k in range(len(Q)):
   j=(k+1)%len(Q);edge=Q[j]-Q[k];length=np.linalg.norm(edge)
   if length<1. or abs(edge@axis)/length<.98:continue
   states=[]
   for t in np.linspace(0,1,9):
    classifier.Perform(gp_Pnt(*map(float,Q[k]*(1-t)+Q[j]*t)),1e-7);states.append(classifier.State())
   if not all(s in (TopAbs_IN,TopAbs_ON)for s in states):continue
   C=(Q[k]+Q[j])*.5;D=origin+axis*((C-origin)@axis)-C;D-=a['normal']*(D@a['normal']);D-=edge*(D@edge)/(length*length)
   if np.linalg.norm(D)<1e-9:continue
   D*=.01/np.linalg.norm(D);u,v=base(a['normal']);xy=np.c_[Q@u,Q@v];shift=np.array([D@u,D@v]);old=Polygon(xy)
   def intersection(A,U,B,V):
    mat=np.c_[U,-V]
    if abs(np.linalg.det(mat))<1e-12:raise ValueError('Aristas casi paralelas en el solape')
    return A+U*np.linalg.solve(mat,B-A)[0]
   try:
    moved=xy.copy();moved[k]=intersection(xy[k-1],xy[k]-xy[k-1],xy[k]+shift,xy[j]-xy[k]);moved[j]=intersection(xy[k]+shift,xy[j]-xy[k],xy[j],xy[(j+1)%len(Q)]-xy[j]);polygon=Polygon(moved)
    if not polygon.is_valid or not polygon.buffer(1e-10).covers(old):continue
    anchor=Q[0]-u*(Q[0]@u)-v*(Q[0]@v);candidate=anchor+moved[:,0,None]*u+moved[:,1,None]*v
    expanded=solido_finito(cq.Solid.extrudeLinear(cq.Wire.makePolygon([cq.Vector(*p)for p in candidate],close=True),[],cq.Vector(*(delta*a['normal']))))
    added=expanded.cut(tool)
    leak=added.cut(shape);leak_volume=float(leak.Volume())
    if not added.isValid()or not leak.isValid()or added.Volume()<=1e-9 or leak_volume>1e-8:continue
    Q=candidate;tool=expanded;buried.append(dict(arista=k,extension_mm=.01,volumen_fuera_nucleo_mm3=leak_volume))
   except (ValueError,RuntimeError):continue
  if len(tool.Solids())!=1 or not tool.isValid():raise ValueError('Refuerzo original no válido')
  tools.append(tool)
  if unir:
   shape=solido_finito(shape.fuse(tool,tol=.0001).clean())
   if not shape.isValid():raise ValueError('La unión del refuerzo no es válida')
  from OCP.BRepAdaptor import BRepAdaptor_Surface
  native_planes=[]
  for f in tool.Faces():
   if f.geomType()!='PLANE':continue
   plane=BRepAdaptor_Surface(f.wrapped,True).Plane();N=np.array(plane.Axis().Direction().Coord());outward=np.array(f.normalAt().toTuple())
   if N@outward<0:N=-N
   native_planes.append(dict(punto=plane.Location().Coord(),normal=N.tolist(),area=f.Area()))
  records.append(dict(caras_fuente=list(map(int,np.r_[a['group'],b['group']])),normal=a['normal'].tolist(),centro_lateral=a['center'].tolist(),espesor_mm=abs(delta),vertices=len(P)-1,area_lateral_mm2=[a['area'],b['area']],planos_CAD=native_planes,solapes_interiores=buried,origen_nucleo=origin.tolist(),radio_nucleo_max=float(np.max(np.asarray(proof['perfil']['profile'])[:,0]))))
 if len(records)>16:raise ValueError('Demasiados refuerzos para esta familia')
 return shape,records,tools


def _proponer_local(mesh,cortes_antes=False,calibrar_vertices=False):
 if mesh.euler_number not in (0,2):raise ValueError('Topología fuera de la familia')
 shape,proof=construir_nucleo(mesh,calibrar_vertices=calibrar_vertices);shape,ribs,tools=conservar_refuerzos(mesh,shape,proof,unir=not cortes_antes)
 if mesh.euler_number==0 and not ribs:raise ValueError('Los cuerpos anulares sin refuerzos conservan la ruta R17')
 shape,openings=conservar_techos_expuestos(mesh,shape,proof['eje'],ribs)
 reference=shape
 if cortes_antes:
  for tool in tools:reference=solido_finito(reference.fuse(tool,tol=.0001).clean())
 shape,details=conservar_vaciados_axiales(mesh,shape,proof['eje'],ribs,reference)
 if cortes_antes:
  for tool in tools:shape=solido_finito(shape.fuse(tool,tol=.0001).clean())
  if not shape.isValid():raise ValueError('La unión final de refuerzos no es válida')
 if len(shape.Faces())>1500:raise ValueError('Complejidad final fuera del alcance')
 proof.update(resolucion_numerica_union_mm=.0001,normalizacion_aristas_planas_mm=.0001,metodo='nucleo_axial_y_refuerzos_originales',rebajes=details,refuerzos=ribs,vaciados_abiertos_refuerzos=openings,caras_finales=len(shape.Faces()),limites_aceptacion_modificados=False)
 return shape,proof


def comprobar_detalles_compuestos(mesh,shape,proof):
 result=comprobar_detalles(mesh,shape,proof)
 from material_cad_indexado import ClasificadorMaterial
 ids=sorted(set(i for g in proof['refuerzos']for i in g['caras_fuente']))
 if not ids:result['refuerzos']=dict(puntos=0,discrepancias=0,caras_fuente=0);return result
 ids=np.asarray(ids,dtype=int);P=mesh.triangles_center[ids];N=mesh.face_normals[ids];points=np.vstack([P+N*.0005,P-N*.0005]);expected=np.r_[np.zeros(len(ids),bool),np.ones(len(ids),bool)]
 classifier=ClasificadorMaterial(shape);actual=classifier.classify(points,expected=expected)
 if not np.array_equal(actual,expected):raise ValueError('Un plano original del refuerzo ha cambiado de material')
 result['refuerzos']=dict(puntos=len(points),discrepancias=0,caras_fuente=len(ids),distancia_probe_mm=.0005)
 return result


def _primer_retorno_material(mesh,points,direction):
 T=np.asarray(mesh.triangles);E1=T[:,1]-T[:,0];E2=T[:,2]-T[:,0];P=np.cross(np.broadcast_to(direction,E2.shape),E2);det=np.sum(E1*P,axis=1)
 inverse=np.divide(1.,det,out=np.zeros_like(det),where=abs(det)>1e-12);out=[]
 for origin in points:
  S=origin-T[:,0];u=np.sum(S*P,axis=1)*inverse;Q=np.cross(S,E1);v=(Q@direction)*inverse;t=np.sum(E2*Q,axis=1)*inverse
  valid=(abs(det)>1e-12)&(u>=-1e-9)&(v>=-1e-9)&(u+v<=1+1e-9)&(t>.0001)&(mesh.face_normals@direction<-.01)
  if not np.any(valid):out.append(None);continue
  index=np.flatnonzero(valid)[np.argmin(t[valid])];out.append(origin+direction*t[index])
 return out


def _herramienta_planar(rib,axis,scale,roof_normal,roof_origin,ceiling_normal=None,ceiling_origin=None):
 side=np.asarray(rib['normal']);radial=np.cross(side,axis);radial/=np.linalg.norm(radial);up=np.cross(radial,side);origin=np.asarray(rib['centro_lateral'])
 points=[np.array(p,float)for p in [(-scale,-scale),(scale,-scale),(scale,scale),(-scale,scale)]]
 planes=[(np.asarray(roof_normal),np.asarray(roof_origin))]
 if 'radio_nucleo_max'in rib:
  core_origin=np.asarray(rib['origen_nucleo']);radius=rib['radio_nucleo_max']+.001
  planes.extend([(radial,core_origin-radial*radius),(-radial,core_origin+radial*radius)])
 if ceiling_normal is not None:
  if abs(np.asarray(ceiling_normal)@side)*rib['espesor_mm']>.0001:raise ValueError('La tapa no es compatible con la extrusión medida')
  planes.append((np.asarray(ceiling_normal),np.asarray(ceiling_origin)))
 for normal,point in planes:
  n=np.array([normal@radial,normal@up]);d=float(normal@(origin-point));result=[]
  for P,Q in zip(points,points[1:]+points[:1]):
   a=float(n@P+d);b=float(n@Q+d)
   if a>=0:result.append(P)
   if (a>=0)!=(b>=0):result.append(P+(Q-P)*(a/(a-b)))
  points=result
  if len(points)<3:raise ValueError('El vaciado medido no encierra volumen')
 wire=cq.Wire.makePolygon([cq.Vector(*(origin+radial*p[0]+up*p[1]))for p in points],close=True)
 tool=cq.Solid.extrudeLinear(wire,[],cq.Vector(*(-side*rib['espesor_mm'])))
 if not tool.isValid()or tool.Volume()<=1e-9:raise ValueError('Herramienta de corte finita inválida')
 return solido_finito(tool)


def cortar_comprobado(shape,tool):
 """Resolve numerical ties only; never change final acceptance tolerances."""
 before=shape.Volume()
 for resolution in (0.,.000005,.00001):
  after=shape.cut(tool,tol=resolution if resolution else None).clean()
  if len(after.Solids())==1 and after.isValid()and before-after.Volume()>1e-9:
   return solido_finito(after),resolution
 raise ValueError('El booleano no retiró de forma válida el material identificado')


def conservar_techos_expuestos(mesh,shape,axis,ribs):
 from OCP.BRepClass3d import BRepClass3d_SolidClassifier
 from OCP.TopAbs import TopAbs_IN
 from OCP.gp import gp_Pnt
 axis=np.asarray(axis);records=[];scale=float(np.linalg.norm(mesh.extents));T=mesh.triangles
 for rib in ribs:
  for plane in rib['planos_CAD']:
   N=np.asarray(plane['normal']);C=np.asarray(plane['punto'])
   if not .05<abs(N@axis)<.99:continue
   ids=np.flatnonzero((np.max(abs((T-C)@N),axis=1)<=.0002)&(mesh.face_normals@N>.9999))
   if not len(ids):continue
   rib['caras_fuente']=sorted(set(rib['caras_fuente'])|set(map(int,ids)))
   center=np.average(mesh.triangles_center[ids],axis=0,weights=mesh.area_faces[ids]);vertices=mesh.vertices[np.unique(mesh.faces[ids])]
   edges=(T[ids]+np.roll(T[ids],-1,axis=1))*.5
   points=np.vstack([mesh.triangles_center[ids],vertices*.999+center*.001,edges.reshape(-1,3)*.999+center*.001]);direction=axis*np.sign(N@axis);classifier=BRepClass3d_SolidClassifier(shape.wrapped);affected=[]
   for P in points:
    classifier.Perform(gp_Pnt(*map(float,P+direction*.0005)),1e-7)
    if classifier.State()==TopAbs_IN:affected.append(P)
   if not affected:continue
   hits=_primer_retorno_material(mesh,np.asarray(affected),direction)
   if all(p is not None for p in hits):continue
   if any(p is not None for p in hits):raise ValueError('El techo mezcla vaciado abierto y cubierto; no se extrapola')
   tool=_herramienta_planar(rib,axis,scale,N,C);shape,resolution=cortar_comprobado(shape,tool)
   records.append(dict(caras_fuente=list(map(int,ids)),puntos_fuente_comprobados=len(affected),plano=plane,resolucion_numerica_booleano_mm=resolution))
 return shape,records


def _vaciado_inclinado(mesh,group,axis,normal,center,origin,ribs,hits):
 hits=np.asarray([p for p in hits if p is not None]);choices=[];scale=float(np.linalg.norm(mesh.extents))
 for rib in ribs:
  n=np.asarray(rib['normal']);c=np.asarray(rib['centro_lateral']);delta=(center-c)@n
  if not -rib['espesor_mm']-.0001<=delta<=.0001:continue
  for plane in rib['planos_CAD']:
   N=np.asarray(plane['normal']);C=np.asarray(plane['punto'])
   if N@normal>-.01:continue
   error=float(abs((hits-C)@N).max())
   if error<=.0002:choices.append((error,rib,N,C))
 if not choices:raise ValueError('El retorno del material no coincide con un plano original del refuerzo')
 error,rib,N,C=min(choices,key=lambda row:row[0])
 # Outward source-floor normal points into the void. Keep that side of the
 # ceiling, and the exterior side of the measured native rib-roof plane.
 tool=_herramienta_planar(rib,axis,scale,N,C,normal,origin)
 if len(tool.Solids())!=1 or not tool.isValid():raise ValueError('El vaciado inclinado no forma un volumen válido')
 return tool,dict(tipo='fondo_inclinado_medido',error_plano_fuente_mm=error)


def conservar_vaciados_axiales(mesh,shape,axis,ribs=(),reference=None):
 from OCP.BRepClass3d import BRepClass3d_SolidClassifier
 from OCP.TopAbs import TopAbs_IN
 from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
 from OCP.BRepExtrema import BRepExtrema_DistShapeShape
 from OCP.gp import gp_Pnt,gp_Dir,gp_Lin
 from OCP.IntCurvesFace import IntCurvesFace_ShapeIntersector
 from shapely.geometry import Polygon
 from collections import Counter,defaultdict
 records=[];V,F=mesh.vertices,mesh.faces;axis=np.asarray(axis);u,v=base(axis);original=shape if reference is None else reference
 for group in regiones_planas_axiales(mesh,axis):
  indices=np.unique(F[group]);points=V[indices];origin=points.mean(0);normal=axis*np.sign(np.mean(mesh.face_normals[group],axis=0)@axis)
  if max(abs((points-origin)@normal))>.0001:continue
  if len(indices)>2048 or len(records)>=32:raise ValueError('Los detalles exceden el presupuesto de construcción')
  center=mesh.triangles_center[group[len(group)//2]];dist=BRepExtrema_DistShapeShape(BRepBuilderAPI_MakeVertex(gp_Pnt(*map(float,center))).Vertex(),original.Shells()[0].wrapped);dist.Perform()
  if dist.Value()<.002:continue
  classifier=BRepClass3d_SolidClassifier(original.wrapped);classifier.Perform(gp_Pnt(*map(float,center)),1e-7)
  if classifier.State()!=TopAbs_IN:raise ValueError('Detalle saliente aún no admitido; conservar ruta anterior')
  ray=IntCurvesFace_ShapeIntersector();ray.Load(original.wrapped,1e-7);ray.Perform(gp_Lin(gp_Pnt(*map(float,center)),gp_Dir(*map(float,normal))),0,float(np.linalg.norm(mesh.extents)))
  depths=[ray.WParameter(i) for i in range(1,ray.NbPnt()+1) if ray.WParameter(i)>.001]
  if not depths:raise ValueError('No se encuentra la tapa correspondiente al rebaje')
  depth=min(depths)
  source_points=mesh.triangles_center[group];hits=_primer_retorno_material(mesh,source_points,normal)
  returns=[float((p-q)@normal)for p,q in zip(hits,source_points)if p is not None]
  if returns and min(returns)<depth-.001:
   if len(returns)!=len(source_points):raise ValueError('El fondo inclinado no se confirma en toda la región')
   tool,detail=_vaciado_inclinado(mesh,group,axis,normal,center,origin,ribs,hits);shape,resolution=cortar_comprobado(shape,tool)
   records.append(dict(faces=int(len(group)),faces_fuente=list(map(int,group)),vertices=len(indices),depth_mm=max(returns),area_mm2=float(mesh.area_faces[group].sum()),contornos=1,resolucion_numerica_booleano_mm=resolution,**detail));continue
  if depth>float(np.ptp(mesh.vertices@axis))*.98:raise ValueError('Rebaje fuera del alcance acotado')
  counter=Counter(tuple(sorted((int(a),int(b)))) for face in F[group] for a,b in zip(face,np.roll(face,-1)));edges=[e for e,c in counter.items() if c==1];adj=defaultdict(list)
  for a,b in edges:adj[a].append(b);adj[b].append(a)
  if any(len(x)!=2 for x in adj.values()):raise ValueError('Contorno plano ramificado')
  todo=set(adj);loops=[]
  while todo:
   first=min(todo);ids=[first];previous=None;current=first
   while True:
    nxt=next(x for x in adj[current] if x!=previous)
    if nxt==first:break
    if nxt in ids:raise ValueError('Ciclo plano repetido')
    ids.append(nxt);previous,current=current,nxt
   todo.difference_update(ids);P=V[ids];P=P-np.outer((P-origin)@normal,normal);xy=np.c_[P@u,P@v];poly=Polygon(xy)
   if not poly.is_valid or poly.area<1e-9:raise ValueError('Polígono plano no válido')
   loops.append((poly,P))
  parents=[]
  for i,(poly,P) in enumerate(loops):
   hosts=[j for j,(q,Q) in enumerate(loops) if j!=i and q.area>poly.area and q.covers(poly.representative_point())];parents.append(min(hosts,key=lambda j:loops[j][0].area) if hosts else None)
  for i,(poly,P) in enumerate(loops):
   if parents[i] is not None:continue
   outer=cq.Wire.makePolygon([cq.Vector(*p) for p in P],close=True);inner=[cq.Wire.makePolygon([cq.Vector(*p) for p in Q],close=True) for j,(q,Q) in enumerate(loops) if parents[j]==i]
   tool=solido_finito(cq.Solid.extrudeLinear(outer,inner,cq.Vector(*(normal*(depth+.001)))));shape=shape.cut(tool)
   if len(shape.Solids())!=1 or not shape.isValid():raise ValueError(f'Vaciado no válido: grupo={group.tolist()}, area={float(mesh.area_faces[group].sum())}, profundidad={depth}, solidos={len(shape.Solids())}')
  records.append(dict(faces=int(len(group)),faces_fuente=[int(i)for i in group],vertices=len(indices),depth_mm=float(depth),area_mm2=float(mesh.area_faces[group].sum()),contornos=len(loops)))
 shape=shape.clean()
 if len(shape.Solids())!=1 or not shape.isValid():raise ValueError('La recuperación de rebajes no deja un sólido válido')
 return shape,records


def _revolver_perfil_r18(profile,origin,axis,u,circular_sections=None,extra_sections=None,source_vertices=None):
 P=compact(profile);original_profile=P.copy()
 def simplify(P):
  if len(P)<=2:return P
  D=P[-1]-P[0];norm=D@D
  distances=np.linalg.norm(P-P[0],axis=1) if norm<1e-24 else np.linalg.norm(P-(P[0]+np.clip((P-P[0])@D/norm,0,1)[:,None]*D),axis=1)
  i=int(np.argmax(distances))
  return np.vstack([simplify(P[:i+1])[:-1],simplify(P[i:])]) if distances[i]>.00008 else P[[0,-1]]
 P=simplify(P);confirmed=[];radius_edges=[]
 if circular_sections:
  for i in range(len(P)-1):
   j=(i+1)%(len(P)-1);a,b=P[i],P[j];lo,hi=sorted([a[1],b[1]])
   if hi-lo<1. or abs(a[0]-b[0])>.004:continue
   values=[]
   rows=circular_sections+(extra_sections(lo,hi)if extra_sections else[])
   for row in rows:
    if lo+.0004<row['z']<hi-.0004:
     value=min([c['radius']for c in row['circles']],key=lambda r:abs(r-(a[0]+b[0])*.5))
     if max(abs(value-a[0]),abs(value-b[0]))<=.004:values.append(value)
   if len(values)>=2 and np.ptp(values)<=.002:radius_edges.append((i,j,values,lo,hi))
  parents=list(range(len(P)-1))
  def root(i):
   while parents[i]!=i:parents[i]=parents[parents[i]];i=parents[i]
   return i
  for i,j,values,lo,hi in radius_edges:parents[root(i)]=root(j)
  for component in {root(i)for i,j,v,lo,hi in radius_edges}:
   edges=[e for e in radius_edges if root(e[0])==component];values=[v for e in edges for v in e[2]]
   if np.ptp(values)>.002:continue
   indices={i for e in edges for i in e[:2]};radius=float(np.median(values));vertex_evidence={}
   if source_vertices is not None:
    VV=np.asarray(source_vertices)-origin;ZZ=VV@axis;RR=np.linalg.norm(VV-np.outer(ZZ,axis),axis=1)
    selected=RR[(abs(RR-radius)<.004)&(ZZ>=min(e[3]for e in edges)-.0001)&(ZZ<=max(e[4]for e in edges)+.0001)]
    if len(selected)>=24 and np.ptp(selected)<.004:
     radius=float(np.median(selected));vertex_evidence=dict(vertices_fuente=len(selected),variacion_vertices_mm=float(np.ptp(selected)))
   for i in indices:P[i,0]=radius
   confirmed.append(dict(z_mm=[float(min(e[3]for e in edges)),float(max(e[4]for e in edges))],radio_mm=radius,estaciones=len(values),variacion_evidencia_mm=float(np.ptp(values)),**vertex_evidence))
  P[-1]=P[0];P=compact(P)
 # Shared meridian vertices remain shared after removing sampling noise.
 for coordinate in range(2):
  parents=list(range(len(P)-1))
  def find(i):
   while parents[i]!=i:parents[i]=parents[parents[i]];i=parents[i]
   return i
  for i in range(len(P)-1):
   j=(i+1)%(len(P)-1)
   if abs(P[i,coordinate]-P[j,coordinate])<.0001:parents[find(i)]=find(j)
  for root in set(map(find,range(len(P)-1))):
   ids=[i for i in range(len(P)-1) if find(i)==root];P[ids,coordinate]=np.mean(P[ids,coordinate])
 P[-1]=P[0]
 if len(P)-1>32:raise ValueError('El perfil medido requiere más de treinta y dos tramos')
 edges=[cq.Edge.makeLine(cq.Vector(*(origin+u*a[0]+axis*a[1])),cq.Vector(*(origin+u*b[0]+axis*b[1]))) for a,b in zip(P[:-1],P[1:])]
 wire=cq.Wire.assembleEdges(edges);proof=dict(type='source_supported_lines',segments=len(edges),points=original_profile.tolist(),profile=P.tolist(),simplificacion_meridiano_mm=.00008,ajuste_circular_confirmado_mm=.004,cilindros_confirmados=confirmed,propuesta_no_es_aceptacion=True)
 shape=solido_finito(cq.Solid.revolve(wire,[],360,cq.Vector(*origin),cq.Vector(*(origin+axis))).clean())
 if len(shape.Solids())!=1 or not shape.isValid():raise ValueError('Revolución inválida')
 return shape,proof


def proponer(mesh,estrategia="marco_centrado"):
 if estrategia=="cortes_previos":
  shape,proof=_proponer_local(mesh,cortes_antes=True,calibrar_vertices=True);proof["estrategia_construccion"]=estrategia
  return shape,proof
 if estrategia!="marco_centrado":raise ValueError("Estrategia de construcción desconocida")
 # Construct in an orthonormal, centred measured cap frame. Keep world
 # coordinates unchanged in the delivered solid and in all source probes.
 axes=ejes(mesh)
 if not axes:raise ValueError('Sin marco axial medido')
 axis=axes[0];u,v=base(axis);R=np.column_stack([u,-v,axis]);C=np.asarray(mesh.vertices).mean(0)
 T=np.eye(4);T[:3,:3]=R.T;T[:3,3]=-R.T@C
 local=mesh.copy();local.apply_transform(T)
 shape,proof=_proponer_local(local)
 inverse=np.eye(4);inverse[:3,:3]=R;inverse[:3,3]=C
 from OCP.gp import gp_Trsf
 transform=gp_Trsf();transform.SetValues(*map(float,inverse[:3].ravel()))
 shape=solido_finito(shape.transformShape(cq.Matrix(transform)))
 visited=set()
 def restore(value):
  if isinstance(value,dict):
   if id(value)in visited:return
   visited.add(id(value))
   for k,x in list(value.items()):
    if k in ('eje','normal','direccion_meridiana')and isinstance(x,list)and len(x)==3:value[k]=(R@np.asarray(x)).tolist()
    elif k in ('origen','punto','centro_lateral','origen_nucleo')and isinstance(x,(list,tuple))and len(x)==3:value[k]=(R@np.asarray(x)+C).tolist()
    else:restore(x)
  elif isinstance(value,list):
   for x in value:restore(x)
 restore(proof);proof['marco_construccion_centrado']=True;proof['estrategia_construccion']=estrategia
 return shape,proof
