"""Pruebas de geometría medida y conservación de la ruta ya aprobada."""
from pathlib import Path
import sys,io,json
import numpy as np,pytest,trimesh
sys.path.insert(0,str(Path(__file__).parent/'motor_superficies'))
from OCP.Geom import Geom_BSplineCurve,Geom_SurfaceOfLinearExtrusion,Geom_Plane
from OCP.gp import gp_Pnt,gp_Dir,gp_Pln

def profile():
 from OCP.TColgp import TColgp_Array1OfPnt
 from OCP.TColStd import TColStd_Array1OfReal,TColStd_Array1OfInteger
 P=TColgp_Array1OfPnt(1,7)
 for i,p in enumerate([(0,0,0),(.2,0,.8),(.8,0,1),(1,0,1),(1.2,0,1),(1.8,0,.8),(2,0,0)],1):P.SetValue(i,gp_Pnt(*p))
 K=TColStd_Array1OfReal(1,3);M=TColStd_Array1OfInteger(1,3)
 for i,(k,m) in enumerate([(0,4),(1,3),(2,4)],1):K.SetValue(i,k);M.SetValue(i,m)
 return Geom_BSplineCurve(P,K,M,3,False)

def test_importar_constructor_no_parchea_la_ruta_anterior():
 import contornos_compatibles as old,pcurvas_compartidas as pc
 functions=(old._interseccion,old.refinar_interseccion,pc.crear_pcurva)
 import constructor_barridos,geometria_medida
 assert (old._interseccion,old.refinar_interseccion,pc.crear_pcurva)==functions
 assert constructor_barridos._interseccion is geometria_medida.intersection_stable

@pytest.mark.parametrize('reverse',[False,True])
def test_segmento_uv_cruza_nudo_y_conserva_toda_la_curva(reverse):
 from tramos_barridos import segmento
 surface=Geom_SurfaceOfLinearExtrusion(profile(),gp_Dir(0,1,0));a=np.array([.12,-2.]);b=np.array([1.8,5.])
 if reverse:a,b=b,a
 curve=segmento(surface,a,b);lo,hi=curve.FirstParameter(),curve.LastParameter()
 for t in np.linspace(0,1,257):
  uv=a+(b-a)*t
  assert curve.Value(float(lo+(hi-lo)*t)).Distance(surface.Value(*map(float,uv)))<1e-11

@pytest.mark.parametrize('reverse',[False,True])
def test_corte_oblicuo_exacto_conserva_pcurva_y_nudos(reverse):
 from curvas_barridas import interseccion_afine
 from pcurvas_compartidas import _error
 from geometria_medida import UV_KNOWN
 surface=Geom_SurfaceOfLinearExtrusion(profile(),gp_Dir(0,1,0));normal=np.array([.3,1.,.2]);normal/=np.linalg.norm(normal);q=np.array([0.,.7,0.]);plane=Geom_Plane(gp_Pln(gp_Pnt(*q),gp_Dir(*normal)))
 points=[]
 for u in np.linspace(.1,1.9,37):
  p=np.array(profile().Value(float(u)).Coord());points.append(p+np.array([0,1,0])*((q-p)@normal/normal[1]))
 points=np.array(points)
 if reverse:points=points[::-1]
 curve,lo,hi=interseccion_afine(surface,plane,points,.012,False)
 assert _error(curve,UV_KNOWN[id(curve),id(surface)],surface,lo,hi)<5e-8
 assert np.linalg.norm(np.array(curve.Value(lo).Coord())-points[0])<1e-9
 for t in np.linspace(lo,hi,257):assert abs((np.array(curve.Value(float(t)).Coord())-q)@normal)<1e-10

@pytest.mark.parametrize('sections,accepted',[(6,False),(12,False),(96,True)])
def test_cilindro_certifica_interior_de_facetas_y_veta_poligonos(sections,accepted):
 from extension_cilindros import propuestas
 mesh=trimesh.creation.cylinder(radius=2,height=3,sections=sections)
 side=np.flatnonzero(abs(mesh.face_normals[:,2])<.1);points=mesh.vertices[np.unique(mesh.faces[side])]
 req=dict(eje=np.array([0.,0.,1.]),centro=np.zeros(3),radio=2.,puntos=points,max_entrada_mm=0.)
 result=propuestas(mesh,[req]);ids=result[0][0]
 assert (len(ids)==len(side))==accepted
 if not accepted:assert len(ids)==0
 assert all(abs(mesh.face_normals[ids,2])<.1)

@pytest.mark.parametrize('code,ok',[(0,True),(2,False)])
def test_resultados_no_aptos_se_conservan_y_errores_no_invocan_mejora(tmp_path,monkeypatch,capsys,code,ok):
 import motor_v2,reconstruccion_medida as measured
 source=tmp_path/'una.stl';source.write_bytes(trimesh.creation.box().export(file_type='stl'));destination=tmp_path/'modelo.step';destination.write_bytes(b'RESULTADO ANTERIOR');monkeypatch.setattr(sys,'argv',['motor',str(source),str(destination)])
 calls=[]
 def main():print(json.dumps({'ok':ok,'resultado':{'calidad':{'caras_step':6}}}));return code
 def reject(*a,**k):calls.append(True);raise OSError('Fallo aislado simulado')
 monkeypatch.setattr(measured,'intentar_refinar',reject)
 assert measured.ejecutar_principal(main,motor_v2._SalidaCad,None)==code
 payload=json.loads(capsys.readouterr().out.splitlines()[-1]);assert payload['ok']==ok
 assert destination.read_bytes()==b'RESULTADO ANTERIOR' and len(calls)==int(ok)

@pytest.mark.parametrize('route',['entrada','base','informe'])
def test_trabajador_no_puede_sobrescribir_entrada_o_base(tmp_path,route):
 from reconstruccion_medida import trabajador
 source=tmp_path/'origen.stl';base=tmp_path/'previo.step';report=tmp_path/'reporte.json';source.write_bytes(b'STL INTACTO');base.write_bytes(b'STEP INTACTO')
 destination={'entrada':source,'base':base,'informe':report}[route]
 with pytest.raises(ValueError,match='distintas'):trabajador(source,base,destination,report)
 assert source.read_bytes()==b'STL INTACTO' and base.read_bytes()==b'STEP INTACTO'

def test_geometria_de_perfil_no_depende_del_nombre(tmp_path):
 from reconstruccion_medida import exigir_elegible
 import cadquery as cq
 with pytest.raises(ValueError,match='compacta'):exigir_elegible(cq.Workplane('XY').box(1,2,3).val())

@pytest.mark.parametrize('reverse',[False,True])
def test_agujero_cruza_perfil_sin_exigir_parametro_monotono(reverse):
 from curvas_barridas import interseccion_angular
 from geometria_medida import UV_KNOWN
 from pcurvas_compartidas import _error
 from OCP.Geom import Geom_CylindricalSurface
 from OCP.gp import gp_Ax3
 from scipy.optimize import brentq
 surface=Geom_SurfaceOfLinearExtrusion(profile(),gp_Dir(0,1,0));cylinder=Geom_CylindricalSurface(gp_Ax3(gp_Pnt(1,0,0),gp_Dir(0,0,1)),.8);points=[]
 for theta in np.linspace(-2,2,79):
  p=np.array(cylinder.Value(float(theta),0.).Coord());u=brentq(lambda u:profile().Value(u).X()-p[0],0,2);p[2]=profile().Value(u).Z();points.append(p)
 points=np.array(points)
 if reverse:points=points[::-1]
 curve,lo,hi=interseccion_angular(surface,cylinder,points,.012,False)
 assert _error(curve,UV_KNOWN[id(curve),id(cylinder)],cylinder,lo,hi)<5e-8
 for t in np.linspace(lo,hi,257):
  p=np.array(curve.Value(float(t)).Coord());assert abs(np.hypot(p[0]-1,p[1])-.8)<2e-8
 assert np.linalg.norm(np.array(curve.Value(lo).Coord())-points[0])<2e-7

@pytest.mark.parametrize('failure',['worker_failure','timeout','bad_source_sha','bad_base_sha','bad_step_sha','parent_validation','base_changed'])
def test_fallo_aislado_no_publica_candidato(tmp_path,monkeypatch,failure):
 import reconstruccion_medida as module,calidad_topologica,control_recursos,cadquery as cq
 source=tmp_path/'original.stl';source.write_bytes(b'original');base=tmp_path/'previo.step';base.write_bytes(b'previo validado');previous=base.read_bytes();mesh=trimesh.creation.box();shape=cq.Workplane('XY').box(1,2,3).val()
 monkeypatch.setattr(calidad_topologica,'leer_solido_step_estricto',lambda p:shape);monkeypatch.setattr(module,'exigir_elegible',lambda s:None)
 counts=iter([1000,100]);monkeypatch.setattr(module,'inventario',lambda shape:{'caras':next(counts),'cilindros':2})
 module._RECHAZOS_TRABAJADOR.clear()
 class Process:
  def __init__(self,args,**kwargs):self.args=args;self.returncode=2 if failure=='worker_failure' else 0
  def __enter__(self):return self
  def __exit__(self,*a):pass
 monkeypatch.setattr(module.subprocess,'Popen',Process)
 def communicate(proc,*args):
  if failure=='timeout':raise control_recursos.LimiteRecursos('Tiempo agotado simulado')
  candidate,report=map(Path,proc.args[-2:]);candidate.write_bytes(b'propuesta sin validar')
  record={'ok':True,'base_sha256':module._sha(base),'original_sha256':module._sha(source),'step_sha256':module._sha(candidate)}
  for kind,field in [('bad_source_sha','original_sha256'),('bad_base_sha','base_sha256'),('bad_step_sha','step_sha256')]:
   if failure==kind:record[field]='0'*64
  if failure=='base_changed':base.write_bytes(b'cambio externo no sobreescribir')
  report.write_text(json.dumps(record));return '',None,1.
 monkeypatch.setattr(control_recursos,'comunicar_vigilado',communicate)
 def reject(*a):raise ValueError('Validación del padre rechazada')
 with pytest.raises((ValueError,RuntimeError)):module.intentar_refinar(source,base,mesh,reject,io.StringIO())
 assert base.read_bytes()==(b'cambio externo no sobreescribir' if failure=='base_changed' else previous)
 assert source.read_bytes()==b'original'

def test_planos_compartidos_se_concilian_con_cota_en_todos_los_triangulos():
 from planos_medidos import proponer,conciliar
 from OCP.Geom import Geom_CylindricalSurface
 from OCP.gp import gp_Ax3
 import meshfit_brep
 mesh=trimesh.creation.box(extents=[2,3,4]);normals=mesh.face_normals.copy();labels=np.argmax(abs(normals),axis=1)*2+(normals.sum(1)>0);surfaces={}
 # Ruido de vértices de fuente: dos triángulos ya no definen un plano exacto.
 rng=np.random.default_rng(718);mesh.vertices+=rng.uniform(-3e-5,3e-5,size=mesh.vertices.shape)
 for r,ids in meshfit_brep._groups(labels).items():surfaces[r]=meshfit_brep._facet_surface(mesh,int(ids[0]))
 labels,surfaces,proof=proponer(mesh,labels,surfaces)
 surfaces[-1]=Geom_CylindricalSurface(gp_Ax3(gp_Pnt(),gp_Dir(0,0,1)),1.);surfaces[-2]=Geom_SurfaceOfLinearExtrusion(profile(),gp_Dir(0,1,0))
 result=conciliar(mesh,labels,surfaces)
 for r,ids in meshfit_brep._groups(labels).items():
  s=result[r];n=np.array(s.Axis().Direction().Coord());q=np.array(s.Location().Coord());P=mesh.vertices[mesh.faces[ids]]
  assert abs((P-q)@n).max()<=1e-4

@pytest.mark.parametrize('deviation',[0.,.0002])
def test_subdivision_cierra_ambos_lados_sin_uniones_en_t(deviation):
 from refinamiento_contorno import dividir
 mesh=trimesh.creation.box();original=mesh.vertices.copy();a,b=map(int,mesh.edges_unique[0]);A,B=mesh.vertices[[a,b]];points=[A*.75+B*.25+np.array([0,0,deviation]),A*.25+B*.75];labels=np.arange(len(mesh.faces))
 result,new_labels,record=dividir(mesh,labels,(a,b),points)
 assert result.is_watertight and result.is_winding_consistent and result.euler_number==mesh.euler_number
 assert len(result.faces)==len(mesh.faces)+4 and len(new_labels)==len(result.faces)
 assert np.array_equal(mesh.vertices,original)

def test_subdivision_fuera_de_cota_no_cambia_entrada():
 from refinamiento_contorno import dividir
 mesh=trimesh.creation.box();labels=np.arange(len(mesh.faces));a,b=map(int,mesh.edges_unique[0]);point=mesh.vertices[[a,b]].mean(0)+np.array([.1,.2,.3]);original=mesh.vertices.copy()
 with pytest.raises(ValueError,match='acotada'):dividir(mesh,labels,(a,b),[point])
 assert np.array_equal(mesh.vertices,original)

def test_prioridad_planos_no_aplana_curva_fuera_de_cota():
 from extension_planos import propuestas
 import meshfit_brep as base
 mesh=trimesh.creation.box(extents=[1,2,3]);n=np.array([1.,0.,0.]);plane_ids=np.flatnonzero(np.all(abs(mesh.triangles[:,:,0]-.5)<1e-12,axis=1));result={'primitives':[{'type':'plane','normal':n,'point':np.array([.5,0,0]),'faces':plane_ids}]}
 extras=propuestas(result,mesh)
 assert len(extras)==1 and set(extras[0][0])==set(plane_ids)
 moved=mesh.copy();v=int(moved.faces[plane_ids[0],0]);moved.vertices[v,0]+=.001
 extra=propuestas(result,moved)
 assert all(v not in moved.faces[i] for ids,s in extra for i in ids)

def test_guia_recortada_recupera_perfil_completo_desde_el_stl():
 from OCP.Geom import Geom_Ellipse
 from OCP.gp import gp_Ax2
 from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
 import cadquery as cq
 from barridos_medidos import ajustar
 ellipse=Geom_Ellipse(gp_Ax2(gp_Pnt(),gp_Dir(0,-1,0),gp_Dir(1,0,0)),2.,1.);surface=Geom_SurfaceOfLinearExtrusion(ellipse,gp_Dir(0,1,0));guide=cq.Face(BRepBuilderAPI_MakeFace(surface,.35,1.05,-2.5,2.5,1e-7).Face())
 theta=np.linspace(0,np.pi/2,33);curve=np.array([ellipse.Value(float(t)).Coord() for t in theta]);cross=np.vstack((np.zeros(3),curve));n=len(cross);vertices=np.vstack((cross+np.array([0,-2.5,0]),cross+np.array([0,2.5,0])));faces=[];side=[]
 for i in range(1,n-1):
  side.extend([len(faces),len(faces)+1]);faces.extend([[i,i+1,i+n],[i+1,i+1+n,i+n]])
 for a,b in [(0,1),(n-1,0)]:faces.extend([[a,b,a+n],[b,b+n,a+n]])
 for i in range(1,n-1):faces.extend([[0,i,i+1],[n,i+1+n,i+n]])
 mesh=trimesh.Trimesh(vertices,np.array(faces),process=False);mesh.fix_normals();assert mesh.is_watertight
 excluded=np.setdiff1d(np.arange(len(mesh.faces)),side);new,ids,proof=ajustar(guide,surface,mesh,[np.array([0.,1.,0.])],excluded,source_ids=np.array(side))
 assert set(ids)==set(side)
 assert proof['max_testigos_mm']<=.003 and proof['max_curva_polilinea_mm']<=.003

def line_profile(points):
 from OCP.TColgp import TColgp_Array1OfPnt
 from OCP.TColStd import TColStd_Array1OfReal,TColStd_Array1OfInteger
 P=TColgp_Array1OfPnt(1,4)
 for i,p in enumerate(points,1):P.SetValue(i,gp_Pnt(*p))
 K=TColStd_Array1OfReal(1,2);M=TColStd_Array1OfInteger(1,2)
 for i,t in enumerate((0.,1.),1):K.SetValue(i,t);M.SetValue(i,4)
 return Geom_BSplineCurve(P,K,M,3,False)

def test_barridos_paralelos_comparten_generatriz_y_ambas_pcurvas():
 from curvas_barridas import interseccion_barridos_paralelos
 from geometria_medida import UV_KNOWN
 from pcurvas_compartidas import _error
 ca=line_profile([(-1,0,-1),(-1/3,0,-1/3),(1/3,0,1/3),(1,0,1)]);cb=line_profile([(-1,5,1),(-1/3,5,1/3),(1/3,5,-1/3),(1,5,-1)])
 A=Geom_SurfaceOfLinearExtrusion(ca,gp_Dir(0,1,0));B=Geom_SurfaceOfLinearExtrusion(cb,gp_Dir(0,1,0));points=np.array([[0.,y,0.] for y in np.linspace(-2,3,11)]);curve,lo,hi=interseccion_barridos_paralelos(A,B,points,.012,False)
 for surface in (A,B):assert _error(curve,UV_KNOWN[id(curve),id(surface)],surface,lo,hi)<5e-8
 assert np.linalg.norm(np.array(curve.Value(lo).Coord())-points[0])<1e-9

def test_dos_perfiles_cruzados_conservan_la_misma_curva_espacial():
 from curvas_barridas import interseccion_barridos_cruzados
 from geometria_medida import UV_KNOWN
 from pcurvas_compartidas import _error
 ca=line_profile([(-1,0,1),(-1/3,0,-1/3),(1/3,0,-1/3),(1,0,1)]);cb=line_profile([(-1,.5,0),(-1/3,-1/6,0),(1/3,-1/6,0),(1,.5,0)])
 A=Geom_SurfaceOfLinearExtrusion(ca,gp_Dir(0,1,0));B=Geom_SurfaceOfLinearExtrusion(cb,gp_Dir(0,0,1));points=np.array([[x,x*x/2,x*x] for x in np.linspace(-.8,.8,19)]);curve,lo,hi=interseccion_barridos_cruzados(A,B,points,.012,False)
 for surface in (A,B):assert _error(curve,UV_KNOWN[id(curve),id(surface)],surface,lo,hi)<5e-8
 for t in np.linspace(lo,hi,129):
  p=np.array(curve.Value(float(t)).Coord());assert abs(p[1]-p[0]**2/2)<5e-8 and abs(p[2]-p[0]**2)<5e-8
