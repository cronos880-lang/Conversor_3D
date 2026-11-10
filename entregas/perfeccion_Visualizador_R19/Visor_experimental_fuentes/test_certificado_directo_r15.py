import copy,json
from pathlib import Path
import cadquery as cq,numpy as np,pytest,trimesh
from certificado_calidad_r15 import identidad,verificar
from conversion_directa_r15 import comprobar_rutas,RutasIncompatibles

@pytest.fixture
def certified(tmp_path):
 # Schema binding unit test; full native geometry is exercised by the exported
 # shapes, material tests and real end-to-end conversion regression separately.
 source=tmp_path/'source.stl';step=tmp_path/'model.step';source.write_bytes(b'original identity');step.write_bytes(b'worker STEP identity')
 q=dict(integridad_cad=dict(brep_valido=True,brep_exacto=True,solidos=1),autointerferencias_occ=False,sin_objetos_sueltos_en_step=True,
        inspeccion_densa=dict(aceptado=True),limites_validacion=dict(desviacion_max_observada_mm=.06,p95_superficie_max_mm=.02))
 root=Path(__file__).parent;cert=identidad(source,step,'request',root);q['perfil_validacion']=cert['perfil']
 record=dict(ok=True,certificado=cert,calidad=q,mallado_fino=dict(resoluciones=[dict(deflexion_mm=x,cerrado=True,orientado=True,intersecciones_cgal=0,euler=2,superficie=dict(max_mm=.001,p95_mm=.001)) for x in [.00025,.0005,.001]]),material_original=dict(puntos=3000,discrepancias=0,banda_excluida_mm=.002),topologia_material=dict(euler_brep=2,euler_malla=2,shells=1))
 return record,source,step,root

@pytest.mark.parametrize('change',['source','step','nonce','profile','code','dependency','fine_missing','fine_open','fine_crossing','fine_error','material','topology','dense','exact'])
def test_incomplete_or_stale_validation_cannot_be_reused(certified,monkeypatch,change):
 r,source,step,root=certified;nonce='request'
 assert verificar(r,source,step,nonce,root)==r['calidad']
 if change=='source':source.write_bytes(b'different original')
 if change=='step':step.write_bytes(b'different STEP')
 if change=='nonce':nonce='another request'
 if change=='profile':monkeypatch.setenv('VISOR_PERFIL','impresion')
 if change=='code':r['certificado']['motor_sha256']='0'*64
 if change=='dependency':r['certificado']['dependencias']['cadquery']='different'
 if change=='fine_missing':r['mallado_fino']['resoluciones'].pop()
 if change=='fine_open':r['mallado_fino']['resoluciones'][0]['cerrado']=False
 if change=='fine_crossing':r['mallado_fino']['resoluciones'][0]['intersecciones_cgal']=1
 if change=='fine_error':r['mallado_fino']['resoluciones'][0]['superficie']['max_mm']=.07
 if change=='material':r['material_original']['discrepancias']=1
 if change=='topology':r['topologia_material']={}
 if change=='dense':r['calidad']['inspeccion_densa']['aceptado']=False
 if change=='exact':r['calidad']['integridad_cad']['brep_exacto']=False
 with pytest.raises(ValueError):verificar(r,source,step,nonce,root)

@pytest.mark.parametrize('suffix',['','.motor.log','.entrada.json','.r15_nucleo.json','.r15_propuesta.json'])
def test_all_outputs_protect_original_bytes(tmp_path,suffix):
 destination=tmp_path/'model.step';source=destination if not suffix else destination.with_suffix(suffix);source.write_bytes(b'original STL untouched')
 with pytest.raises(RutasIncompatibles):comprobar_rutas(source,destination)
 assert source.read_bytes()==b'original STL untouched'

def test_hardlinked_source_cannot_be_overwritten(tmp_path):
 source=tmp_path/'source.stl';source.write_bytes(b'original');destination=tmp_path/'model.step';destination.hardlink_to(source)
 with pytest.raises(RutasIncompatibles):comprobar_rutas(source,destination)
 assert source.read_bytes()==b'original'
