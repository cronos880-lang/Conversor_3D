"""Conversión local STL a STEP; consolida caras planas sin alterar el modelo."""
from pathlib import Path
import io
import tempfile
import trimesh
import cadquery as cq
from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, Response
import uvicorn
from analisis_superficies import analizar_superficies
from fastapi.responses import JSONResponse

ROOT = Path(__file__).resolve().parent
app = FastAPI(title='Visor STL STEP local')
MAX_BYTES = 30 * 1024 * 1024
MAX_FACES = 12000

@app.get('/')
def index():
    return FileResponse(ROOT / 'Visor_STL_STEP.html')

@app.post('/analizar')
async def analizar(archivo: UploadFile = File(...)):
    if not archivo.filename or not archivo.filename.lower().endswith('.stl'):
        raise HTTPException(400, 'Selecciona un STL.')
    data = await archivo.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, 'Archivo demasiado grande.')
    try:
        mesh = trimesh.load(io.BytesIO(data), file_type='stl', force='mesh', process=True)
        if not isinstance(mesh, trimesh.Trimesh) or len(mesh.faces) == 0:
            raise ValueError('Malla vacía')
        return JSONResponse(analizar_superficies(mesh))
    except Exception as exc:
        raise HTTPException(422, str(exc)) from exc


import asyncio
import datetime
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import time
import uuid
import threading
import shutil
import signal
from control_recursos import comunicar_vigilado, LimiteRecursos
from perfiles_precision import obtener_perfil
from politica_conversion import presupuesto_conversion

# Las conversiones OCC pueden consumir mucha memoria. Evitar ejecuciones
# simultáneas y conservar un informe de cualquier fallo o éxito.
CONVERSION_LOCK = asyncio.Semaphore(1)
LOG_DIR = ROOT / "Registros_Conversion"
LOG_DIR.mkdir(exist_ok=True)

def _diagnostico(id, meta, salida, errores, motor_log):
    meta['motor_stdout_ultimas_lineas'] = salida[-4000:]
    meta['version_programa'] = 'V4.0 R5 EXPERIMENTAL reparación local verificada'
    meta['python_version'] = sys.version.split()[0] + ' (' + platform.platform() + ')'
    try:
        import importlib.metadata as _dist
        meta['dependencias'] = {n: _dist.version(n) for n in ('cadquery','cadquery-ocp','trimesh','numpy','scipy','vtk','shapely')}
    except Exception: pass
    meta['motor_stderr_ultimas_lineas'] = errores[-4000:]
    (LOG_DIR / f"{id}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    (LOG_DIR / f"{id}.txt").write_text(
        "INFORME DEL CONVERSOR\n" + json.dumps(meta,ensure_ascii=False,indent=2) +
        "\n\n--- REGISTRO DEL MOTOR ---\n" + motor_log[-120000:] +
        "\n\n--- SALIDA Y ERRORES ---\n" + salida[-10000:] + "\n" + errores[-10000:],
        encoding="utf-8",errors="replace")

@app.get('/diagnostico/{id}')
def obtener_diagnostico(id: str):
    if not re.fullmatch(r'[0-9a-f]{12}', id):
        raise HTTPException(404, 'Registro no encontrado.')
    path = LOG_DIR / f'{id}.txt'
    if not path.is_file():
        raise HTTPException(404, 'Registro no encontrado.')
    return FileResponse(path, media_type='text/plain',filename=f'Diagnostico_{id}.txt')


def _guardar_preproceso(id, dst, src, meta):
    """Conservar evidencias antes de que desaparezca el temporal del trabajo."""
    report = dst.with_suffix('.entrada.json')
    rejected=dst.with_suffix('.rechazos.jsonl')
    if rejected.is_file():
        shutil.copyfile(rejected,LOG_DIR/f'{id}.rechazos.jsonl')
        meta['criterios_rechazados']=[]
        for line in rejected.read_text(encoding='utf-8',errors='replace').splitlines():
            try:meta['criterios_rechazados'].append(json.loads(line))
            except ValueError:pass  # Un proceso interrumpido puede dejar la última línea incompleta.
    if report.is_file():
        shutil.copyfile(report, LOG_DIR / f'{id}.entrada.json')
        try:
            meta['preprocesamiento'] = json.loads(report.read_text(encoding='utf-8'))
        except ValueError:
            meta['preprocesamiento'] = {'error': 'Informe de entrada incompleto; proceso interrumpido.'}
        if meta['preprocesamiento'].get('error'):
            shutil.copyfile(src,LOG_DIR/f'{id}.original.stl')
            meta['archivos_reparacion']={'informe':f'/reparacion/{id}/informe',
                                        'original':f'/reparacion/{id}/original'}
        repaired = dst.with_suffix('.reparado.stl')
        if repaired.is_file():
            shutil.copyfile(repaired, LOG_DIR / f'{id}.reparado.stl')
            shutil.copyfile(src, LOG_DIR / f'{id}.original.stl')
            meta['archivos_reparacion'] = {
                kind: f'/reparacion/{id}/{kind}' for kind in ('informe', 'original', 'reparado')}


@app.get('/reparacion/{id}/{tipo}')
def obtener_reparacion(id: str, tipo: str):
    suffixes = {'informe': '.entrada.json', 'original': '.original.stl', 'reparado': '.reparado.stl'}
    if not re.fullmatch(r'[0-9a-f]{12}', id) or tipo not in suffixes:
        raise HTTPException(404, 'Evidencia no encontrada.')
    path = LOG_DIR / (id+suffixes[tipo])
    if not path.is_file():
        raise HTTPException(404, 'Evidencia no encontrada.')
    return FileResponse(path, filename=path.name)

@app.post('/convertir')
async def convertir(archivo: UploadFile = File(...), perfil: str = Form('precision')):
    try:obtener_perfil(perfil)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
    if not archivo.filename or not archivo.filename.lower().endswith('.stl'):
        raise HTTPException(400, 'Selecciona un archivo STL.')
    data = await archivo.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, 'STL demasiado grande (máximo 30 MB).')
    if not data:
        raise HTTPException(400, 'El archivo está vacío.')
    id = uuid.uuid4().hex[:12]
    meta = {
        'id': id,
        'fecha_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'archivo': archivo.filename,
        'bytes_stl': len(data),
        'sha256_stl': hashlib.sha256(data).hexdigest(),
        'python': sys.version.split()[0],
        'dependencias': {p: __import__('importlib.metadata',fromlist=['version']).version(p) if __import__('importlib.util',fromlist=['find_spec']).find_spec(p.replace('-','_')) else 'no disponible' for p in ('numpy','scipy','trimesh','cadquery','vtk','fastapi','shapely')},
        'plataforma': platform.platform(),
        'resultado': 'iniciado',
    }
    try:
        async with CONVERSION_LOCK:
            with tempfile.TemporaryDirectory(prefix='visor_stl_') as td:
                src, dst = Path(td)/'entrada.stl', Path(td)/'salida.step'
                src.write_bytes(data)
                args=[sys.executable, str(ROOT/'motor_v2.py'), str(src), str(dst)]
                t0=time.monotonic()
                # Una pieza densa no debe ser rechazada por el mismo límite que
                # un STL pequeño; continúa siendo un proceso acotado.
                policy=presupuesto_conversion(data)
                timeout = policy['inicial_s']
                meta.update(perfil=perfil,presupuesto=policy)
                status='fallo'
                try:
                    with subprocess.Popen(args,cwd=str(ROOT),stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,text=True,encoding='utf-8',errors='replace',
                        start_new_session=os.name != 'nt',
                        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0,
                        env={**os.environ,'PYTHONUNBUFFERED':'1','OPENBLAS_NUM_THREADS':'1',
                             'OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','VISOR_PERFIL':perfil}) as child:
                        salida, errores, pico = await asyncio.to_thread(
                            comunicar_vigilado, child, timeout, _detener_arbol, politica=policy)
                        proc = subprocess.CompletedProcess(args, child.returncode, salida, errores)
                        meta['ram_pico_mb'] = pico
                        meta['codigo_motor'] = proc.returncode
                except LimiteRecursos as e:
                    salida, errores = e.stdout, e.stderr
                    meta.update(resultado='limite_recursos', error=str(e), ram_pico_mb=e.pico_mb,tipo_error=e.codigo)
                    proc = None
                finally:
                    _guardar_preproceso(id, dst, src, meta)
                meta['segundos']=round(time.monotonic()-t0,3)
                motor_log_path=dst.with_suffix('.motor.log')
                motor_log=motor_log_path.read_text(encoding='utf-8',errors='replace') if motor_log_path.exists() else ''
                if proc is None:
                    meta.setdefault('error', f'La conversión superó {timeout} segundos.')
                    _diagnostico(id,meta,salida,errores,motor_log)
                    raise HTTPException(422,f"{meta['error']} Diagnóstico: /diagnostico/{id}")
                try:
                    report=json.loads(salida.strip().splitlines()[-1])
                except (ValueError,IndexError):
                    report={'ok':False,'error':'El proceso CAD finalizó sin un informe de resultado legible.'}
                if proc.returncode!=0 or not report.get('ok') or not dst.is_file():
                    meta['resultado']='fallido'
                    meta['tipo_error']=report.get('tipo_error','reconstruccion_cad_rechazada')
                    meta['error']=str(report.get('error','No se produjo un STEP válido.'))
                    _diagnostico(id,meta,salida,errores,motor_log)
                    raise HTTPException(422,f"{meta['error']} Diagnóstico: /diagnostico/{id}")
                result=report['resultado']
                quality=result['calidad']
                body=dst.read_bytes()
                meta['resultado']='exito'
                meta['calidad']=quality
                meta['estrategia']=result.get('estrategia',result.get('modo'))
                meta['bytes_step']=len(body)
                if quality['integridad_cad']['tolerancia_max_mm'] > .02:
                    meta['advertencia']='Tolerancia CAD de ciertas aristas mayor de 0,02 unidades; comprobar edición en Onshape.'
                _diagnostico(id,meta,salida,errores,motor_log)
                return Response(content=body,media_type='application/step',headers={
                    'X-STEP-Achieved-Profile':quality.get('precision_alcanzada',perfil),
                    'X-STEP-Max-Deviation':str(quality.get('desviacion_max_verificada_mm','')),
                    'X-STEP-Faces':str(quality['caras_step']),
                    'X-STL-Triangles':str(result['caras_stl']),
                    'X-STEP-Method':('superficies' if result.get('modo') == 'extrusiones_y_vaciados' else str(result.get('modo','superficies'))),
                    'X-STEP-Bytes':str(len(body)),
                    'X-STEP-Reduction':f"{(1-quality['caras_step']/result['caras_stl'])*100:.1f}",
                    'X-Volume-Error':str(quality['volumen_error_pct']),
                    'X-Diagnostic-ID':id,
                    'Access-Control-Expose-Headers':'X-STEP-Faces, X-STL-Triangles, X-STEP-Method, X-STEP-Bytes, X-STEP-Reduction, X-Volume-Error, X-Diagnostic-ID, X-STEP-Achieved-Profile, X-STEP-Max-Deviation',
                    'Cache-Control':'no-store',
                })
    except HTTPException:
        raise
    except Exception as e:
        meta['resultado']='fallo_servidor';meta['error']=repr(e)
        _diagnostico(id,meta,'','',str(e))
        raise HTTPException(500,f'Fallo del servidor. Diagnóstico: /diagnostico/{id}')

# API no bloqueante. Una petición HTTP nunca espera a que termine OpenCascade:
# el navegador obtiene un identificador, consulta el estado y descarga el STEP.
# La operación CAD sigue siendo local (subproceso aislado) y el visor mantiene
# sus cuatro botones, sin conexiones a servicios externos.
JOBS = {}
JOBS_LOCK = threading.Lock()


def _detener_arbol(proc):
    """Detiene el subproceso CAD y todos sus hijos, también Easymeshfit.

    No basta con cambiar el estado HTTP: OpenCascade continuaría consumiendo CPU
    y bloquearía los siguientes STL. Todo motor se lanza en su grupo de procesos.
    """
    if proc is None or proc.poll() is not None:
        return
    try:
        if os.name == 'nt':
            subprocess.run(['taskkill','/F','/T','/PID',str(proc.pid)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=8, check=False)
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except (OSError, subprocess.TimeoutExpired, ProcessLookupError):
        pass
    if proc.poll() is None:
        try:
            proc.kill()
        except OSError:
            pass


class ConversionCancelada(Exception):
    pass


def _worker_conversion(job_id: str, raw: bytes, filename: str, perfil='precision'):
    with JOBS_LOCK:
        job = JOBS[job_id]
    now = time.monotonic()
    out = ''
    err = ''
    motor_log = ''
    metadata = {
        'id': job_id,
        'fecha_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'archivo': filename,
        'bytes_stl': len(raw),
        'sha256_stl': hashlib.sha256(raw).hexdigest(),
        'resultado': 'iniciado',
        'perfil':perfil,
    }
    try:
        with JOBS_LOCK:
            if job['cancel_requested']:
                raise ConversionCancelada('Conversión cancelada antes de arrancar.')
        with tempfile.TemporaryDirectory(prefix='visor_cad_job_') as td:
            src = Path(td)/'entrada.stl'
            dst = Path(td)/'salida.step'
            src.write_bytes(raw)
            progress_path = LOG_DIR / f'{job_id}.avance.jsonl'
            with JOBS_LOCK:
                job['log_path'] = str(dst.with_suffix('.motor.log'))
                job['progress_path'] = str(progress_path)
            # Limitar el tiempo del proceso NO mata el servidor ni el navegador.
            policy=presupuesto_conversion(raw)
            limit=policy['inicial_s']
            metadata['presupuesto']=policy
            with JOBS_LOCK:job['presupuesto']=policy.copy()
            def informar(update):
                with JOBS_LOCK:job['presupuesto'].update(update)
                metadata['presupuesto'].update(update)
            args = [sys.executable, str(ROOT/'motor_v2.py'), str(src), str(dst)]
            try:
                flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
                with subprocess.Popen(args, cwd=str(ROOT), stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace',
                    creationflags=flags, start_new_session=(os.name != 'nt'),
                    env={**os.environ, 'VISOR_AVANCE_PATH':str(progress_path),'VISOR_PERFIL':perfil,
                         'PYTHONUNBUFFERED':'1','PYTHONIOENCODING':'utf-8','OPENBLAS_NUM_THREADS':'1',
                         'OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1'}) as proc:
                    with JOBS_LOCK:
                        job['process'] = proc
                        cancelar_ya = job['cancel_requested']
                    if cancelar_ya:
                        _detener_arbol(proc)
                    try:
                        out, err, pico = comunicar_vigilado(proc, limit, _detener_arbol,
                                                          politica=policy,informar=informar)
                        metadata['ram_pico_mb'] = pico
                    except LimiteRecursos as ex:
                        out, err = ex.stdout, ex.stderr
                        metadata['ram_pico_mb'] = ex.pico_mb
                        metadata['tipo_error']=ex.codigo
                        raise
                    finally:
                        with JOBS_LOCK:
                            if job['process'] is proc:
                                job['process'] = None
                    with JOBS_LOCK:
                        if job['cancel_requested']:
                            raise ConversionCancelada('Conversión cancelada por el usuario.')
                    metadata['codigo_motor'] = proc.returncode
            finally:
                logfile = dst.with_suffix('.motor.log')
                if logfile.exists():
                    motor_log = logfile.read_text(encoding='utf-8',errors='replace')
                _guardar_preproceso(job_id, dst, src, metadata)
            try:
                report = json.loads(out.strip().splitlines()[-1])
            except (IndexError,ValueError):
                report = {'ok':False,'error':'El motor ha terminado sin un informe válido. Revisa el diagnóstico.'}
            if proc.returncode != 0 or not report.get('ok') or not dst.is_file():
                metadata['tipo_error']=report.get('tipo_error','reconstruccion_cad_rechazada')
                raise RuntimeError(str(report.get('error') or f'El motor terminó con código {proc.returncode}.'))
            result = report['resultado']
            quality = result['calidad']
            destination = LOG_DIR / f'{job_id}.step'
            with JOBS_LOCK:
                if job['cancel_requested']:
                    raise ConversionCancelada('Conversión cancelada por el usuario.')
            shutil.copyfile(dst,destination)
            metadata.update({'resultado':'exito','segundos':round(time.monotonic()-now,3),
                'calidad':quality,'estrategia':result.get('estrategia',result.get('modo')),
                'bytes_step':destination.stat().st_size})
            _diagnostico(job_id,metadata,out,err,motor_log)
            with JOBS_LOCK:
                if job['cancel_requested']:
                    destination.unlink(missing_ok=True)
                    raise ConversionCancelada('Conversión cancelada por el usuario.')
                job.update({'status':'terminado', 'caras':quality['caras_step'],
                    'triangulos':result['caras_stl'], 'modo':result.get('modo','superficies'),
                    'size':destination.stat().st_size, 'file':str(destination),
                    'calidad':quality})
    except Exception as exc:
        with JOBS_LOCK:
            cancelado = job['cancel_requested'] or isinstance(exc, ConversionCancelada)
        metadata.update({'resultado':'cancelado' if cancelado else ('limite_recursos' if isinstance(exc,LimiteRecursos) else 'fallido'), 'error':str(exc),
                         'segundos':round(time.monotonic()-now,3)})
        try:
            _diagnostico(job_id,metadata,out,err,motor_log)
        except OSError:
            pass
        with JOBS_LOCK:
            job.update(status='cancelado' if cancelado else 'error', error=str(exc),
                       tipo_error=metadata.get('tipo_error','reconstruccion_cad_rechazada'),
                       malla_reparada=bool(metadata.get('preprocesamiento',{}).get('reparado')),
                       archivos_reparacion=metadata.get('archivos_reparacion',{}))
    finally:
        # El directorio temporal se destruye antes de consultar el estado final.
        # Un trabajo terminado devuelve 100%; uno fallido conserva su último hito
        # en el informe escrito y no simula haber llegado al final.
        with JOBS_LOCK:
            job['log_path'] = None
            job['process'] = None
            job['completed'].set()
            # Conservar los hitos del trabajo, también si falla.


@app.post('/iniciar-conversion')
async def iniciar_conversion(archivo: UploadFile = File(...), perfil: str = Form('precision')):
    try:obtener_perfil(perfil)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
    if not archivo.filename or not archivo.filename.lower().endswith('.stl'):
        raise HTTPException(400,'Selecciona un STL.')
    raw = await archivo.read(MAX_BYTES + 1)
    if not raw:
        raise HTTPException(400,'Archivo STL vacío.')
    if len(raw) > MAX_BYTES:
        raise HTTPException(413,'El conversor admite STL de hasta 30 MB; el visor puede mostrar archivos mayores.')
    with JOBS_LOCK:
        if any(item['status'] in ('ejecutando','cancelando') for item in JOBS.values()):
            raise HTTPException(409,'Ya hay una conversión en marcha. Cancélala antes de cargar otra.')
        job_id=uuid.uuid4().hex[:12]
        JOBS[job_id]={'status':'ejecutando','inicio':time.monotonic(),
                      'log_path':None,'name':archivo.filename,'perfil':perfil,
                      'cancel_requested':False,'process':None,'completed':threading.Event()}
    try:
        threading.Thread(target=_worker_conversion,
                         args=(job_id,raw,archivo.filename,perfil),daemon=True).start()
    except Exception:
        with JOBS_LOCK:
            JOBS.pop(job_id,None)
        raise
    return {'id':job_id,'estado':'ejecutando'}


@app.post('/cancelar-conversion/{id}')
def cancelar_conversion(id: str):
    if not re.fullmatch(r'[0-9a-f]{12}', id):
        raise HTTPException(404, 'No se conoce esta conversión.')
    with JOBS_LOCK:
        job = JOBS.get(id)
        if job is None:
            raise HTTPException(404, 'No se conoce esta conversión.')
        if job['status'] not in ('ejecutando','cancelando'):
            return {'id':id,'estado':job['status']}
        job['cancel_requested'] = True
        job['status'] = 'cancelando'
        proc = job.get('process')
        finished = job['completed']
    # El subprocess puede estar en OpenCascade o esperando a otro proceso hijo.
    # Interrumpimos TODA la familia, no solo la petición del navegador.
    _detener_arbol(proc)
    finished.wait(timeout=8)
    with JOBS_LOCK:
        return {'id':id,'estado':job['status']}


@app.get('/estado-conversion/{id}')
def estado_conversion(id: str):
    if not re.fullmatch('[0-9a-f]{12}',id):
        raise HTTPException(404,'No se conoce esta conversión.')
    with JOBS_LOCK:
        if id not in JOBS:
            raise HTTPException(404,'No se conoce esta conversión.')
        job = JOBS[id].copy()
        if job.get('presupuesto'):job['presupuesto']=job['presupuesto'].copy()
    stage='Reconstruyendo geometría CAD'
    log_path=job.get('log_path')
    if job['status'] in ('ejecutando','cancelando') and log_path:
        try:
            rows=Path(log_path).read_text(encoding='utf-8',errors='replace').splitlines()
            interesting=('[Ruta rápida]','[Preparación]','[Detección]','[Perfiles CAD]',
                         '[Integración]','[Franjas]','[Recuperación]','[Calidad]','[Adaptativa]')
            matches=[row.strip() for row in rows[-150:] if row.strip().startswith(interesting)]
            if matches: stage=matches[-1][:180]
        except (OSError,PermissionError):
            pass
    # Solo hitos que el motor ha publicado al terminar una etapa.
    # Nunca incrementar porcentaje por el mero paso del tiempo.
    percent = 100 if job['status'] == 'terminado' else 0
    since_progress = round(time.monotonic()-job['inicio'], 1)
    progress_path = job.get('progress_path')
    if progress_path:
        try:
            data = Path(progress_path).read_text(encoding='utf-8',errors='replace').splitlines()
            latest = None
            for line in data[-100:]:
                try:
                    event=json.loads(line)
                    value=int(event['porcentaje'])
                    if not 0 <= value <= 99:
                        continue
                    if job['status'] != 'terminado':
                        percent=max(percent,value)
                    latest=event
                except (ValueError,KeyError,TypeError):
                    continue
            if latest is not None and job['status'] == 'ejecutando':
                stage=str(latest.get('fase') or stage)[:180]
                since_progress=max(0, round(time.time()-float(latest['instante']),1))
        except (OSError,PermissionError):
            pass
    return {'id':id,'estado':job['status'],
            'precision_alcanzada':job.get('calidad',{}).get('precision_alcanzada'),
            'desviacion_max_mm':job.get('calidad',{}).get('desviacion_max_verificada_mm'),
            'perfil':job.get('perfil','precision'),'presupuesto':job.get('presupuesto'),
            'porcentaje':percent,'sin_avances_segundos':since_progress,
            'segundos':round(time.monotonic()-job['inicio'],1),
            'fase':stage if job['status']=='ejecutando' else '',
            'error':job.get('error'),
            'tipo_error':job.get('tipo_error'),
            'malla_reparada':job.get('malla_reparada',False),
            'archivos_reparacion':job.get('archivos_reparacion',{}),
            'diagnostico':f'/diagnostico/{id}' if job['status']!='ejecutando' else None}


@app.get('/descargar-conversion/{id}')
def descargar_conversion(id: str):
    with JOBS_LOCK:
        job=JOBS.get(id)
        if not job or job.get('status')!='terminado':
            raise HTTPException(404,'El STEP no está disponible. Consulta el estado de la conversión.')
        path=Path(job['file'])
    if not path.is_file():
        raise HTTPException(404,'El resultado ya no está disponible.')
    return FileResponse(path,media_type='application/step',filename='modelo.step',headers={
        'X-STEP-Achieved-Profile':job.get('calidad',{}).get('precision_alcanzada',job.get('perfil','precision')),
        'X-STEP-Max-Deviation':str(job.get('calidad',{}).get('desviacion_max_verificada_mm','')),
        'X-STEP-Faces':str(job['caras']),
        'X-STL-Triangles':str(job['triangulos']),
        'X-STEP-Method':str(job['modo']),
        'X-STEP-Bytes':str(job['size']),
        'X-Diagnostic-ID':id,
        'Cache-Control':'no-store',
        'Access-Control-Expose-Headers':'X-STEP-Faces, X-STL-Triangles, X-STEP-Method, X-STEP-Bytes, X-Diagnostic-ID, X-STEP-Achieved-Profile, X-STEP-Max-Deviation'})


if __name__ == '__main__':
    uvicorn.run(app, host='127.0.0.1',port=8769,log_level='warning')
