"""Geometría independiente, conservación de detalles y retorno seguro a R16."""
from pathlib import Path
import sys,io,json
import numpy as np,pytest,cadquery as cq,trimesh
import reconstruccion_fuente_r17 as route
from certificado_calidad_r15 import sha

@pytest.fixture
def kernel_imports(monkeypatch):
 root=Path(__file__).parent/'motor_calidad';monkeypatch.syspath_prepend(str(root));monkeypatch.syspath_prepend(str(root/'motor_superficies'))


def mesh_of(shape):
 V,F=shape.copy().tessellate(.001,angularTolerance=.06)
 return trimesh.Trimesh([p.toTuple()for p in V],F,process=True)


def bearing(pocket=False):
 shape=cq.Solid.makeCylinder(5,8).cut(cq.Solid.makeCylinder(2,8))
 if pocket:shape=shape.cut(cq.Solid.makeBox(.6,1.,.1,cq.Vector(3.,-.5,0)))
 return shape

@pytest.mark.parametrize('rotated',[False,True])
def test_eje_y_diametros_se_recuperan_en_un_casquillo_independiente(rotated,kernel_imports):
 from reconstruccion_axial_medida_r17 import proponer
 mesh=mesh_of(bearing());T=trimesh.transformations.rotation_matrix(.47,[1.,2.,3.]);T[:3,3]=[7.,-4.,2.]
 if rotated:mesh.apply_transform(T)
 before=(mesh.vertices.copy(),mesh.faces.copy());shape,proof=proponer(mesh)
 assert len(shape.Solids())==1 and len(shape.Faces())<=8
 assert {f.geomType()for f in shape.Faces()}<={'PLANE','CYLINDER','CONE'}
 assert abs(shape.Volume()-mesh.volume)/mesh.volume<.001
 expected=T[:3,2]if rotated else np.array([0.,0.,1.]);assert abs(np.array(proof['eje'])@expected)>1-1e-10
 assert np.array_equal(mesh.vertices,before[0])and np.array_equal(mesh.faces,before[1])


@pytest.mark.parametrize('rotated',[False,True])
def test_rebaje_pequeno_se_conserva_y_llenarlo_se_detecta(kernel_imports,rotated):
 from reconstruccion_axial_medida_r17 import proponer,comprobar_detalles
 mesh=mesh_of(bearing(True));original=bearing(False)
 if rotated:
  T=trimesh.transformations.rotation_matrix(.47,[1.,2.,3.]);T[:3,3]=[7.,-4.,2.];mesh.apply_transform(T);mesh.vertices=np.asarray(mesh.vertices,dtype=np.float32).astype(float);from OCP.gp import gp_Trsf
  transform=gp_Trsf();transform.SetValues(*map(float,T[:3].ravel()));original=original.transformShape(cq.Matrix(transform))
 shape,proof=proponer(mesh)
 assert len(proof['rebajes'])==1 and proof['rebajes'][0]['depth_mm']==pytest.approx(.1,abs=1e-5)
 result=comprobar_detalles(mesh,shape,proof);assert result['puntos']>=4 and result['discrepancias']==0
 with pytest.raises(ValueError,match='desaparecido|material'):comprobar_detalles(mesh,original,proof)


def test_elipse_no_se_sustituye_por_un_cilindro(kernel_imports):
 from reconstruccion_axial_medida_r17 import proponer
 mesh=mesh_of(bearing());mesh.vertices[:,0]*=1.2
 with pytest.raises(ValueError):proponer(mesh)


def test_taladro_hexagonal_no_se_redondea(kernel_imports):
 from reconstruccion_axial_medida_r17 import proponer
 p=[cq.Vector(2*np.cos(a),2*np.sin(a),0)for a in np.arange(6)*np.pi/3];wire=cq.Wire.makePolygon(p,close=True);shape=cq.Solid.makeCylinder(5,8).cut(cq.Solid.extrudeLinear(wire,[],cq.Vector(0,0,8)))
 with pytest.raises(ValueError):proponer(mesh_of(shape))


def test_la_guarda_no_intercepta_una_pieza_sin_tunel(tmp_path):
 mesh=trimesh.creation.icosphere(subdivisions=3);source=tmp_path/'pieza.stl';source.write_bytes(mesh.export(file_type='stl'));assert not route.elegible(source)


def test_salida_o_evidencia_no_pueden_ser_alias_del_original(tmp_path):
 source=tmp_path/'pieza.stl';source.write_bytes(b'original');destination=tmp_path/'pieza.step';alias=destination.with_suffix('.r17_nucleo.json');alias.hardlink_to(source)
 with pytest.raises(route.RutasIncompatibles):route.comprobar_rutas(source,destination)
 assert source.read_bytes()==b'original'


def test_rechazo_de_propuesta_conserva_archivos_y_delega_una_vez(tmp_path,monkeypatch,capsys):
 source=tmp_path/'pieza.stl';source.write_bytes(b'original');destination=tmp_path/'pieza.step';destination.write_bytes(b'anterior');before=(sha(source),sha(destination));calls=[];monkeypatch.setattr(sys,'argv',['motor_v2.py',str(source),str(destination)]);monkeypatch.setattr(route,'elegible',lambda p:True)
 def reject(*args):raise ValueError('Candidato no aprobado')
 monkeypatch.setattr(route,'intentar',reject)
 assert route.ejecutar(lambda:calls.append(True)or 7)==7 and calls==[True]
 assert (sha(source),sha(destination))==before


@pytest.mark.parametrize('kind',['cancelado','cambio'])
def test_cancelacion_o_entrada_cambiada_no_lanzan_otra_conversion(tmp_path,monkeypatch,capsys,kind):
 from perfeccion_calidad import EntradaCambiada
 from control_recursos import LimiteRecursos
 source=tmp_path/'pieza.stl';source.write_bytes(b'original');destination=tmp_path/'pieza.step';monkeypatch.setattr(sys,'argv',['motor_v2.py',str(source),str(destination)]);monkeypatch.setattr(route,'elegible',lambda p:True);calls=[]
 def reject(*args):raise LimiteRecursos('Cancelación',codigo='cancelado')if kind=='cancelado'else EntradaCambiada('Entrada cambiada')
 monkeypatch.setattr(route,'intentar',reject)
 assert route.ejecutar(lambda:calls.append(True)or 0)==2 and not calls
 assert json.loads(capsys.readouterr().out)['ok']is False


def test_desactivar_nueva_ruta_delega_sin_inspeccionar_archivo(monkeypatch):
 monkeypatch.setenv('VISOR_RECONSTRUCCION_FUENTE_R17','0');monkeypatch.setattr(sys,'argv',['motor_v2.py','no-existe.stl','salida.step']);assert route.ejecutar(lambda:11)==11
