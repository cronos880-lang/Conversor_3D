"""Geometría independiente e inmutabilidad ante fallos del trabajador R16.

Las pruebas de archivo sustituyen deliberadamente al trabajador; no cuentan
como pruebas de conversión. La batería CAD completa usa los STL reales aparte.
"""
from pathlib import Path
import copy,io,json,sys
import numpy as np
import pytest
import cadquery as cq
from OCP.Geom import Geom_BSplineSurface,Geom_BSplineCurve
from OCP.GeomFill import GeomFill_BSplineCurves,GeomFill_StretchStyle
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.TColgp import TColgp_Array2OfPnt,TColgp_Array1OfPnt
from OCP.TColStd import TColStd_Array1OfReal,TColStd_Array1OfInteger
from OCP.gp import gp_Pnt,gp_Trsf,gp_Ax1,gp_Dir,gp_Vec
import reconstruccion_continua_r16 as route
from respaldo_conversion import guardar,recuperar
from certificado_calidad_r15 import sha

def array(cls,values):
    a=cls(1,len(values))
    for i,v in enumerate(values,1):a.SetValue(i,v)
    return a

@pytest.fixture
def kernel_imports(monkeypatch):
    root=Path(__file__).parent/'motor_calidad'
    monkeypatch.syspath_prepend(str(root))
    monkeypatch.syspath_prepend(str(root/'motor_superficies'))

@pytest.mark.parametrize('rotated',[False,True])
def test_ajuste_normal_corrige_ondulacion_sin_mover_la_carta_o_frontera(rotated,kernel_imports):
    from ajuste_interior_r16 import ajustar
    poles=TColgp_Array2OfPnt(1,4,1,4)
    for i in range(4):
        for j in range(4):poles.SetValue(i+1,j+1,gp_Pnt(10*i/3,4*j/3,.005 if i in (1,2) and j in (1,2) else 0.))
    knots=array(TColStd_Array1OfReal,[0.,1.]);mult=array(TColStd_Array1OfInteger,[4,4]);surface=Geom_BSplineSurface(poles,knots,knots,mult,mult,3,3,False,False)
    wire=cq.Wire.makePolygon([cq.Vector(*p) for p in [(0,0,0),(10,0,0),(10,4,0),(0,4,0)]],close=True);plane=cq.Face.makeFromWires(wire)
    if rotated:
        t=gp_Trsf();t.SetRotation(gp_Ax1(gp_Pnt(0,0,0),gp_Dir(1,2,3)),.41);t.SetTranslationPart(gp_Vec(100,-50,12));surface=surface.Transformed(t);plane=cq.Face(plane.wrapped.Moved(__import__('OCP.TopLoc',fromlist=['TopLoc_Location']).TopLoc_Location(t)))
    fitted,proof=ajustar(surface,[plane],spans=2)
    normal=np.array(plane.normalAt(plane.Center()).toTuple());origin=np.array(plane.Center().toTuple())
    uv=[(u,v) for u in np.linspace(0,1,23) for v in np.linspace(0,1,17)];before=np.array([surface.Value(float(u),float(v)).Coord() for u,v in uv]);after=np.array([fitted.Value(float(u),float(v)).Coord() for u,v in uv]);change=after-before
    assert np.max(abs((after-origin)@normal))<5e-5
    assert np.max(np.linalg.norm(change-np.outer(change@normal,normal),axis=1))<2e-11
    border=[(u,v) for u in [0.,1.] for v in np.linspace(0,1,17)]+[(u,v) for v in [0.,1.] for u in np.linspace(0,1,17)]
    assert max(surface.Value(float(u),float(v)).Distance(fitted.Value(float(u),float(v))) for u,v in border)<2e-11
    assert proof['regularidad_antes']['signo']==proof['regularidad_despues']['signo']

def test_no_confunde_brep_exacto_con_ausencia_de_pliegues(kernel_imports):
    from ajuste_interior_r16 import ajustar
    d=json.loads((Path(__file__).parent/'fixtures_cad/R16/carta_plegada.json').read_text());curves=[]
    for row in d['curvas']:
        p=TColgp_Array1OfPnt(1,len(row['polos']))
        for i,q in enumerate(row['polos'],1):p.SetValue(i,gp_Pnt(*q))
        curves.append(Geom_BSplineCurve(p,array(TColStd_Array1OfReal,row['pesos']),array(TColStd_Array1OfReal,row['nudos']),array(TColStd_Array1OfInteger,row['multiplicidades']),row['grado'],False))
    surface=GeomFill_BSplineCurves(*curves,GeomFill_StretchStyle).Surface();face=cq.Face(BRepBuilderAPI_MakeFace(surface,1e-7).Face())
    assert BRepCheck_Analyzer(face.wrapped,True,False,True).IsValid() is d['brep_exacto']
    # The source anchor establishes the expected wall normal independently.
    source=cq.Face.makeFromWires(cq.Wire.makePolygon([cq.Vector(*p) for p in [(239,0,0),(239,1,0),(239,1,1),(239,0,1)]],close=True))
    with pytest.raises(ValueError,match='pliega'):ajustar(surface,[source])

def test_identifica_la_cara_tras_step_y_no_una_superficie_distinta(tmp_path,kernel_imports):
    from reconstruccion_paredes_r16 import firma_cara,corresponde_firma
    p=TColgp_Array2OfPnt(1,2,1,2)
    for i in range(2):
        for j in range(2):p.SetValue(i+1,j+1,gp_Pnt(i,j,0.))
    k=array(TColStd_Array1OfReal,[0.,1.]);m=array(TColStd_Array1OfInteger,[2,2]);s=Geom_BSplineSurface(p,k,k,m,m,1,1,False,False);face=cq.Face(BRepBuilderAPI_MakeFace(s,1e-7).Face());signature=firma_cara(face)
    file=tmp_path/'anonimo.step';cq.exporters.export(face,str(file));reopened=cq.importers.importStep(str(file)).val().Faces()[0]
    assert corresponde_firma(reopened,signature)
    changed=s.Copy();changed.SetPole(2,2,gp_Pnt(1,1,.001));other=cq.Face(BRepBuilderAPI_MakeFace(changed,1e-7).Face())
    assert not corresponde_firma(other,signature)
    assert not corresponde_firma(cq.Face.makePlane(1,1),signature)

def payload(source,faces=134):
    from perfiles_precision import obtener_perfil
    return dict(ok=True,preprocesamiento=dict(reparado=False,original_sha256=sha(source)),resultado=dict(calidad=dict(caras_step=faces,tipos_caras=dict(GeomAbs_Plane=57,GeomAbs_Cylinder=25,GeomAbs_BSplineSurface=38,GeomAbs_SurfaceOfExtrusion=14),integridad_cad=dict(brep_valido=True,brep_exacto=True,solidos=1),autointerferencias_occ=False,sin_objetos_sueltos_en_step=True,inspeccion_densa=dict(aceptado=True),perfil_validacion=obtener_perfil('precision'),desviacion_max_verificada_mm=.003438,caja_error_mm=.000561,volumen_error_pct=.022032)))

@pytest.mark.parametrize('profile',['precision','impresion'])
def test_trabajador_conserva_el_perfil_aunque_el_lanzador_use_precision(profile,kernel_imports,monkeypatch):
    from reconstruccion_continua_worker_r16 import configurar_perfil
    from perfiles_precision import obtener_perfil
    requested=obtener_perfil(profile);spec=dict(perfil=requested,previous_quality=dict(perfil_validacion=copy.deepcopy(requested)))
    monkeypatch.setenv('VISOR_PERFIL','precision');configurar_perfil(spec)
    assert obtener_perfil()==requested
    altered=copy.deepcopy(spec);altered['perfil']['max_mm']*=10
    with pytest.raises(ValueError,match='límites'):configurar_perfil(altered)

def test_trabajador_desde_otra_carpeta_sin_pythonpath_del_programa(tmp_path):
    import subprocess,os,trimesh
    from perfiles_precision import obtener_perfil
    from certificado_calidad_r15 import firma_motor
    root=Path(__file__).parent.resolve();source=tmp_path/'entrada.stl';base=tmp_path/'base.step';destination=tmp_path/'propuesta.step';spec=tmp_path/'peticion.json';report=tmp_path/'informe.json'
    source.write_bytes(trimesh.creation.box(extents=[10,4,6]).export(file_type='stl'));cq.exporters.export(cq.Workplane('XY').box(10,4,6).val(),str(base));before=(source.read_bytes(),base.read_bytes());profile=obtener_perfil('precision')
    spec.write_text(json.dumps(dict(source_sha256=sha(source),base_sha256=sha(base),motor_sha256=firma_motor(root),nonce='prueba-importacion-aislada',perfil=profile,previous_quality=dict(perfil_validacion=profile))))
    external=[p for p in os.environ.get('PYTHONPATH','').split(os.pathsep) if p and not Path(p).resolve().is_relative_to(root)]
    env={**os.environ,'PYTHONPATH':os.pathsep.join(external),'VISOR_PERFIL':'precision','PYTHONDONTWRITEBYTECODE':'1','OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'}
    proc=subprocess.run([sys.executable,str(root/'motor_calidad/reconstruccion_continua_worker_r16.py'),str(source),str(base),str(destination),str(spec),str(report)],cwd=tmp_path,env=env,capture_output=True,text=True,timeout=45)
    assert proc.returncode==2 and report.is_file(),proc.stdout+proc.stderr
    data=json.loads(report.read_text());assert not data['ok'] and 'No hay paredes' in data['error']
    assert not destination.exists() and before==(source.read_bytes(),base.read_bytes())

def test_trabajador_rechazado_conserva_los_bytes_aprobados(tmp_path,monkeypatch):
    import perfeccion_calidad
    src=tmp_path/'entrada.stl';step=tmp_path/'pieza.step';src.write_bytes(b'original inmutable');step.write_bytes(b'resultado previo aprobado');prior=payload(src);before=step.read_bytes()
    def rejected(script,args,timeout,log):raise ValueError('El mallado fino contiene intersecciones')
    monkeypatch.setattr(perfeccion_calidad,'ejecutar_subproceso',rejected)
    with pytest.raises(ValueError,match='intersecciones'):route.intentar(src,step,prior,io.StringIO())
    assert src.read_bytes()==b'original inmutable' and step.read_bytes()==before

def test_entrada_cambiada_no_se_presenta_como_respaldo_valido(tmp_path,monkeypatch):
    import perfeccion_calidad
    src=tmp_path/'entrada.stl';step=tmp_path/'pieza.step';src.write_bytes(b'original');step.write_bytes(b'CAD previo');prior=payload(src)
    def changed(script,args,timeout,log):src.write_bytes(b'entrada distinta');raise ValueError('Rechazo del trabajador')
    monkeypatch.setattr(perfeccion_calidad,'ejecutar_subproceso',changed)
    with pytest.raises(perfeccion_calidad.EntradaCambiada,match='Cambió una entrada'):route.intentar(src,step,prior,io.StringIO())
    assert step.read_bytes()==b'CAD previo'

def test_respaldo_r16_tiene_prioridad_y_no_anula_cancelacion(tmp_path):
    src=tmp_path/'entrada.stl';step=tmp_path/'pieza.step';src.write_bytes(b'original');step.write_bytes(b'R14');old=payload(src,190);guardar(src,step,old,etapa='r14')
    step.write_bytes(b'R15');recent=payload(src);guardar(src,step,recent,etapa='r16');step.write_bytes(b'salida incompleta')
    assert recuperar(src,step,perfil='precision',motivo='cancelado',cancelado=True) is None
    assert step.read_bytes()==b'salida incompleta'
    recovered=recuperar(src,step,perfil='precision',motivo='tiempo agotado')
    assert step.read_bytes()==b'R15' and recovered['resultado']['calidad']['caras_step']==134

def test_no_sobrescribe_el_original_si_es_alias_de_una_salida(tmp_path):
    step=tmp_path/'pieza.step';source=step.with_suffix('.r16_nucleo.json');source.write_bytes(b'original')
    with pytest.raises(route.RutasIncompatibles):route.comprobar_rutas(source,step)
    assert source.read_bytes()==b'original'

def test_familia_nueva_no_absorbe_organicas_o_conversiones_ya_compactas(tmp_path):
    source=tmp_path/'entrada.stl';source.write_bytes(b'source');p=payload(source)
    assert route.elegible(p)
    p['resultado']['calidad']['tipos_caras']['GeomAbs_SurfaceOfExtrusion']=0
    assert not route.elegible(p)
    p=payload(source,36)
    assert not route.elegible(p)
    p=payload(source);p['preprocesamiento']['reparado']=True
    assert not route.elegible(p)
