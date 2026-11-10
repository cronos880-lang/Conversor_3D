"""Reutilizar un entorno CAD existente sin instalar ni modificar la R7."""
from pathlib import Path
import os,subprocess,sys

IMPORTS='import gpytoolbox_bindings_copyleft,CGAL,igl,cadquery,trimesh,scipy,numpy,shapely,vtk,fastapi,uvicorn,multipart,manifold3d,psutil,networkx'

def compatible(executable):
    if not Path(executable).is_file():return False
    code='import sys,struct;assert sys.version_info[:2]==(3,12) and struct.calcsize("P")==8;'+IMPORTS
    try:
        result=subprocess.run([str(executable),'-c',code],stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                              timeout=45,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
        return result.returncode==0
    except (OSError,subprocess.TimeoutExpired):return False

def candidatos(folder):
    root=Path(folder)
    choices=[root/'.venv/Scripts/python.exe',root/'Visor_experimental_fuentes/.venv/Scripts/python.exe',root/'Scripts/python.exe',root/'.venv/bin/python']
    for config in [root/'.entorno_python.txt',root/'Visor_experimental_fuentes/.entorno_python.txt']:
        if config.is_file():
            try:
                configured=Path(config.read_text(encoding='utf-8').strip())
                if configured.is_absolute():choices.append(configured)
            except OSError:pass
    return [p for p in dict.fromkeys(choices) if p.is_file()]


def seleccionar_carpeta():
    try:
        from tkinter import Tk,filedialog
        window=Tk();window.withdraw()
        try:return filedialog.askdirectory(title='Selecciona la carpeta de tu Visor R7 a R18 para reutilizar su entorno CAD')
        finally:window.destroy()
    except Exception:return ''

def resolver(root):
    root=Path(root);configuration=root/'.entorno_python.txt';choices=candidatos(root)
    if configuration.exists():
        try:choices.append(Path(configuration.read_text(encoding='utf-8').strip()))
        except OSError:pass
    choices.append(Path(sys.executable))
    for executable in dict.fromkeys(choices):
        if compatible(executable):return executable.resolve()
    print('Esta copia R19 necesita un entorno CAD preparado.\n'
          'Si ya usas un Visor R7 a R18, selecciona ahora su carpeta. Se utilizarán sus dependencias sin modificarla.\n'
          'Si prefieres instalar un entorno nuevo, cancela y ejecuta Instalar_Entorno.bat.',flush=True)
    folder=seleccionar_carpeta()
    if folder:
        for executable in candidatos(folder):
            if compatible(executable):
                configuration.write_text(str(executable.resolve()),encoding='utf-8')
                return executable.resolve()
    print('No se ha seleccionado un entorno CAD compatible. Ejecuta Instalar_Entorno.bat y vuelve a abrir Iniciar.bat.',flush=True)
    return None
