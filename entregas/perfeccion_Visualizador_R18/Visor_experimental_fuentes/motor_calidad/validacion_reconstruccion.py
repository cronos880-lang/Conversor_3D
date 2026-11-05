"""Invariantes adicionales de la recuperación numérica, sin ampliar tolerancias."""
import numpy as np

def certificar_malla(reference,candidate):
 if not np.array_equal(reference.faces,candidate.faces) or len(reference.vertices)!=len(candidate.vertices):raise ValueError('La reparación numérica ha cambiado la triangulación o sus componentes')
 delta=np.linalg.norm(candidate.vertices-reference.vertices,axis=1);roundoff=64*np.finfo(float).eps*(1+np.max(np.abs(reference.vertices)));bound=float(delta.max(initial=0.)+roundoff);volume=100*abs(candidate.volume-reference.volume)/max(abs(reference.volume),1e-30);bbox=float(np.abs(candidate.bounds-reference.bounds).max())
 if bound>.002 or volume>.001 or bbox>.002:raise ValueError('La estabilización excede el presupuesto geométrico local')
 return {'cota_global_superficie_mm':bound,'margen_redondeo_mm':float(roundoff),'volumen_error_pct':float(volume),'caja_error_mm':bbox,'caras_con_correspondencia':len(reference.faces),'fundamento':'Misma triangulación: cada punto baricéntrico se desplaza como máximo el mayor desplazamiento de sus vértices.','limites':{'superficie_mm':.002,'volumen_pct':.001,'caja_mm':.002}}

def euler_brep(solid):
 # Los contornos de un plano pueden tocarse en vértices compartidos. Contar
 # cada wire como agujero independiente atribuiría túneles inexistentes.
 contribution=0
 for face in solid.Faces():
  wires=face.Wires();parents=list(range(len(wires)));nodes=[wire.Vertices() for wire in wires]
  def find(i):
   while parents[i]!=i:parents[i]=parents[parents[i]];i=parents[i]
   return i
  for i in range(len(wires)):
   for j in range(i):
    if any(a.wrapped.IsSame(b.wrapped) for a in nodes[i] for b in nodes[j]):parents[find(i)]=find(j)
  contribution+=2-len({find(i) for i in range(len(wires))})
 return len(solid.Vertices())-len(solid.Edges())+contribution

def certificar_topologia_step(solid,mesh,invariants):
 import igl
 from OCP.BRepClass3d import BRepClass3d_SolidClassifier
 from OCP.TopAbs import TopAbs_IN,TopAbs_OUT
 from OCP.gp import gp_Pnt
 from proximidad_triangular import punto_mas_cercano
 expected_shells=len(invariants.groups);chi=euler_brep(solid)
 if len(solid.Solids())!=1 or len(solid.Shells())!=expected_shells or chi!=mesh.euler_number:raise ValueError('El STEP cambia cavidades o túneles de la malla de referencia')
 classifier=BRepClass3d_SolidClassifier(solid.wrapped);records=[];V,F=mesh.vertices,mesh.faces
 for gi in invariants.negative:
  faces=F[invariants.groups[gi]];T=V[faces];cross=np.cross(T[:,1]-T[:,0],T[:,2]-T[:,0]);normals=cross/np.linalg.norm(cross,axis=1)[:,None];centers=T.mean(1);points=[]
  for eps in np.geomspace(1e-8,.001,24):points.extend(centers+eps*normals)
  points=np.asarray(points);winds=igl.winding_number(V,faces,points);points=points[winds<-.75]
  if not len(points):raise ValueError('No se encuentra un punto interior verificable de una cavidad')
  distances=[]
  for p in points:
   q=punto_mas_cercano(T,np.tile(p,(len(T),1)));distances.append(float(np.linalg.norm(q-p,axis=1).min()))
  order=np.argsort(-np.asarray(distances));chosen=None
  for idx in order:
   if distances[idx]<4e-7:break
   p=points[idx];classifier.Perform(gp_Pnt(*map(float,p)),1e-10)
   if classifier.State()==TopAbs_OUT:chosen=(p,distances[idx]);break
  if chosen is None:raise ValueError('La cavidad ha desaparecido o su interior no es verificable en el STEP')
  material=None
  for eps in np.geomspace(5e-7,.001,16):
   for p in centers-eps*normals:
    classifier.Perform(gp_Pnt(*map(float,p)),1e-10)
    if classifier.State()==TopAbs_IN:material=p;break
   if material is not None:break
  if material is None:raise ValueError('No se verifica material alrededor de una cavidad')
  records.append({'componente':gi,'punto_vacio_mm':chosen[0].tolist(),'holgura_vacio_mm':chosen[1],'punto_material_mm':material.tolist(),'clasificacion_vacio':'OUT','clasificacion_material':'IN'})
 return {'euler_malla':int(mesh.euler_number),'euler_brep':int(chi),'shells':len(solid.Shells()),'cavidades_preservadas':len(records),'probes_cavidades':records}
