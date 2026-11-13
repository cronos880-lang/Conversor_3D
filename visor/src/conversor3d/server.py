"""Conservar la interfaz existente y conectar ambas rutas al pipeline de desarrollo."""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import webbrowser
from .legacy import FROZEN, REPO, native_env
from .settings import Settings
from ._version import APPLICATION_LABEL, __version__


VIEWER = Path(__file__).parent / 'resources/viewer'


def viewer_html():
    """Interfaz de desarrollo propia; las fuentes R19 permanecen congeladas."""
    html = (VIEWER / 'viewer.html').read_text(encoding='utf-8')
    return html.replace('__APPLICATION_LABEL__', APPLICATION_LABEL)


class PipelineCommands:
    """Adaptador local al módulo servidor; no altera subprocess globalmente."""
    def translate(self, command, options):
        if (isinstance(command, (list, tuple)) and len(command) == 4
                and Path(command[1]).resolve() == (FROZEN / 'motor_r19.py').resolve()):
            command = [command[0], '-m', 'conversor3d', 'convert', command[2], command[3]]
            options = dict(options)
            options['env'] = {**native_env(), **options.get('env', {}),
                              'PYTHONPATH': str(Path(__file__).resolve().parents[1])}
        return command, options

    def Popen(self, command, *args, **kwargs):
        command, kwargs = self.translate(command, kwargs)
        return subprocess.Popen(command, *args, **kwargs)

    def run(self, command, *args, **kwargs):
        command, kwargs = self.translate(command, kwargs)
        return subprocess.run(command, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(subprocess, name)


def serve(port=None, open_browser=True):
    """Inicia el adaptador de imports en un proceso propio, sin mezclar núcleos."""
    configuration = Settings.read()
    port = configuration.port if port is None else port
    if not 1024 <= port <= 65535:
        raise ValueError('El puerto debe estar entre 1024 y 65535')
    with tempfile.TemporaryDirectory(prefix='visor server ') as folder:
        path = Path(folder) / 'server.json'
        path.write_text(json.dumps({'action': 'serve', 'port': port, 'open_browser': open_browser}), encoding='utf-8')
        from .processes import stop_tree
        environment = {**native_env(), 'CONVERSOR3D_PORT': str(port)}
        process = subprocess.Popen([sys.executable, '-m', 'conversor3d.legacy_worker', str(path)],
                                   cwd=REPO, env=environment, start_new_session=True)
        try:
            code = process.wait()
        except BaseException:
            stop_tree(process)
            raise
        if code:
            raise RuntimeError('El servidor terminó con un error; consulta el registro de esta ventana')


def serve_in_legacy(port, open_browser):
    """Se llama únicamente dentro del trabajador con R19 importado explícitamente."""
    from .dependencies import runtime_identity
    runtime_identity()
    import servidor
    import uvicorn
    configuration = Settings.read()
    identity = configuration.identity(port)
    servidor.subprocess = PipelineCommands()
    servidor.identidad = lambda root: identity.copy()
    servidor.VERSION, servidor.COMPILACION = APPLICATION_LABEL, __version__
    from fastapi.responses import HTMLResponse, Response
    async def development_index():
        return HTMLResponse(viewer_html(), headers={'Cache-Control': 'no-store'})
    async def presentation_script():
        return Response((VIEWER / 'presentation.js').read_text(encoding='utf-8'),
                        media_type='text/javascript', headers={'Cache-Control': 'no-store'})
    servidor.app.router.routes[:] = [r for r in servidor.app.router.routes if getattr(r, 'path', None) != '/']
    servidor.app.add_api_route('/', development_index, methods=['GET'])
    servidor.app.add_api_route('/viewer/presentation.js', presentation_script, methods=['GET'])
    servidor.app.title, servidor.app.version = APPLICATION_LABEL, __version__
    from starlette.middleware.cors import CORSMiddleware
    from .security import LocalAccessMiddleware
    allowed_origins = [f'http://127.0.0.1:{port}', f'http://localhost:{port}']
    servidor.app.add_middleware(CORSMiddleware, allow_origins=allowed_origins,
                                allow_methods=['GET', 'POST'], allow_headers=['Content-Type'])
    servidor.app.add_middleware(LocalAccessMiddleware, port=port)

    # El respaldo histórico no sustituye el certificado final del pipeline nuevo.
    servidor._recuperar_salida = lambda *args, **kwargs: None
    data = configuration.data_dir
    data.mkdir(parents=True, exist_ok=True)
    servidor.LOG_DIR = data
    original_diagnostic = servidor._diagnostico
    def owned_diagnostic(job_id, metadata, *args):
        metadata['conversor3d_owned'] = True
        metadata['conversor3d_completed_at'] = time.time()
        return original_diagnostic(job_id, metadata, *args)
    servidor._diagnostico = owned_diagnostic
    if configuration.retention_days:
        import logging
        from .retention import cleanup_records
        stopped = threading.Event()
        servidor.app.add_event_handler('shutdown', stopped.set)
        def clean_finished():
            while not stopped.is_set():
                with servidor.JOBS_LOCK:
                    active = [key for key, job in servidor.JOBS.items()
                              if job['status'] in ('ejecutando', 'cancelando')]
                try:
                    cleaned = cleanup_records(data, configuration.retention_days, active)
                    with servidor.JOBS_LOCK:
                        for job_id in cleaned['removed_jobs']:
                            servidor.JOBS.pop(job_id, None)
                    for skipped in cleaned['skipped']:
                        logging.getLogger(__name__).warning('Registro conservado: %s', skipped)
                except OSError as error:
                    logging.getLogger(__name__).warning('No se pudo limpiar registros: %s', error)
                stopped.wait(60)
        threading.Thread(target=clean_finished, daemon=True).start()

    if open_browser:
        def open_when_ready():
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            for _ in range(300):
                try:
                    with opener.open(f'http://127.0.0.1:{port}/version', timeout=.5) as response:
                        if response.status == 200 and json.load(response) == identity:
                            webbrowser.open(f'http://127.0.0.1:{port}')
                            return
                except OSError:
                    time.sleep(.2)
        threading.Thread(target=open_when_ready, daemon=True).start()
    uvicorn.run(servidor.app, host='127.0.0.1', port=port, log_level='warning')
