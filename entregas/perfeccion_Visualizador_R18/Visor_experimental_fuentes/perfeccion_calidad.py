"""Mejorar después del resultado R11 completo, conservándolo ante rechazo.

El núcleo nuevo vive en otro proceso y directorio. No sustituye los módulos
del motor R11 cargado. Sólo publica tras validar original, material y tres
mallados, y revalidar con el evaluador R11 y sus límites originales.
"""
from pathlib import Path
import contextlib,hashlib,json,os,shutil,subprocess,sys,tempfile,time

NUCLEO=Path(__file__).resolve().parent/'motor_calidad'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class EntradaCambiada(ValueError):pass


def ejecutar_subproceso(script,args,timeout,log):
    import psutil
    from control_recursos import comunicar_vigilado
    def stop(proc):
        try:
            parent=psutil.Process(proc.pid)
            for p in reversed(parent.children(recursive=True)):
                try:p.kill()
                except psutil.NoSuchProcess:pass
            parent.kill()
        except psutil.NoSuchProcess:pass
    env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1',
         'PYTHONDONTWRITEBYTECODE':'1','PYTHONIOENCODING':'utf-8','VISOR_PERFIL':'precision'}
    # Ningún diagnóstico de desarrollo modifica una conversión del programa.
    for key in tuple(env):
        if key.startswith('PILOTO_'):env.pop(key)
    with subprocess.Popen([sys.executable,str(script),*map(str,args)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                          text=True,encoding='utf-8',errors='replace',env=env) as proc:
        try:out,_,peak=comunicar_vigilado(proc,timeout,stop,memoria_bytes=3*1024**3)
        except Exception as exc:
            if getattr(exc,'stdout',''):print(exc.stdout,file=log,flush=True)
            if getattr(exc,'stderr',''):print(exc.stderr,file=log,flush=True)
            raise
    if out:print(out,file=log,flush=True)
    if proc.returncode:
        reason=''
        try:reason=json.loads(Path(args[-1]).read_text(encoding='utf-8')).get('error','')
        except (OSError,ValueError,TypeError,AttributeError):pass
        if not reason:reason=out.strip().splitlines()[-1] if out.strip() else 'sin informe legible'
        raise ValueError('La mejora aislada fue rechazada: '+reason)
    return peak


def entrada_preparada(source,destination,preprocessing):
    expected=preprocessing.get('reparado_sha256')
    if preprocessing.get('original_sha256')!=sha(source) or not expected:
        raise ValueError('La reparación no está vinculada al STL original')
    choices=[destination.with_suffix('.reparado.stl'),destination.with_suffix('.saneado.stl')]
    found=[p for p in choices if p.is_file() and sha(p)==expected]
    if len(found)!=1:raise ValueError('No se encuentra una única entrada reparada certificada')
    return found[0]


def mejorar(source,destination,payload,validar,log,tiempo_base_s=0.):
    from preprocesador_stl import cargar_exacto
    from prueba_cad import desde_trabajador
    from avance_conversion import avance
    result=payload['resultado'];quality=result.get('calidad',{})
    if result.get('reconstruccion_medida',{}).get('aplicado') is True:return None
    if int(quality.get('caras_step',0))<80:return None
    preprocessing=payload.get('preprocesamiento',{})
    # Despliegue conservador de esta primera mejora: contactos ya reparados,
    # entradas moderadas y tiempo suficiente para verificar el original.
    if (preprocessing.get('reparado') is not True or
        preprocessing.get('ruta_seleccionada')!='contactos_locales_exactos_verificados'):return None
    original_hash,base_hash=sha(source),sha(destination);preprocessing=payload.get('preprocesamiento',{})
    if preprocessing.get('original_sha256') not in (None,original_hash):raise EntradaCambiada('La entrada original cambió después de la conversión R11')
    original=cargar_exacto(source)
    if len(original.faces)>6000:return None
    source_prepared=entrada_preparada(source,destination,preprocessing) if preprocessing.get('reparado') else source
    prepared_hash=sha(source_prepared)
    def immutable():
        if sha(source)!=original_hash or sha(source_prepared)!=prepared_hash:raise EntradaCambiada('Una entrada cambió durante la mejora')
        if sha(destination)!=base_hash:raise EntradaCambiada('El STEP R11 cambió durante la mejora')
    with tempfile.TemporaryDirectory(prefix='visor_mejora_verificada_',dir=destination.parent) as directory:
        directory=Path(directory);active=source_prepared;normalization=None
        if preprocessing.get('reparado'):
            active=directory/'entrada_calidad.stl';normalization_path=directory/'normalizacion.json'
            avance(78,'Preparando una copia verificada para mejorar superficies')
            ejecutar_subproceso(NUCLEO/'preparar_calidad.py',[source,source_prepared,active,normalization_path],120,log)
            normalization=json.loads(normalization_path.read_text())
            if (normalization.get('ok') is not True or normalization.get('original_sha256')!=original_hash or
                normalization.get('entrada_reparada_sha256')!=prepared_hash or normalization.get('salida_sha256')!=sha(active)):
                raise ValueError('La limpieza no coincide con sus archivos')
        immutable();active_hash=sha(active)
        candidate=directory/'candidato.step';worker_path=directory/'trabajador.json'
        avance(78,'Mejorando superficies; se conserva el STEP anterior mientras se verifica')
        start=time.monotonic()
        peak=ejecutar_subproceso(NUCLEO/'reconstruccion_medida.py',[active,destination,candidate,worker_path],1000,log)
        record=json.loads(worker_path.read_text())
        if (record.get('ok') is not True or record.get('original_sha256')!=active_hash or
            record.get('base_sha256')!=base_hash or not candidate.is_file() or record.get('step_sha256')!=sha(candidate)):
            raise ValueError('El resultado no coincide con la reconstrucción verificada')
        immutable()
        original_path=directory/'original.json'
        avance(78,'Comprobando el STL original, el material y los tres mallados finos')
        peak=max(peak,ejecutar_subproceso(NUCLEO/'verificar_original_calidad.py',[source,active,candidate,worker_path,original_path],300,log))
        original_report=json.loads(original_path.read_text())
        if (original_report.get('ok') is not True or original_report.get('revision')!='R12_ORIGINAL_CGAL3_MATERIAL_20261030' or
            original_report.get('original_sha256')!=original_hash or original_report.get('preparado_sha256')!=active_hash or
            original_report.get('step_sha256')!=sha(candidate) or original_report.get('trabajador_sha256')!=sha(worker_path)):
            raise ValueError('La validación original no coincide con los archivos')
        # Evaluación final por el núcleo R11 que produjo la conversión inicial.
        final_quality=validar(source,candidate,original,control_avanzado=True,prueba_cad=desde_trabajador(record,candidate))
        if final_quality['caras_step']>.75*quality['caras_step']:raise ValueError('No se alcanza la reducción mínima de caras')
        immutable()
        if sha(active)!=active_hash or sha(candidate)!=record['step_sha256']:raise EntradaCambiada('El candidato cambió después de verificarse')
        proof=dict(aplicado=True,metodo='superficies_compartidas_verificadas',original_sha256=original_hash,
                   entrada_reparada_sha256=prepared_hash,entrada_calidad_sha256=active_hash,step_anterior_sha256=base_hash,
                   step_sha256=record['step_sha256'],caras_antes=quality['caras_step'],caras_despues=final_quality['caras_step'],
                   segundos=time.monotonic()-start,ram_pico_mb=peak,normalizacion=normalization,
                   cilindros_respaldados=record['cilindros_respaldados'],topologia_material=record['topologia_material'],
                   mallado_original=original_report['mallado_original'],material_original=original_report['material_original'],
                   limites_aceptacion_modificados=False)
        for origin,suffix in [(worker_path,'.calidad_nucleo.json'),(original_path,'.calidad_original.json')]:
            shutil.copyfile(origin,destination.with_suffix(suffix))
        if normalization is not None:
            prepared_saved=destination.with_suffix('.calidad_preparado.stl')
            shutil.copyfile(active,prepared_saved)
            if sha(prepared_saved)!=active_hash:raise ValueError('La copia de auditoría no coincide con la entrada de calidad')
            proof['archivo_preparado_calidad']=prepared_saved.name
        candidate.replace(destination)
        return final_quality,proof


def ejecutar(legacy,output_type,validar):
    if len(sys.argv)!=3:return legacy()
    from reunion_resultado_aislada import elegible as elegible_reunion,intentar as reunir
    from respaldo_conversion import guardar
    source,destination=map(Path,sys.argv[1:]);output=output_type(sys.stdout);start=time.monotonic()
    with contextlib.redirect_stdout(output):code=legacy()
    baseline_seconds=time.monotonic()-start
    lines=output.getvalue().splitlines()
    try:payload=json.loads(lines[-1])
    except (ValueError,IndexError):raise RuntimeError('El motor R11 no emitió un resultado verificable')
    if code==0 and payload.get('ok') and os.environ.get('VISOR_MEJORA_SUPERFICIES','1')=='1':
        result=payload['resultado'];q=result.get('calidad',{});prep=payload.get('preprocesamiento',{})
        eligible=(result.get('reconstruccion_medida',{}).get('aplicado') is not True and
                  int(q.get('caras_step',0))>=80 and prep.get('reparado') is True and
                  prep.get('ruta_seleccionada')=='contactos_locales_exactos_verificados')
        if eligible:
            from politica_conversion import presupuesto_conversion
            eligible=presupuesto_conversion(source.read_bytes())['triangulos']<=6000
        if eligible or elegible_reunion(payload):
            try:guardar(source,destination,payload)
            except Exception as exc:
                payload['mejora_superficies']=dict(aplicado=False,estado='conservada_conversion_validada',motivo='No se inicia la mejora sin respaldo íntegro: '+str(exc),conservado_resultado_R11=True)
                print(json.dumps(payload,ensure_ascii=True));return code
            if eligible:
                try:
                    with destination.with_suffix('.motor.log').open('a',encoding='utf-8',buffering=1) as log:
                        improved=mejorar(source,destination,payload,validar,log,baseline_seconds)
                    if improved is not None:
                        quality,proof=improved;result['calidad']=quality;result['calidad_original']=quality
                        result['mejora_superficies']=proof;result['estrategia']='superficies_compartidas_verificadas'
                        result['modo']='superficies';result['motor']='Superficies verificadas con conservación del resultado R11'
                except EntradaCambiada as exc:payload.update(ok=False,error=str(exc));code=2
                except Exception as exc:payload['mejora_superficies']=dict(aplicado=False,estado='propuesta_rechazada',motivo=str(exc),conservado_resultado_R11=True)
            if code==0 and elegible_reunion(payload):
                try:
                    with destination.with_suffix('.motor.log').open('a',encoding='utf-8',buffering=1) as log:
                        changed=reunir(source,destination,payload,validar,log)
                    if changed is not None:
                        quality,proof=changed;result['calidad']=quality;result['calidad_original']=quality
                        result['reunion_superficies']=proof;result['estrategia']='reunion_campos_verificada'
                        result['motor']='Reunión verificada de superficies medidas'
                except EntradaCambiada as exc:payload.update(ok=False,error=str(exc));code=2
                except Exception as exc:result['reunion_superficies']=dict(aplicado=False,motivo=str(exc),conservado_resultado_R11=True)
        else:
            payload['mejora_superficies']=dict(aplicado=False,estado='conservada_reconstruccion_anterior',motivo='Se conserva el resultado analítico, compacto o de una familia ya validada.',conservado_resultado_R11=True)
    print(json.dumps(payload,ensure_ascii=True));return code
