"""Independent CAD fixtures, finite material, original details and safe fallback."""
from pathlib import Path
import sys,json
import numpy as np,pytest,cadquery as cq,trimesh
import reconstruccion_fuente_r18 as route
from certificado_calidad_r15 import sha
from familia_axial_r18 import pertenece

@pytest.fixture
def kernel_imports(monkeypatch):
 root=Path(__file__).parent/'motor_calidad';monkeypatch.syspath_prepend(str(root));monkeypatch.syspath_prepend(str(root/'motor_superficies'))

def mesh_of(shape):
 V,F=shape.copy().tessellate(.0005,angularTolerance=.04)
 return trimesh.Trimesh(np.asarray([p.toTuple()for p in V],dtype=np.float32).astype(float),F,process=True)

def moved(shape):
 from OCP.gp import gp_Trsf
 T=trimesh.transformations.rotation_matrix(.43,[1,2,-3]);T[:3,3]=[13,-9,21];tr=gp_Trsf();tr.SetValues(*map(float,T[:3].ravel()));return shape.transformShape(cq.Matrix(tr))

def cylinder_with_pockets(deep=True,lower=True):
 s=cq.Solid.makeCylinder(6,9)
 if deep:s=s.cut(cq.Solid.makeBox(2,2,6,cq.Vector(-1,-1,3)))
 if lower:s=s.cut(cq.Solid.makeBox(1.2,.8,.12,cq.Vector(2.5,-.4,0)))
 return s.clean()

def ribbed(count=2,ceiling=9.925):
 s=cq.Solid.makeCylinder(6,10).cut(cq.Solid.makeCylinder(3,10))
 for k in range(count):
  tool=cq.Solid.makeBox(4,1.6,10.5 if k%2==0 else ceiling,cq.Vector(5,-.8,0)).rotate((0,0,0),(0,0,1),k*360/count);s=s.cut(tool)
 for k in range(count):
  P=[cq.Vector(x,-.8,z)for x,z in [(5,0),(9,0),(9,3),(5,10)]];tool=cq.Solid.extrudeLinear(cq.Wire.makePolygon(P,close=True),[],cq.Vector(0,1.6,0)).rotate((0,0,0),(0,0,1),k*360/count);s=s.fuse(tool)
 return s.clean()

@pytest.mark.parametrize('rotated',[False,True])
def test_disco_macizo_se_recupera_sin_agujero_y_sin_modificar_malla(kernel_imports,rotated):
 from reconstruccion_axial_compuesta_r18 import proponer
 reference=cq.Solid.makeCylinder(6,3);reference=moved(reference)if rotated else reference;mesh=mesh_of(reference);before=(mesh.vertices.copy(),mesh.faces.copy());shape,proof=proponer(mesh)
 assert pertenece(mesh)and len(shape.Faces())==3 and sum(f.geomType()=='CYLINDER'for f in shape.Faces())==1
 assert abs(shape.Volume()-reference.Volume())/reference.Volume()<.0005
 assert np.array_equal(mesh.vertices,before[0])and np.array_equal(mesh.faces,before[1])

@pytest.mark.parametrize('reverse',[False,True])
def test_meridiano_en_ambos_sentidos_define_material_finito_y_booleanos_correctos(kernel_imports,reverse):
 from reconstruccion_axial_compuesta_r18 import _revolver_perfil_r18
 from OCP.BRepClass3d import BRepClass3d_SolidClassifier
 from OCP.TopAbs import TopAbs_OUT,TopAbs_IN
 from OCP.gp import gp_Pnt
 P=np.array([[0,0],[6,0],[6,3],[0,3],[0,0]],float);P=P[::-1]if reverse else P
 shape,proof=_revolver_perfil_r18(P,np.zeros(3),np.array([0.,0.,1.]),np.array([1.,0.,0.]))
 classifier=BRepClass3d_SolidClassifier(shape.wrapped);classifier.PerformInfinitePoint(1e-7);assert classifier.State()==TopAbs_OUT
 classifier.Perform(gp_Pnt(2,0,1),1e-7);assert classifier.State()==TopAbs_IN
 assert shape.Volume()-shape.cut(cq.Solid.makeBox(1,1,1,cq.Vector(.5,.5,.5))).Volume()==pytest.approx(1.,abs=1e-7)

@pytest.mark.parametrize('rotated',[False,True])
def test_vaciado_profundo_y_rebaje_inferior_se_conservan_y_su_relleno_se_detecta(kernel_imports,rotated):
 from reconstruccion_axial_compuesta_r18 import proponer,comprobar_detalles_compuestos
 reference=cylinder_with_pockets();wrong=cylinder_with_pockets(deep=False)
 if rotated:reference=moved(reference);wrong=moved(wrong)
 mesh=mesh_of(reference);shape,proof=proponer(mesh)
 assert len(proof['rebajes'])==2 and max(g['depth_mm']for g in proof['rebajes'])==pytest.approx(6,abs=.0001)
 result=comprobar_detalles_compuestos(mesh,shape,proof);assert result['puntos']>=8 and result['discrepancias']==0
 with pytest.raises(ValueError,match='desaparecido|material'):comprobar_detalles_compuestos(mesh,wrong,proof)

@pytest.mark.parametrize('count',[2,3,4])
def test_refuerzos_y_techo_abierto_o_cubierto_de_cap_fino_se_conservan(kernel_imports,count):
 from reconstruccion_axial_compuesta_r18 import proponer,comprobar_detalles_compuestos
 reference=ribbed(count);reference=moved(reference)if count==2 else reference;mesh=mesh_of(reference);shape,proof=proponer(mesh)
 assert pertenece(mesh)and len(proof['refuerzos'])==count and proof['vaciados_abiertos_refuerzos']
 assert any(g.get('tipo')=='fondo_inclinado_medido'for g in proof['rebajes'])
 assert abs(shape.Volume()-reference.Volume())/reference.Volume()<.0005
 result=comprobar_detalles_compuestos(mesh,shape,proof);assert result['refuerzos']['puntos']>=4*count and result['refuerzos']['discrepancias']==0

def test_quitar_los_refuerzos_falla_su_control_dirigido(kernel_imports):
 from reconstruccion_axial_compuesta_r18 import proponer,comprobar_detalles_compuestos
 mesh=mesh_of(ribbed(2));shape,proof=proponer(mesh);wrong=cq.Solid.makeCylinder(6,10).cut(cq.Solid.makeCylinder(3,10))
 with pytest.raises(ValueError,match='material|desaparecido'):comprobar_detalles_compuestos(mesh,wrong,proof)

def test_anillo_simple_sigue_delegando_a_la_familia_r17():
 mesh=mesh_of(cq.Solid.makeCylinder(5,8).cut(cq.Solid.makeCylinder(2,8)))
 assert not pertenece(mesh)

@pytest.mark.parametrize('kind',['ellipse','hexagon'])
def test_no_redondea_perfiles_mecanicos_no_confirmados(kernel_imports,kind):
 from reconstruccion_axial_compuesta_r18 import proponer
 if kind=='ellipse':
  mesh=mesh_of(cq.Solid.makeCylinder(6,3));mesh.vertices[:,0]*=1.1
 else:
  P=[cq.Vector(6*np.cos(t),6*np.sin(t),0)for t in np.arange(6)*np.pi/3];s=cq.Solid.extrudeLinear(cq.Wire.makePolygon(P,close=True),[],cq.Vector(0,0,3));mesh=mesh_of(s)
 assert not pertenece(mesh)
 with pytest.raises(ValueError):proponer(mesh)

def test_original_no_puede_ser_alias_de_evidencias_r18(tmp_path):
 source=tmp_path/'original.stl';source.write_bytes(b'original');destination=tmp_path/'salida.step';destination.with_suffix('.r18_nucleo.json').hardlink_to(source)
 with pytest.raises(route.RutasIncompatibles):route.comprobar_rutas(source,destination)
 assert source.read_bytes()==b'original'

def test_propuesta_rechazada_delega_una_vez_y_conserva_original_y_salida(tmp_path,monkeypatch):
 source=tmp_path/'original.stl';source.write_bytes(b'original');destination=tmp_path/'salida.step';destination.write_bytes(b'previo');before=sha(source),sha(destination);calls=[]
 monkeypatch.setattr(sys,'argv',['motor_v2.py',str(source),str(destination)]);monkeypatch.setattr(route,'elegible',lambda p:True)
 def reject(*args):raise ValueError('Rechazado por validación')
 monkeypatch.setattr(route,'intentar',reject)
 assert route.ejecutar(lambda:calls.append(True)or 7)==7 and calls==[True]and (sha(source),sha(destination))==before

@pytest.mark.parametrize('kind',['cancelado','cambio'])
def test_cancelar_o_cambiar_entrada_no_inicia_otra_conversion(tmp_path,monkeypatch,capsys,kind):
 from perfeccion_calidad import EntradaCambiada
 from control_recursos import LimiteRecursos
 source=tmp_path/'original.stl';source.write_bytes(b'original');destination=tmp_path/'salida.step';calls=[]
 monkeypatch.setattr(sys,'argv',['motor_v2.py',str(source),str(destination)]);monkeypatch.setattr(route,'elegible',lambda p:True)
 def reject(*args):raise LimiteRecursos('Cancelación',codigo='cancelado')if kind=='cancelado'else EntradaCambiada('Entrada cambiada')
 monkeypatch.setattr(route,'intentar',reject)
 assert route.ejecutar(lambda:calls.append(True)or 0)==2 and not calls and json.loads(capsys.readouterr().out)['ok']is False

def test_desactivar_r18_no_inspecciona_el_archivo(monkeypatch):
 monkeypatch.setenv('VISOR_RECONSTRUCCION_FUENTE_R18','0');monkeypatch.setattr(sys,'argv',['motor_v2.py','no_existe.stl','salida.step'])
 def inspect(*args):raise AssertionError('No debe inspeccionar al estar desactivada')
 monkeypatch.setattr(route,'elegible',inspect);assert route.ejecutar(lambda:9)==9
