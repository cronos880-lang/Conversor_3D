"""Abrir esta copia del Visor cuando su servidor local esté preparado."""
from pathlib import Path
import json,os,runpy,socket,sys,threading,time,webbrowser,http.client
from urllib.parse import urlsplit
from version_programa import PUERTO,identidad

ROOT=Path(__file__).resolve().parent

def version_local(url):
    address=urlsplit(url)
    if address.scheme!='http' or address.hostname!='127.0.0.1':raise ValueError('Sólo se comprueba el servidor local.')
    connection=http.client.HTTPConnection('127.0.0.1',address.port,timeout=1.)
    try:
        connection.request('GET','/version');response=connection.getresponse()
        if response.status!=200:raise OSError('La otra aplicación no identifica esta copia.')
        return json.loads(response.read())
    finally:connection.close()

def abrir(url):
    if os.environ.get('VISOR_NO_ABRIR_NAVEGADOR')!='1':webbrowser.open(url)

def misma_instancia(url,root=ROOT):
    try:
        data=version_local(url)
        return data==identidad(root)
    except (OSError,ValueError):return False

def abrir_cuando_listo(url,root=ROOT,timeout=60.):
    until=time.monotonic()+timeout
    while time.monotonic()<until:
        if misma_instancia(url,root):
            abrir(url);return True
        time.sleep(.2)
    print('El servidor todavía no está preparado. Revisa esta ventana; cuando arranque abre '+url,flush=True)
    return False

def main():
    try:
        port=int(os.environ.get('VISOR_PORT',str(PUERTO)))
        if not 1024<=port<=65535:raise ValueError()
    except ValueError:
        print('VISOR_PORT debe ser un puerto entre 1024 y 65535.');return 2
    url=f'http://127.0.0.1:{port}'
    try:
        with socket.socket() as probe:
            if hasattr(socket,'SO_EXCLUSIVEADDRUSE'):probe.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
            probe.bind(('127.0.0.1',port))
    except OSError:
        if misma_instancia(url):
            print('Esta copia ya está abierta en '+url);abrir(url);return 0
        print(f'El puerto {port} está ocupado por otra copia o por otro programa.\n'
              'No se abrirá una versión distinta. Cierra el otro Visor experimental y vuelve a intentarlo.\n'
              'La R7 del puerto 8771 y la R8 del 8772 pueden seguir abiertas.');return 2
    print('Visor R10 experimental. Deja abierta esta ventana.\n'+url,flush=True)
    threading.Thread(target=abrir_cuando_listo,args=(url,),daemon=True).start()
    runpy.run_path(str(ROOT/'servidor.py'),run_name='__main__')
    return 0

if __name__=='__main__':
    if '--entorno-listo' not in sys.argv:
        from entorno_local import resolver
        executable=resolver(ROOT)
        if executable is None:raise SystemExit(2)
        if executable!=Path(sys.executable).resolve():
            import subprocess
            try:
                result=subprocess.run([str(executable),str(Path(__file__).resolve()),'--entorno-listo'],cwd=ROOT,
                                      env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
                raise SystemExit(result.returncode)
            except KeyboardInterrupt:raise SystemExit(130)
    raise SystemExit(main())
