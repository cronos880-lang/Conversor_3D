"""No repetir en el mismo proceso una construcción idéntica ya fallida."""
import functools
import hashlib
import inspect
import os

_fallos = {}


def evitar_repetidos(function):
    signature=inspect.signature(function)
    @functools.wraps(function)
    def wrapped(path_stl,path_step,log,**kwargs):
        bound=signature.bind(path_stl,path_step,log,**kwargs);bound.apply_defaults()
        options=tuple((k,v) for k,v in bound.arguments.items() if k not in ('path_stl','path_step','log'))
        defaults={'VISOR_CENTROID_GATE':'0','VISOR_REFINAMIENTO_BREP':'0',
                  'VISOR_EXPERIMENTAL_CILINDROS':'0','VISOR_LIMPIEZA_FRANJAS':'0',
                  'VISOR_RECONOCIMIENTO_ORIGINAL':'0','VISOR_PERFIL':'precision',
                  'VISOR_VERIFICAR_INTERFERENCIAS_CAD':'0','VISOR_RECUPERACION_CAD':'1'}
        env=tuple((k,os.environ.get(k,v)) for k,v in defaults.items())
        key=(hashlib.sha256(path_stl.read_bytes()).hexdigest(),options,env)
        if key in _fallos:
            print('[Reintento omitido] Misma malla, parámetros y perfil: '+_fallos[key],file=log,flush=True)
            raise ValueError(_fallos[key])
        try:return function(path_stl,path_step,log,**kwargs)
        except ValueError as exc:
            # No retener excepciones con traceback y sólidos nativos en memoria.
            # Las subclases con diagnósticos específicos conservan su recorrido.
            if type(exc) is ValueError:_fallos[key]=str(exc)
            raise
    return wrapped
