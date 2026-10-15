"""Preparar el entorno local y abrir la interfaz HTML."""
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import urllib.request
import venv
import webbrowser

root=Path(__file__).resolve().parent
env=root/'.venv'
python=env/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
if not python.exists():
    venv.EnvBuilder(with_pip=True).create(env)
subprocess.run([str(python),'-m','pip','install','--disable-pip-version-check','-r',str(root/'requirements.txt')],check=True)
def open_when_ready():
    for _ in range(120):
        try:
            with urllib.request.urlopen('http://127.0.0.1:8000/',timeout=1) as response:
                if response.status==200:
                    webbrowser.open('http://127.0.0.1:8000/')
                    return
        except OSError:
            time.sleep(.5)
threading.Thread(target=open_when_ready,daemon=True).start()
raise SystemExit(subprocess.call([str(python),'-m','uvicorn','app:app','--host','127.0.0.1','--port','8000'],cwd=root))
