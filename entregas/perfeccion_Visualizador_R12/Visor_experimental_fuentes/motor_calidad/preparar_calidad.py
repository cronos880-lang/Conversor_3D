"""Normalizar exclusivamente una copia de la entrada YA reparada por R11."""
from pathlib import Path
import sys,json,hashlib,tempfile,shutil
import trimesh
from preprocesador_stl import cargar_exacto
from normalizacion_microcaras import normalizar
from reparador_exacto_aislado import ControlExacto,medidas_superficie
from topologia_vertices import inspeccionar_vertices


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def ejecutar(original,prepared,destination,report_path):
    original,prepared,destination,report_path=map(Path,(original,prepared,destination,report_path))
    paths=(original,prepared,destination,report_path)
    if len({p.resolve() for p in paths})!=4 or destination.exists() or report_path.exists():raise ValueError('Rutas distintas y salidas nuevas obligatorias')
    if any(a.exists() and b.exists() and a.samefile(b) for i,a in enumerate(paths) for b in paths[i+1:]):raise ValueError('Las rutas comparten archivo')
    identity=sha(original),sha(prepared);mesh=cargar_exacto(prepared)
    candidate,proof=normalizar(mesh)
    if proof['aplicado']:destination.write_text(trimesh.exchange.stl.export_stl_ascii(candidate),encoding='ascii')
    else:shutil.copyfile(prepared,destination)
    back=cargar_exacto(destination)
    with tempfile.TemporaryDirectory(prefix='visor_calidad_entrada_') as directory:
        if (not back.is_watertight or not back.is_winding_consistent or back.euler_number!=mesh.euler_number or
            len(back.split(only_watertight=False))!=1 or inspeccionar_vertices(back)['vertices_no_manifold'] or
            ControlExacto(back,Path(directory)/'fuente.off').pares()):raise ValueError('La copia no conserva una frontera cerrada regular')
    geometry=medidas_superficie(mesh,back)
    if geometry['max_mm']>1e-7:raise ValueError('La serialización supera la banda de limpieza')
    if identity!=(sha(original),sha(prepared)):raise ValueError('Una entrada cambió durante la limpieza')
    result=dict(ok=True,original_sha256=identity[0],entrada_reparada_sha256=identity[1],salida_sha256=sha(destination),normalizacion=proof,geometria_guardada=geometry)
    report_path.write_text(json.dumps(result,indent=2));return 0


if __name__=='__main__':raise SystemExit(ejecutar(*sys.argv[1:]))
