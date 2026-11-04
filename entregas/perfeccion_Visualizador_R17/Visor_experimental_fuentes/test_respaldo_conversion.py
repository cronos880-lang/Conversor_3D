from pathlib import Path
import copy,json,pytest
import respaldo_conversion as r


def job(tmp):
 source=tmp/'entrada.stl';source.write_bytes(b'original inmutable');step=tmp/'salida.step';step.write_bytes(b'STEP aprobado por el motor')
 payload=dict(ok=True,preprocesamiento=dict(original_sha256=r.sha(source)),resultado=dict(calidad=dict(integridad_cad=dict(brep_valido=True,brep_exacto=True,solidos=1),autointerferencias_occ=False,sin_objetos_sueltos_en_step=True,inspeccion_densa=dict(aceptado=True),perfil_validacion=dict(id='precision'))))
 return source,step,payload


def test_recupera_el_step_anterior_ante_fase_opcional_incompleta(tmp_path):
 source,step,payload=job(tmp_path);body=step.read_bytes();r.guardar(source,step,payload);step.write_bytes(b'propuesta sin aprobar')
 recovered=r.recuperar(source,step,perfil='precision',motivo='tiempo de mejora agotado')
 assert recovered['ok'] and recovered['recuperacion_respaldo']['aplicado'] and step.read_bytes()==body
 assert recovered['mejora_superficies']['aplicado'] is False


def test_cancelacion_prevalece_y_no_publica_respaldo(tmp_path):
 source,step,payload=job(tmp_path);r.guardar(source,step,payload);step.write_bytes(b'propuesta incompleta')
 assert r.recuperar(source,step,perfil='precision',motivo='cancelado',cancelado=True) is None
 assert step.read_bytes()==b'propuesta incompleta'


@pytest.mark.parametrize('change',['source','step','profile','payload','partial'])
def test_respaldo_no_se_acepta_si_falla_su_integridad(tmp_path,change):
 source,step,payload=job(tmp_path);r.guardar(source,step,payload);saved,report=r.rutas(step);step.write_bytes(b'incompleto')
 if change=='source':source.write_bytes(b'otro STL')
 if change=='step':saved.write_bytes(b'STEP distinto')
 if change=='partial':report.write_bytes(b'{')
 if change=='payload':
  data=json.loads(report.read_text());data['payload']['resultado']['calidad']['integridad_cad']['brep_valido']=False;report.write_text(json.dumps(data))
 assert r.recuperar(source,step,perfil='impresion' if change=='profile' else 'precision',motivo='limite') is None
 assert step.read_bytes()==b'incompleto'


def test_no_guarda_como_base_un_resultado_sin_validar(tmp_path):
 source,step,payload=job(tmp_path);payload['resultado']['calidad']['inspeccion_densa']['aceptado']=False
 with pytest.raises(ValueError,match='aprobada'):r.guardar(source,step,payload)
 assert not any(p.exists() for p in r.rutas(step))
