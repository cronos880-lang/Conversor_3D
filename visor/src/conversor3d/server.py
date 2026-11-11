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


def serve(port=8783, open_browser=True):
    """Inicia el adaptador de imports en un proceso propio, sin mezclar núcleos."""
    if not 1024 <= port <= 65535:
        raise ValueError('El puerto debe estar entre 1024 y 65535')
    with tempfile.TemporaryDirectory(prefix='visor server ') as folder:
        path = Path(folder) / 'server.json'
        path.write_text(json.dumps({'action': 'serve', 'port': port, 'open_browser': open_browser}), encoding='utf-8')
        from .processes import stop_tree
        process = subprocess.Popen([sys.executable, '-m', 'conversor3d.legacy_worker', str(path)],
                                   cwd=REPO, env=native_env(), start_new_session=True)
        try:
            code = process.wait()
        except BaseException:
            stop_tree(process)
            raise
        if code:
            raise RuntimeError('El servidor terminó con un error; consulta el registro de esta ventana')


def serve_in_legacy(port, open_browser):
    """Se llama únicamente dentro del trabajador con R19 importado explícitamente."""
    import servidor
    import uvicorn
    servidor.subprocess = PipelineCommands()
    # El respaldo histórico no sustituye el certificado final del pipeline nuevo.
    servidor._recuperar_salida = lambda *args, **kwargs: None
    data = Path(os.environ.get('CONVERSOR3D_DATA_DIR', str(REPO / 'visor/data')))
    data.mkdir(parents=True, exist_ok=True)
    servidor.LOG_DIR = data
    if open_browser:
        def open_when_ready():
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            for _ in range(300):
                try:
                    with opener.open(f'http://127.0.0.1:{port}/version', timeout=.5) as response:
                        if response.status == 200:
                            webbrowser.open(f'http://127.0.0.1:{port}')
                            return
                except OSError:
                    time.sleep(.2)
        threading.Thread(target=open_when_ready, daemon=True).start()
    uvicorn.run(servidor.app, host='127.0.0.1', port=port, log_level='warning')
