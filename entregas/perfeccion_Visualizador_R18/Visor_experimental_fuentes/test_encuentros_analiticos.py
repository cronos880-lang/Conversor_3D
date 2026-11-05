"""Regresiones de límites, prioridad, parametrización y escritura del rescate R10."""
from pathlib import Path
import sys,io
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parent/'motor_superficies'))
import cadquery as cq
from OCP.Geom import Geom_Ellipse,Geom_Circle,Geom_BSplineCurve,Geom_Plane,Geom_CylindricalSurface
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.gp import gp_Ax2,gp_Ax3,gp_Pnt,gp_Dir,gp_Pln
from encuentros_analiticos import extend_profile,normalizar_circulos,intersection_stable

def test_perfil_extendido_conserva_intervalo_y_derivadas():
    from OCP.TColgp import TColgp_Array1OfPnt
    from OCP.TColStd import TColStd_Array1OfReal,TColStd_Array1OfInteger
    p=TColgp_Array1OfPnt(1,4)
    for i,xyz in enumerate([(0,0,0),(1,2,0),(2,-1,0),(3,0,0)],1):p.SetValue(i,gp_Pnt(*xyz))
    k=TColStd_Array1OfReal(1,2);m=TColStd_Array1OfInteger(1,2)
    for i,t in enumerate((2.,7.),1):k.SetValue(i,t);m.SetValue(i,4)
    curve=Geom_BSplineCurve(p,k,m,3,False);out=extend_profile(curve)
    for t in np.linspace(2,7,201):assert curve.Value(float(t)).Distance(out.Value(float(t)))<1e-12
    for t in (2,7):
        for n in (1,2,3):
            # Derivadas: medir el error físico de Taylor en el tramo añadido.
            # El parámetro no es una distancia y D3 amplifica el redondeo.
            import math
            delta=curve.DN(t,n).Subtracted(out.DN(t,n)).Magnitude()
            assert delta*.03**n/math.factorial(n)<1e-12
    assert out.FirstParameter()<2 and out.LastParameter()>7

def test_perfil_no_cubico_rechazado():
    with pytest.raises((ValueError,AttributeError)):extend_profile(Geom_Circle(gp_Ax2(),2))

@pytest.mark.parametrize('minor,expected',[(3.,1),(2.999,0)])
def test_solo_elipse_circular_se_canoniza(minor,expected):
    curve=Geom_Ellipse(gp_Ax2(gp_Pnt(1,2,3),gp_Dir(0,1,0)),3.,minor)
    edge=cq.Edge(BRepBuilderAPI_MakeEdge(curve,.2,2.1).Edge())
    oldtol=BRep_Tool.Tolerance_s(edge.wrapped)
    points=[curve.Value(float(t)) for t in np.linspace(.2,2.1,41)]
    assert normalizar_circulos(edge)==expected
    a=BRepAdaptor_Curve(edge.wrapped);new=BRep_Tool.Curve_s(edge.wrapped,a.FirstParameter(),a.LastParameter())
    assert isinstance(new,Geom_Circle if expected else Geom_Ellipse)
    assert BRep_Tool.Tolerance_s(edge.wrapped)==oldtol
    assert max(p.Distance(new.Value(float(t))) for p,t in zip(points,np.linspace(.2,2.1,41)))<1e-12

@pytest.mark.parametrize('angle',[0.,.37,1.4])
def test_interseccion_plano_cilindro_paralelo_rotado(angle):
    # Dos generatrices reales; escoger la que se aproxima al borde medido.
    axis=np.array([np.sin(angle),0.,np.cos(angle)]);normal=np.array([np.cos(angle),0.,-np.sin(angle)])
    center=np.array([3.,-4.,2.]);surf=Geom_CylindricalSurface(gp_Ax3(gp_Pnt(*center),gp_Dir(*axis)),2.)
    plane=Geom_Plane(gp_Pln(gp_Pnt(*(center+normal)),gp_Dir(*normal)))
    radial=normal+np.array([0.,np.sqrt(3),0.]);pts=np.array([center+radial+t*axis for t in np.linspace(-3,7,33)])
    curve,lo,hi=intersection_stable(plane,surf,pts,.06,False)
    for t in np.linspace(lo,hi,65):
        p=np.array(curve.Value(float(t)).Coord())
        assert abs((p-center)@normal-1)<5e-8
        assert abs(np.linalg.norm(np.cross(p-center,axis))-2)<5e-8
    assert np.linalg.norm(np.array(curve.Value(lo).Coord())-pts[0])<1e-7
    assert np.linalg.norm(np.array(curve.Value(hi).Coord())-pts[-1])<1e-7

def test_prioridad_R9_sin_invocar_rescate(monkeypatch):
    import reconstruccion_curvas as old
    import reconstruccion_analitica as new
    sentinel=(object(),object())
    monkeypatch.setattr(old,'_intentar_refinar_R9',lambda *a,**k:sentinel)
    def forbidden(*a,**k):raise AssertionError('No sustituir una reconstrucción aprobada')
    monkeypatch.setattr(new,'intentar_refinar',forbidden)
    assert old.intentar_refinar(None,None,None,None,io.StringIO()) is sentinel

def test_rescate_solo_despues_de_rechazo(monkeypatch):
    import reconstruccion_curvas as old
    import reconstruccion_analitica as new
    def decline(*a,**k):raise ValueError('R9 rechazado')
    monkeypatch.setattr(old,'_intentar_refinar_R9',decline)
    sentinel=(object(),object());monkeypatch.setattr(new,'intentar_refinar',lambda *a,**k:sentinel)
    assert old.intentar_refinar(None,None,None,None,io.StringIO()) is sentinel

def test_rechazo_no_toca_base(tmp_path):
    from reconstruccion_analitica import intentar_refinar
    base=tmp_path/'base.step';base.write_bytes(b'BASE CONSERVADA')
    class NotEligible:
        faces=range(20001)
    with pytest.raises(ValueError):intentar_refinar(tmp_path/'entrada.stl',base,NotEligible(),None,io.StringIO())
    assert base.read_bytes()==b'BASE CONSERVADA'

def test_superficie_libre_y_toro_no_verificados_rechazados():
    from reconstruccion_analitica import exigir_elegible
    exigir_elegible(cq.Workplane('XY').box(1,2,3).val())
    with pytest.raises(ValueError):exigir_elegible(cq.Solid.makeTorus(3.,1.))

@pytest.mark.parametrize('failure',['worker_failure','timeout','bad_source_sha','bad_step_sha','parent_validation'])
def test_trabajador_rechazado_jamas_publica(tmp_path,monkeypatch,failure):
    import json,hashlib
    import reconstruccion_analitica as module
    import calidad_topologica,control_recursos
    source=tmp_path/'entrada.stl';source.write_bytes(b'entrada original')
    base=tmp_path/'base.step';base.write_bytes(b'candidato anterior sin modificar')
    original_bytes=base.read_bytes()
    shape=cq.Workplane('XY').circle(2).extrude(3).val()
    mesh=__import__('trimesh').creation.box()
    module._RECHAZOS_TRABAJADOR.clear()
    monkeypatch.setattr(calidad_topologica,'leer_solido_step_estricto',lambda p:shape)
    class Process:
        def __init__(self,args,**kwargs):self.args=args;self.returncode=2 if failure=='worker_failure' else 0
        def __enter__(self):return self
        def __exit__(self,*a):pass
    monkeypatch.setattr(module.subprocess,'Popen',Process)
    def communicate(proc,*args):
        if failure=='timeout':raise control_recursos.LimiteRecursos('Tiempo agotado simulado')
        candidate,report=map(Path,proc.args[-2:]);candidate.write_bytes(b'propuesta nunca aprobada')
        record={'ok':True,'base_sha256':module._sha(base),'original_sha256':module._sha(source),'step_sha256':module._sha(candidate)}
        if failure=='bad_source_sha':record['original_sha256']='0'*64
        if failure=='bad_step_sha':record['step_sha256']='1'*64
        report.write_text(json.dumps(record));return '',None,2.
    monkeypatch.setattr(control_recursos,'comunicar_vigilado',communicate)
    def refuse(*a):raise ValueError('Validación del padre rechazada')
    with pytest.raises((ValueError,RuntimeError)):
        module.intentar_refinar(source,base,mesh,refuse,io.StringIO())
    assert base.read_bytes()==original_bytes
    assert source.read_bytes()==b'entrada original'
