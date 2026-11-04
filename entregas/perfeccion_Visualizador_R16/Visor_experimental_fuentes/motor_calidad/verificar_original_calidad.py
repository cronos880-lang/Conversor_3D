"""Validación independiente contra el STL original, antes de publicar la mejora."""
from pathlib import Path
import sys,json,hashlib,tempfile,os,time
import numpy as np
from preprocesador_stl import cargar_exacto
from prueba_cad import desde_trabajador
from motor_v2 import _calidad
from calidad_topologica import leer_solido_step_estricto
from reconstruccion_curvas import certificar_mallado
from verificacion_reparacion import distancia_malla
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.TopAbs import TopAbs_IN,TopAbs_ON,TopAbs_OUT
from OCP.gp import gp_Pnt
import igl

REVISION='R12_ORIGINAL_CGAL3_MATERIAL_20261030'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def comprobar_material_original(original,shape,*,progress=None):
    """Same deterministic original-material test, reusable without repeating CAD."""
    rng=np.random.default_rng(20261030);points=rng.uniform(original.bounds[0],original.bounds[1],size=(3000,3))
    from topologia_vertices import inspeccionar_vertices
    contacts=inspeccionar_vertices(original).get('ejemplos',[])
    extra=[np.array(contact['xyz_mm'])+sign*d*axis for contact in contacts for d in (.002,.004,.01) for sign in (-1,1) for axis in np.eye(3)]
    if extra:points=np.vstack([points,extra])
    points=points[distancia_malla(original,points)>.002]
    before=igl.winding_number(original.vertices,original.faces,points)>.5
    from material_cad_indexado import ClasificadorMaterial
    if progress is not None:progress(0,len(points))
    classifier=ClasificadorMaterial(shape)
    after=classifier.classify(points,expected=before,progress=progress)
    if not np.array_equal(before,after):raise ValueError('El material del STEP no coincide con el STL original')
    return dict(puntos=len(points),puntos_extra_contacto=len(extra),discrepancias=0,banda_excluida_mm=.002,clasificador='CAD_exacto_indexado_doble_rayo',consultas_nativas=classifier.queries,fallbacks=classifier.fallbacks,tolerancia_cad_mm=1e-7)


def ejecutar(source,prepared,step,worker_path,report_path):
    source,prepared,step,worker_path,report_path=map(Path,(source,prepared,step,worker_path,report_path))
    # source y prepared pueden ser el mismo archivo en una entrada sana.
    inputs=(source,prepared,step,worker_path)
    if report_path.exists() or any(report_path.resolve()==p.resolve() or (report_path.exists() and report_path.samefile(p)) for p in inputs):raise ValueError('El informe debe ser nuevo y distinto de las entradas')
    identity=tuple(map(sha,inputs));record=json.loads(worker_path.read_text())
    if not record.get('ok') or record.get('original_sha256')!=identity[1] or record.get('step_sha256')!=identity[2]:raise ValueError('El STEP no coincide con el trabajador certificado')
    original=cargar_exacto(source);reference=cargar_exacto(prepared);shape=leer_solido_step_estricto(step);start=time.monotonic()
    os.environ['VISOR_PERFIL']='precision'
    quality=_calidad(source,step,original,control_avanzado=True,prueba_cad=desde_trabajador(record,step))
    with tempfile.TemporaryDirectory(prefix='visor_calidad_original_') as directory:
        fine=certificar_mallado(shape,reference,Path(directory)/'frontera.off',quality,referencia_superficie=original)
    material=comprobar_material_original(original,shape)
    if identity!=tuple(map(sha,inputs)):raise ValueError('Una entrada cambió durante la validación')
    result=dict(ok=True,revision=REVISION,original_sha256=identity[0],preparado_sha256=identity[1],step_sha256=identity[2],trabajador_sha256=identity[3],
                calidad_original=quality,mallado_original=fine,material_original=material,
                topologia_referencia='STL preparado certificado; geometría y material se contrastan con el original',segundos=time.monotonic()-start,limites_aceptacion_modificados=False)
    report_path.write_text(json.dumps(result,indent=2));return 0


if __name__=='__main__':raise SystemExit(ejecutar(*sys.argv[1:]))
