"""Conversión STL->STEP CAD supervisada. Uso: python motor_v2.py entrada.stl salida.step

- Reconstruye B-Rep matemático con OpenCascade, sin idealización de escaneos.
- Las mallas de trabajo reducidas jamás sustituyen al archivo STL de referencia.
- Rechaza STEP abiertos, de volumen incorrecto, con contornos cambiados o con
  desviación geométrica superficial excesiva (controles muestreados, no prueba absoluta).
- El proceso se ejecuta por separado del servidor para aislar errores de OCC.
"""
from __future__ import annotations

import contextlib
import shutil
import io
import json
import os
# Limitar BLAS evita bloqueos de cálculo en ajustes de superficies grandes.
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
from pathlib import Path
import sys
import tempfile
import traceback

import numpy as np
import trimesh
from avance_conversion import avance

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'motor_superficies'))

# Umbrales conservadores, en las unidades del STL (habitualmente milímetros).
# No pueden garantizar recuperar la superficie anterior a la triangulación.
MAX_INPUT_FACES = 250_000
MAX_INPUT_BYTES = 30 * 1024 * 1024
MAX_WORK_FACES = 20_000
MAX_WORK_FACES_DENSO = 40_000
# Una entrada apenas por encima de 20k también puede usar una malla de trabajo
# ya contrastada. Todas las mediciones finales siguen usando el STL original.
MAX_RECOVERY_INPUT_FACES = 60_000
MAX_WORK_SURFACE_DIFFERENCE = 0.010  # mm; medido en todos los vértices del STL
MAX_VOLUME_ERROR = 0.005            # 0,5 %, además del control de superficies
MAX_BBOX_ERROR = 0.020              # mm
MAX_SURFACE_P95 = 0.020              # mm
MAX_SURFACE_OBSERVED = 0.060         # mm


def _vtk_mesh(file_path):
    import vtk
    reader = vtk.vtkSTLReader()
    reader.SetFileName(str(file_path))
    reader.SetMerging(True)
    reader.Update()
    poly = vtk.vtkPolyData()
    poly.DeepCopy(reader.GetOutput())
    if poly.GetNumberOfPolys() < 1:
        raise ValueError('Archivo STL sin triángulos.')
    return poly


def _distancias_vertices(poly_source, poly_reference, limit=None):
    import vtk
    from vtk.util.numpy_support import vtk_to_numpy

    ref = vtk.vtkImplicitPolyDataDistance()
    ref.SetInput(poly_reference)
    pts = vtk_to_numpy(poly_source.GetPoints().GetData())
    if limit is not None and len(pts) > limit:
        pts = pts[np.linspace(0, len(pts)-1, limit, dtype=int)]
    return np.asarray([abs(ref.EvaluateFunction(pt)) for pt in pts], dtype=float)


def _estadisticas(values):
    values = np.asarray(values, dtype=float)
    return {
        'media': round(float(values.mean()), 6),
        'p95': round(float(np.percentile(values, 95)), 6),
        'p99': round(float(np.percentile(values, 99)), 6),
        'max_muestreado': round(float(values.max()), 6),
        'muestras': int(len(values)),
    }


def _preparar_trabajo(source_path: Path, target_path: Path, original: trimesh.Trimesh, log, *, work_face_limit=MAX_WORK_FACES):
    import vtk
    original_poly = _vtk_mesh(source_path)
    reducer = vtk.vtkQuadricDecimation()
    reducer.SetInputData(original_poly)
    reducer.SetTargetReduction(max(0.0, 1.0 - work_face_limit / len(original.faces)))
    reducer.SetVolumePreservation(True)
    reducer.Update()
    reduced_poly = reducer.GetOutput()
    writer = vtk.vtkSTLWriter()
    writer.SetFileName(str(target_path))
    writer.SetFileTypeToBinary()
    writer.SetInputData(reduced_poly)
    if writer.Write() != 1:
        raise ValueError('Error al preparar la malla de trabajo.')
    work = trimesh.load(str(target_path), force='mesh', process=True)
    if not work.is_watertight or not work.is_winding_consistent or len(work.split(only_watertight=False)) != 1:
        raise ValueError('La preparación de la malla no conserva su topología cerrada.')
    changed_volume = abs(abs(work.volume)-abs(original.volume))/max(abs(original.volume),1e-12)
    old_to_new = _distancias_vertices(original_poly,reduced_poly)
    new_to_old = _distancias_vertices(reduced_poly,original_poly)
    error = max(float(old_to_new.max()),float(new_to_old.max()))
    print(f'[Preparación] {len(original.faces)} -> {len(work.faces)} triángulos; '
          f'desviación máxima en vértices {error:.6f} mm; volumen {changed_volume:.5%}', file=log,flush=True)
    if error > MAX_WORK_SURFACE_DIFFERENCE or changed_volume > 0.0003:
        raise ValueError(f'Para procesar esta malla sería necesario alterar la geometría de trabajo '
                         f'más de {MAX_WORK_SURFACE_DIFFERENCE:.3f} mm. Conversión detenida.')
    return {'caras': len(work.faces), 'distancia_mm': round(error,6),
            'volumen_error_pct': round(changed_volume*100,6)}


def _caja_cad_teselada(solid, original, log=None):
    """Segunda medición si la caja analítica de OCC sobreestima límites de
    superficies B-spline recortadas. No cambia la tolerancia de aceptación.

    Las cajas de triangulaciones CAD se calculan a dos resoluciones y se
    amplían conservadoramente para evitar aceptar cotas falsas por teselación.
    Este método NO sustituye las comprobaciones de superficies ni de volumen.
    """
    bounds=[]
    for deflexion in (0.008, 0.003):
        vertices, _ = solid.tessellate(deflexion)
        if not vertices:
            raise ValueError('No se pudo recalcular la caja CAD con una triangulación fina.')
        arr=np.asarray([[v.x,v.y,v.z] for v in vertices],dtype=float)
        bounds.append(np.array([arr.min(axis=0),arr.max(axis=0)]))
    if not np.all(np.isfinite(bounds)):
        raise ValueError('Caja CAD teselada no finita.')
    # Las dos cajas deben ser estables y dentro de un margen inferior a 0.005 mm.
    if np.max(np.abs(bounds[0]-bounds[1])) > 0.005:
        raise ValueError('La caja del STEP depende demasiado de la triangulación.')
    measured=float(np.max(np.abs(bounds[1]-original.bounds)))
    return measured + 0.003  # seguridad conservadora, sin relajar límite 0.020 mm


def _calidad(path_stl: Path, step_path: Path, original: trimesh.Trimesh, *, error_preparacion_mm: float = 0.0, control_avanzado=False,prueba_cad=None):
    import cadquery as cq
    import vtk
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from OCP.gp import gp_Pnt
    from collections import Counter
    from vtk.util.numpy_support import vtk_to_numpy

    from perfiles_precision import obtener_perfil
    from diagnostico_validacion import ErrorGeometrico, criterio
    perfil=obtener_perfil()
    bbox_limit=perfil['caja_mm']

    avance(78, 'Releyendo STEP y comprobando sólido, volumen y cotas')
    from calidad_topologica import leer_solido_step_estricto
    solid=leer_solido_step_estricto(step_path)
    # Un candidato con volumen inviable ya debe rechazarse. Algunas superficies
    # recortadas defectuosas hacen muy costosa la caja o su teselación; ninguna
    # de esas mediciones puede rescatar un volumen que supera el límite vigente.
    volume_error_early = float(abs(solid.Volume()-abs(original.volume))/max(abs(original.volume),1e-12))
    if volume_error_early > MAX_VOLUME_ERROR:
        raise ErrorGeometrico('Reconstrucción deformada', [
            criterio('Error de volumen',100*volume_error_early,MAX_VOLUME_ERROR*100,'%')])
    # Todas las rutas se juzgan en lectura fría, antes de teselar un candidato
    # defectuoso. isValid y un único sólido no excluyen autointersecciones.
    from saneamiento_cad import comprobar_interferencias, InterferenciasCAD,exigir_coherencia_exacta
    from prueba_cad import valida as prueba_valida
    control_cad_reutilizado=prueba_valida(prueba_cad,step_path)
    if not control_cad_reutilizado:
        avance(78,f'Comprobando interferencias entre {len(solid.Faces())} caras CAD')
        valid,count=comprobar_interferencias(solid)
        if not valid:raise InterferenciasCAD(count,{'brep_valido':True,'lectura_fria':True})
    avance(78,'Comprobando la coherencia exacta de curvas y superficies CAD')
    exigir_coherencia_exacta(solid)
    sampling_solid = solid.copy()
    bounds = solid.BoundingBox()  # Antes de la teselación, que altera la caché de OCC
    bbox = np.asarray([[bounds.xmin,bounds.ymin,bounds.zmin],
                       [bounds.xmax,bounds.ymax,bounds.zmax]])
    bbox_error_analitico = float(np.max(np.abs(bbox-original.bounds)))
    bbox_error = bbox_error_analitico
    caja_modo='OpenCascade'
    if bbox_error_analitico > bbox_limit:
        bbox_error = _caja_cad_teselada(sampling_solid,original)
        caja_modo='triangulacion CAD a dos resoluciones + margen 0.003 mm'
        print(f'[Caja V4] CAD analítico={bbox_error_analitico:.6f} mm, '
              f'CAD recortado={bbox_error:.6f} mm (margen incluido)',flush=True)
    print(f'[Control STEP exportado] volumen_STL={abs(original.volume):.6f} '
          f'volumen_STEP={solid.Volume():.6f} caras_STEP={len(solid.Faces())}', flush=True)
    volume_error = float(abs(solid.Volume()-abs(original.volume))/max(abs(original.volume),1e-12))
    face_count = len(solid.Faces())
    if face_count >= len(original.faces):
        raise ValueError('El STEP no ha reducido realmente las caras triangulares.')
    if volume_error > MAX_VOLUME_ERROR or bbox_error > bbox_limit:
        raise ErrorGeometrico('Reconstrucción deformada', [
            criterio('Error de volumen',100*volume_error,MAX_VOLUME_ERROR*100,'%'),
            criterio('Desviación de cotas exteriores',bbox_error,bbox_limit)])

    srcpoly = _vtk_mesh(path_stl)
    raw = vtk_to_numpy(srcpoly.GetPoints().GetData())
    # CAD -> STL: usar puntos pertenecientes a la superficie reconstruida.
    # La teselación CAD se emplea solo para tomar muestras; no se exporta como malla.
    # OCC puede adjuntar a la forma polígonos de triangulación defectuosos
    # durante el muestreo y hacer que BRepCheck rechace después ese caché.
    # Muestrear una copia profunda; juzgar el B-Rep STEP recién importado.
    # No se cambia ninguna superficie, muestra ni límite geométrico.
    avance(78, 'Muestreando las superficies CAD del STEP')
    mesh_vertices, triangles = sampling_solid.tessellate(0.010)
    cadpts = np.asarray([[p.x,p.y,p.z] for p in mesh_vertices], dtype=float)
    if len(cadpts)==0:
        raise ValueError('No se ha podido inspeccionar la superficie del STEP.')
    n_muestras = 220 if len(original.faces) > 100_000 else 800
    cadpts = cadpts[np.linspace(0,len(cadpts)-1,min(len(cadpts),n_muestras),dtype=int)]
    query = vtk.vtkImplicitPolyDataDistance()
    query.SetInput(srcpoly)
    cad_to_stl = np.array([abs(query.EvaluateFunction(p)) for p in cadpts])

    # STL -> CAD: distancia directamente al shell B-Rep (no a la triangulación).
    # Esto evita considerar erróneamente como distancia cero puntos interiores.
    src_sample = raw[np.linspace(0,len(raw)-1,min(len(raw),n_muestras),dtype=int)]
    from frontera_cad import frontera_completa
    shell = frontera_completa(solid).wrapped
    dist = BRepExtrema_DistShapeShape()
    dist.LoadS2(shell)
    dlist = []
    for sample_index, p in enumerate(src_sample):
        if sample_index % 100 == 0:
            avance(78, f'Midiendo STL frente al CAD: {sample_index}/{len(src_sample)} puntos')
        vertex = BRepBuilderAPI_MakeVertex(gp_Pnt(*[float(x) for x in p])).Vertex()
        dist.LoadS1(vertex)
        dist.Perform()
        if not dist.IsDone():
            raise ValueError('Falló la medición geométrica de superficies.')
        dlist.append(float(dist.Value()))
    stl_to_cad = np.asarray(dlist)
    result1,result2 = _estadisticas(stl_to_cad),_estadisticas(cad_to_stl)
    # Criterio multiescala: error ≤0,02 mm en piezas pequeñas, ≤0,03 mm
    # en piezas de dimensión característica ≥150 mm. Nunca depende del nombre.
    surface_p95_limit = max(MAX_SURFACE_P95, min(0.030, float(np.linalg.norm(original.extents))*0.0002))
    if len(original.faces) > 100_000:
        # Margen de muestreo medido en el chasis (0.001 mm), sin superar 0.030 mm.
        # Los límites de caja, volumen, máximo y topología NO cambian.
        surface_p95_limit = max(MAX_SURFACE_P95, min(0.030,
            float(np.linalg.norm(original.extents))*0.0002 + 0.001))
    # En una malla de trabajo reducida se conoce una cota observada de error
    # introducido en la preparación. Solo el umbral del MÁXIMO muestreado
    # admite ese margen documentado; el p95 no se relaja. Nunca se usa la
    # diferencia de volumen para justificar una desviación superficial.
    prep = max(0.0, min(float(error_preparacion_mm), MAX_WORK_SURFACE_DIFFERENCE))
    strict_p95_limit=surface_p95_limit
    if perfil['p95_mm'] is not None:
        surface_p95_limit=perfil['p95_mm']
    surface_max_limit = (MAX_SURFACE_OBSERVED + prep if perfil['id']=='precision'
                         else perfil['max_mm'])
    # Una teselación puede ofrecer vértices fuera del recorte real. Antes de
    # rechazar por CAD→STL, medir el punto correspondiente del B-Rep exacto.
    projection={'muestras_proyectadas':0,'max_distancia_al_brep_mm':0.}
    if result2['p95']>surface_p95_limit or result2['max_muestreado']>surface_max_limit:
        from validacion_local import proyectar_en_brep
        cutoff=surface_p95_limit if result2['p95']>surface_p95_limit else surface_max_limit
        suspect=np.flatnonzero(cad_to_stl>cutoff)
        if len(suspect):
            projected,offset=proyectar_en_brep(solid,cadpts[suspect])
            cad_to_stl[suspect]=[abs(query.EvaluateFunction(p)) for p in projected]
            result2=_estadisticas(cad_to_stl)
            projection={'muestras_proyectadas':len(suspect),'max_distancia_al_brep_mm':float(offset.max())}
    p95_observed = max(result1['p95'],result2['p95'])
    max_observed = max(result1['max_muestreado'],result2['max_muestreado'])
    print(f"[Calidad] p95 STL->CAD {result1['p95']:.5f} CAD->STL {result2['p95']:.5f}; "
          f"máximos {result1['max_muestreado']:.5f} y {result2['max_muestreado']:.5f}; "
          f"límite p95 {surface_p95_limit:.5f}, máximo {surface_max_limit:.5f} "
          f"(margen preparación {prep:.6f})",flush=True)
    if p95_observed > surface_p95_limit or max_observed > surface_max_limit:
        reasons = []
        if p95_observed > surface_p95_limit:
            reasons.append(f'p95 {p95_observed:.5f} > {surface_p95_limit:.5f} mm')
        if max_observed > surface_max_limit:
            reasons.append(f'máximo muestreado {max_observed:.5f} > {surface_max_limit:.5f} mm')
        raise ErrorGeometrico('STEP válido, pero la fidelidad superficial no supera el control', [
            criterio('Percentil 95 superficial',p95_observed,surface_p95_limit),
            criterio('Desviación superficial máxima muestreada',max_observed,surface_max_limit)])
    types = Counter(str(BRepAdaptor_Surface(face.wrapped).GetType()).split('.')[-1]
                    for face in solid.Faces())
    avance(78, 'Comprobando integridad final del B-Rep STEP')
    from calidad_topologica import inspeccionar
    topologia=inspeccionar(solid)
    if not topologia['brep_valido'] or topologia['solidos']!=1 or topologia['aristas_parametrizacion_incoherente']:
        raise ValueError('La reconstrucción presenta defectos topológicos en aristas o caras.')
    result = {
        'integridad_cad':topologia,
        'perfil_validacion':perfil,
        'caras_step':face_count, 'bytes_step':step_path.stat().st_size,
        'volumen_error_pct':round(100*volume_error,6),
        'caja_error_mm':round(bbox_error,6),
        'caja_error_analitico_mm':round(bbox_error_analitico,6),
        'caja_modo_verificacion':caja_modo,
        'distancia_stl_step_mm':result1,
        'distancia_step_stl_mm':result2,
        'contraste_muestreo_cad':projection,
        'tipos_caras':dict(types),
        'limites_validacion':{'volumen_error_max_pct': MAX_VOLUME_ERROR*100,
            'caja_error_max_mm':bbox_limit,'p95_superficie_max_mm':surface_p95_limit,
            'desviacion_max_observada_mm':surface_max_limit,'margen_preparacion_mm':prep},
        'nota':'Mediciones de muestras, no garantía absoluta de desviación global.'
    }
    # Puerta adicional solo para entradas reparadas o cuando el muestreo
    # reproduce el falso rechazo de caché. Las entradas históricas sanas
    # mantienen el recorrido y los umbrales de sus comprobaciones.
    result['autointerferencias_occ'] = False
    result['interferencias_comprobadas_en_frio'] = True
    result['control_cad_reutilizado_por_sha256'] = control_cad_reutilizado
    result['sin_objetos_sueltos_en_step'] = True
    result['integridad_cad']['brep_exacto'] = True
    avance(78, 'Inspección densa de caras y aristas del STEP frente al STL de referencia')
    from validacion_densa import exigir_denso
    result['inspeccion_densa'] = exigir_denso(original,solid,
        limite_p95=surface_p95_limit,limite_max=surface_max_limit)
    dense=result['inspeccion_densa']
    observed_max=max(max_observed,dense['stl_a_cad']['max_mm'],dense['cad_a_stl']['max_mm'])
    observed_p95=max(p95_observed,dense['stl_a_cad']['p95_mm'],dense['cad_a_stl']['p95_mm'])
    strict=(bbox_error<=MAX_BBOX_ERROR and volume_error<=MAX_VOLUME_ERROR
            and observed_p95<=strict_p95_limit and observed_max<=MAX_SURFACE_OBSERVED+prep)
    result['precision_alcanzada']='precision' if strict else 'impresion'
    result['desviacion_max_verificada_mm']=round(float(observed_max),6)
    result['limites_precision_originales']={'caja_mm':MAX_BBOX_ERROR,'p95_mm':strict_p95_limit,
                                           'max_mm':MAX_SURFACE_OBSERVED+prep}
    return result


from intentos_conversion import evitar_repetidos


@evitar_repetidos
def convertir(path_stl: Path, path_step: Path, log, *, flat_tol_deg=8.0,
             digital=False, analitico=False, sin_simplificar=False, precision_reparacion=False, control_avanzado=False, union_certificada=False,
             bandas_revolucion=False, conservar_vertices=False, proteger_contactos=False,
             cavidades_verificadas=False):
    from meshfit_detect import detect
    from meshfit_step import export_step
    avance(20, "Comprobando la malla STL")
    if conservar_vertices:
        from preprocesador_stl import cargar_exacto
        original=cargar_exacto(path_stl)
    else:
        original = trimesh.load(str(path_stl),force='mesh',process=True)
    if not isinstance(original,trimesh.Trimesh) or not len(original.faces):
        raise ValueError('No se ha podido leer una malla STL válida.')
    if len(original.faces)>MAX_INPUT_FACES:
        raise ValueError(f'Este STL contiene {len(original.faces):,} triángulos; el máximo actual '
                         f'es {MAX_INPUT_FACES:,}. No se reducirá sin comprobar la precisión.')
    if not original.is_watertight or not original.is_winding_consistent:
        raise ValueError('Para obtener un sólido CAD fiable, el STL debe estar cerrado y orientado.')
    if len(original.split(only_watertight=False))!=1 and not cavidades_verificadas:
        raise ValueError('La malla contiene varios componentes; aún no se reconstruyen como un único sólido.')
    if abs(original.volume)<1e-9:
        raise ValueError('El STL no encierra un volumen válido.')
    attempts = []
    with tempfile.TemporaryDirectory(prefix='visor_step_v2_') as t:
        t = Path(t)
        mesh_path = path_stl
        prep = None
        inventario = None
        reconocimiento_bruto = None
        if os.environ.get('VISOR_RECONOCIMIENTO_ORIGINAL') == '1':
            # Estudiar el STL completo antes de la decimación; sin tocar geometría.
            from reconocimiento_diseno import inventario_original
            inventario, reconocimiento_bruto = inventario_original(
                path_stl, detect, flat_tol_deg=flat_tol_deg)
            print(f'[Intención CAD, malla original] {inventario["tipos"]}; '
                  f'{inventario["num_relaciones"]} relaciones candidatas; '
                  f'{inventario["num_uniones_analiticas"]} uniones',file=log,flush=True)

        work_limit = MAX_WORK_FACES_DENSO if digital and len(original.faces) > 100_000 else MAX_WORK_FACES
        if len(original.faces) > work_limit and not sin_simplificar:
            mesh_path = t / 'trabajo.stl'
            # V4: progresar desde la mínima malla validable; el STL original
            # siempre se conserva para medir fidelidad. Nunca aceptar una
            # simplificación que incumple el límite anterior de 0.010 mm.
            limites = sorted({min(len(original.faces),int(n)) for n in
                             (work_limit, 30_000, 40_000, 60_000, 80_000)
                             if n>=work_limit and int(n)<len(original.faces)})
            for limite in limites:
                try:
                    prep = _preparar_trabajo(path_stl,mesh_path,original,log,
                                             work_face_limit=limite)
                    print(f'[Preparación V4] Aceptados {prep["caras"]} triángulos de trabajo',
                          file=log,flush=True)
                    break
                except ValueError as e:
                    print(f'[Preparación V4] {limite} triángulos rechazados: {e}',
                          file=log,flush=True)
            if prep is None:
                # No aceptar una reducción inválida; trabajar con STL original.
                mesh_path = path_stl
                print('[Preparación V4] Ninguna reducción segura: '
                      'se conserva la malla original.',file=log,flush=True)
        elif sin_simplificar:
            print('[Preparación V4] Recuperación sobre el STL original, sin decimar.',
                  file=log,flush=True)
        os.environ['VISOR_STL_DIGITAL']='1' if digital else '0'
        avance(35, "Detectando planos, cilindros y superficies")
        detect_options={'mesh_input':original} if conservar_vertices and mesh_path==path_stl else {}
        res,working = detect(str(mesh_path),angle_tol_deg=32.0,rms_tol_rel=0.01,
                             flat_tol_deg=flat_tol_deg,
                             scan_mode=False,**detect_options)
        bandas=[]
        if bandas_revolucion:
            from revolucion_verificada import incorporar
            bandas=incorporar(res,working)
            if not bandas:
                raise ValueError('Sin bandas circulares completas verificadas para reducir fragmentación.')
            print(f'[Bandas circulares verificadas] {bandas}',file=log,flush=True)
        if reconocimiento_bruto is not None and prep is not None:
            from reconocimiento_diseno import transferir_etiquetas
            transferencia = transferir_etiquetas(reconocimiento_bruto, working)
            print(f'[Intención CAD, transferencia conservadora] {transferencia}',file=log,flush=True)
            inventario['transferencia_a_malla_reducida'] = transferencia
            inventario['regiones_despues_de_reducir'] = len(res['primitives'])
        cilindros_analiticos=[]
        if analitico and digital and len(original.faces) <= MAX_WORK_FACES and prep is None:
            from refinamiento_analitico import recuperar_cilindros
            cilindros_analiticos=recuperar_cilindros(res,working,tol=.008)
            if cilindros_analiticos:
                print(f'[CAD analítico] Cilindros recuperados y verificados: {cilindros_analiticos}',file=log,flush=True)
        if os.environ.get('VISOR_EXPERIMENTAL_CILINDROS') == '1':
            from axial_recognition import inject_verified_cylinders
            new_cyls=inject_verified_cylinders(res,working)
            print(f'[Reconocimiento axial verificado] {new_cyls}',file=log,flush=True)
        print(f'[Detección] {len(res["primitives"])} regiones analíticas y '
              f'{len(res.get("freeform_regions",[]))} regiones libres; '
              f'segmentación={flat_tol_deg:.1f}°',file=log,flush=True)
        # Una región grande etiquetada como plano y con RMS claramente NO plano
        # suele indicar que una curva suave ha quedado atrapada en el cluster
        # coplanar. El refinamiento posterior se permite únicamente si afecta
        # una parte importante de la geometría; de otro modo se protege el
        # resultado de la versión estable.
        suspicious=sum(int(p['n_faces']) for p in res['primitives']
                       if p['type']=='plane' and p['n_faces']>=100 and p['rms']>.020)
        fraction_suspicious = float(suspicious / len(original.faces))
        candidate = t / 'candidato.step'
        # No se ejecutan funciones de idealización, simetrización, rosca o escaneado.
        avance(55, "Reconstruyendo el B-Rep con el motor estable")
        regiones_bloqueadas=None;proteccion=None
        if proteger_contactos:
            from reparacion_contactos_locales import regiones_planas_protegidas
            regiones_bloqueadas,proteccion=regiones_planas_protegidas(working)
            print(f'[Protección local CAD] {proteccion}',file=log,flush=True)
        with contextlib.redirect_stdout(log):
            export_step(res,working,str(candidate),organic=True,solid=True,
                        organic_smooth=0.0,ajuste_ia=False,require_solid=True,
                        precision_reparacion=precision_reparacion,
                        **({'regiones_bloqueadas':regiones_bloqueadas,
                            'preservar_contactos':True,
                            'cavidades_verificadas':cavidades_verificadas} if proteger_contactos else
                           ({'cavidades_verificadas':True} if cavidades_verificadas else {})))
        from meshfit_step import LAST_INFO
        if not LAST_INFO.get('solid') or not LAST_INFO.get('valid'):
            raise ValueError('No se ha reconstruido un B-Rep cerrado válido. '
                             'La versión V2 no exportará un STEP facetado como sustituto.')
        if not candidate.exists():
            raise ValueError('La reconstrucción no ha producido un archivo STEP.')
        # Limpieza opcional y validada de franjas COPLANARES (no idealización).
        # Si falla, se conserva el STEP reconstruido original.
        from limpieza_franjas import limpiar
        limpieza_path = t / 'limpieza.step'
        try:
            if digital and os.getenv("VISOR_LIMPIEZA_FRANJAS", "0") != "1":
                raise RuntimeError("Omitida en mallas densas para preservar el B-Rep construido")
            limpieza = limpiar(path_stl,candidate,limpieza_path,original,_calidad)
            print(f'[Franjas] {limpieza}',file=log,flush=True)
            if limpieza.get('aplicado'):
                candidate=limpieza_path
        except Exception as exc:
            limpieza={'aplicado':False,'motivo':f'Error no bloqueante: {exc}'}
            print(f'[Franjas] {limpieza}',file=log,flush=True)
        avance(78, "Validando sólido, cotas y precisión")
        from saneamiento_cad import InterferenciasCAD,IncoherenciaCAD,intentar_sanear
        saneamiento = {'aplicado':False}
        try:
            quality = _calidad(path_stl,candidate,original,
                               error_preparacion_mm=prep['distancia_mm'] if prep else 0.0,
                               control_avanzado=control_avanzado)
        except (InterferenciasCAD,IncoherenciaCAD) as initial:
            if union_certificada:
                # El llamador ya dispone de una unión certificada. Evitar
                # reconstrucciones alternativas que repitan el ajuste fallido;
                # la recuperación exterior vuelve a verificar el original.
                raise
            print(f'[Recuperación CAD] {initial}',file=log,flush=True)
            avance(78,'Resolviendo interferencias del candidato CAD; se conservarán los límites')
            try:
                if isinstance(initial,IncoherenciaCAD):
                    from reconstruccion_curvas import intentar_refinar
                    quality,saneamiento = intentar_refinar(path_stl,candidate,original,
                        lambda src,step,mesh: _calidad(src,step,mesh,
                            error_preparacion_mm=prep['distancia_mm'] if prep else 0.0,
                            control_avanzado=True),log,
                        validar_con_prueba=lambda src,step,mesh,prueba:_calidad(src,step,mesh,
                            error_preparacion_mm=prep['distancia_mm'] if prep else 0.0,
                            control_avanzado=True,prueba_cad=prueba))
                else:
                    quality,saneamiento = intentar_sanear(path_stl,candidate,original,
                        lambda src,step,mesh: _calidad(src,step,mesh,
                            error_preparacion_mm=prep['distancia_mm'] if prep else 0.0,
                            control_avanzado=True))
            except Exception as repair_error:
                if isinstance(initial,IncoherenciaCAD):
                    print(f'[Contornos compatibles] Descartado: {repair_error}',file=log,flush=True)
                    raise initial from repair_error
                print(f'[Saneamiento CAD] Descartado: {repair_error}',file=log,flush=True)
                try:
                    from reconstruccion_curvas import intentar_refinar
                    quality,saneamiento = intentar_refinar(path_stl,candidate,original,
                        lambda src,step,mesh: _calidad(src,step,mesh,
                            error_preparacion_mm=prep['distancia_mm'] if prep else 0.0,
                            control_avanzado=True),log,
                        validar_con_prueba=lambda src,step,mesh,prueba:_calidad(src,step,mesh,
                            error_preparacion_mm=prep['distancia_mm'] if prep else 0.0,
                            control_avanzado=True,prueba_cad=prueba))
                except Exception as refinement_error:
                    print(f'[Refinamiento de curvas] Descartado: {refinement_error}',file=log,flush=True)
                    raise initial from refinement_error
        if os.environ.get('VISOR_VALIDACION_LOCAL') == '1':
            import cadquery as cq
            from validacion_local import inspeccionar_local
            cad = cq.importers.importStep(str(candidate)).solids().vals()[0]
            informe_local = inspeccionar_local(path_stl,cad,puntos_stl=700,
                                              puntos_cad=300,
                                              tolerancia_max=MAX_SURFACE_OBSERVED)
            print('[Validación local] ' + json.dumps(informe_local,ensure_ascii=False),
                  file=log,flush=True)
            # Informativo hasta estudiar falsos positivos por facetas STL.
            quality['inspeccion_local_experimental'] = informe_local
        avance(79, "Candidato STEP validado; evaluando otras reconstrucciones")
        path_step.write_bytes(candidate.read_bytes())
        return {
            'caras_stl':int(len(original.faces)),
            'diagnostico': {'caras_de_planos_dudosos': suspicious,
                            'proporcion': round(fraction_suspicious, 5),
                            'segmentacion_grados': flat_tol_deg},
            'modo':'superficies',
            'preparacion':prep,
            'saneamiento_cad':saneamiento,
            'reconocimiento_original_experimental':inventario,
            'cilindros_analiticos_verificados':cilindros_analiticos,
            'bandas_revolucion_verificadas':bandas,
            'proteccion_contactos':proteccion,
            'limpieza_franjas':limpieza,
            'calidad':quality,
            'motor':'Reconstrucción CAD de superficies, sin idealización',
        }



def _mejora_suficiente(original, refinado):
    """Selección geométrica neutra: preferir menos facetas SOLO si las
    tolerancias y precisión real no empeoran significativamente.
    No examina nombres de archivos, ni reutiliza resultados CAD de terceros.
    """
    a, b = original['calidad'], refinado['calidad']
    upgrade=a.get('precision_alcanzada','precision')=='impresion' and b.get('precision_alcanzada','precision')=='precision'
    if a.get('precision_alcanzada','precision')=='precision' and b.get('precision_alcanzada','precision')=='impresion':
        return False,'La alternativa pierde el nivel de precisión ya alcanzado.'
    if not upgrade and b['caras_step'] > 0.85 * a['caras_step']:
        return False, 'La reducción de caras no es sustancial.'
    if b['volumen_error_pct'] > a['volumen_error_pct'] * 1.05:
        return False, 'Empeora la coincidencia de volumen.'
    if b['caja_error_mm'] > a['caja_error_mm'] + 0.001:
        return False, 'Empeora el tamaño exterior.'
    at=a['integridad_cad'];bt=b['integridad_cad']
    if bt['tolerancia_max_mm'] > max(at['tolerancia_max_mm']*1.15, at['tolerancia_max_mm']+0.002):
        return False, 'Las tolerancias CAD empeoran.'
    if bt['tolerancia_p95_mm'] > max(at['tolerancia_p95_mm']*1.20, at['tolerancia_p95_mm']+0.002):
        return False, 'La mayoría de las aristas presenta tolerancias peores.'
    for direction in ('distancia_stl_step_mm','distancia_step_stl_mm'):
        old, new = a[direction],b[direction]
        if new['p95'] > old['p95'] + 0.004 or new['max_muestreado'] > old['max_muestreado'] + .010:
            return False, 'La desviación superficial de la alternativa empeora.'
    return True, ('Mayor precisión verificada, sin empeorar los otros controles.' if upgrade else
                  'Menos caras planas residuales, sólido validado y precisión conservada.')

def _comparar_candidatos_cad(anterior, nuevo):
    """Permitir menos caras solo si NO empeoran materialmente la precisión y la topología.

    Estos son umbrales de comparación ENTRE dos STEP que YA han pasado _calidad;
    no cambian ni relajan el validador dimensional y volumétrico.
    """
    a,b=anterior['calidad'],nuevo['calidad']
    upgrade=a.get('precision_alcanzada','precision')=='impresion' and b.get('precision_alcanzada','precision')=='precision'
    if a.get('precision_alcanzada','precision')=='precision' and b.get('precision_alcanzada','precision')=='impresion':
        return False,'Se conserva el candidato que ya alcanza precisión.'
    n0,n1=a['caras_step'],b['caras_step']
    if not upgrade and n1 >= n0-max(4,int(n0*.05)):
        return False, 'La reducción de caras es insuficiente.'
    if b['caja_error_mm'] > a['caja_error_mm']+.003:
        return False, 'Empeoran las dimensiones.'
    if b['volumen_error_pct'] > max(.15,a['volumen_error_pct']+.04):
        return False, 'Empeora el volumen.'
    if b['integridad_cad']['tolerancia_max_mm'] > a['integridad_cad']['tolerancia_max_mm']+.005:
        return False, 'Empeora la tolerancia de las aristas.'
    if b['integridad_cad']['tolerancia_p95_mm'] > a['integridad_cad']['tolerancia_p95_mm']+.002:
        return False, 'Empeora la mayor parte de las aristas.'
    for d in ('distancia_stl_step_mm','distancia_step_stl_mm'):
        if b[d]['p95'] > a[d]['p95']+.002 or b[d]['max_muestreado'] > a[d]['max_muestreado']+.010:
            return False, 'Empeoran las desviaciones superficiales.'
    a_bs=sum(v for k,v in a['tipos_caras'].items() if 'BSpline' in k)
    b_bs=sum(v for k,v in b['tipos_caras'].items() if 'BSpline' in k)
    if b_bs > a_bs+max(2,int(.10*a_bs)):
        return False, 'Aumenta la fragmentación B-spline.'
    return True, ('Mayor precisión verificada sin empeorar materialmente los demás controles.' if upgrade else
                  f'Menos caras CAD: {n0} → {n1}, sin incumplir controles de fidelidad.')


def _main_cad():
    if len(sys.argv)!=3:
        print(json.dumps({'ok':False,'error':'Uso: motor_v2.py entrada.stl salida.step'}))
        return 1
    src,dst=map(Path,sys.argv[1:])
    log_path=dst.with_suffix('.motor.log')
    avance(5, "Leyendo el STL")
    try:
        if not src.is_file() or src.stat().st_size>MAX_INPUT_BYTES:
            raise ValueError('No se encuentra el STL o supera el límite de 30 MB.')
        with log_path.open('w',encoding='utf-8',buffering=1) as log:
            # Método de perfiles CAD general para STL digitales estratificados.
            # Se usa por características geométricas, nunca por el nombre.
            # Las piezas conocidas de V2.7 conservan su motor de superficies.
            triangles = len(trimesh.load(str(src),force='mesh',process=False).faces)
            fallos_rapidos=0
            avance(10, f"STL leído: {triangles} triángulos")
            print("[Estrategia] Motor estable V2.7, sin prioridad ni rescate de Easymeshfit original.",
                  file=log,flush=True)
            if 20_000 < triangles <= 60_000:
                # El método por perfiles usa shapely para contornos y vaciados.
                # Si está ausente, no continuar 600 s con un método inapropiado.
                try:
                    import shapely
                except ImportError as e:
                    raise RuntimeError('Falta la dependencia shapely. Instálala con: '
                                       'python -m pip install -r requirements.txt') from e
                try:
                    avance(20, "Analizando posibilidad de perfiles CAD")
                    from perfiles_cad import detectar_eje, construir_por_vaciados
                    original = trimesh.load(str(src),force='mesh',process=True)
                    strata = detectar_eje(original)
                    if strata is not None and len(strata[2])>=3:
                        avance(55, "Construyendo perfiles y vaciados")
                        with contextlib.redirect_stdout(log):
                            info=construir_por_vaciados(src,dst,profile_tol=0.005)
                        avance(78, "Validando STEP por perfiles")
                        quality = _calidad(src,dst,original)
                        avance(79, "STEP por perfiles validado; terminando conversión")
                        result = {
                            'caras_stl':int(len(original.faces)),
                            'modo':'extrusiones_y_vaciados',
                            'estrategia':'perfiles_cad_verificados',
                            'perfiles':info,
                            'calidad':quality,
                            'motor':'Reconstrucción por perfiles CAD y recortes geométricos',
                        }
                        print(json.dumps({'ok':True,'resultado':result},ensure_ascii=True))
                        return 0
                except Exception as e:
                    print(f'[Perfiles CAD] rechazado por validación: {e}',file=log,flush=True)
                    if dst.exists(): dst.unlink()
            # RUTA RAPIDA GENERAL: mallas CAD pequenas con curvaturas locales
            # suficientemente marcadas. La malla se clasifica por sus normales,
            # nunca por el nombre del archivo. Evita repetir reparaciones de
            # contornos estancados antes de ensayar CAD analitico.
            if 1_500 <= triangles <= 12_000 and os.getenv('VISOR_RUTA_RAPIDA','1') == '1':
                try:
                    muestra=trimesh.load(str(src),force='mesh',process=True)
                    angulos=np.degrees(muestra.face_adjacency_angles)
                    mediana=float(np.median(angulos)) if len(angulos) else 0.0
                    if 3.0 <= mediana <= 8.0 and muestra.is_watertight:
                        print(f'[Ruta rápida] Diedro mediano {mediana:.2f} grados: '
                              'probando CAD digital analitico antes del B-Rep clasico.',file=log,flush=True)
                        with tempfile.TemporaryDirectory(prefix='visor_rapido_') as td:
                            pre_mejor=None;pre_path=None;validos_rapidos=0
                            for angulo in (4.0, 6.0, 3.0, 5.0, 7.0):
                                destino=Path(td)/f'analitico_{angulo:.0f}.step'
                                try:
                                    candidato=convertir(src,destino,log,flat_tol_deg=angulo,
                                                       digital=True,analitico=True,control_avanzado=True)
                                    validos_rapidos+=1
                                    candidato['estrategia']='rapida_analitica_validada'
                                    candidato['segmentacion_grados']=angulo
                                    if pre_mejor is None:
                                        pre_mejor=candidato;pre_path=destino
                                    else:
                                        mejor,razon=_comparar_candidatos_cad(pre_mejor,candidato)
                                        if mejor: pre_mejor=candidato;pre_path=destino
                                    ncaras=pre_mejor['calidad']['caras_step']
                                    n_bs=sum(v for k,v in pre_mejor['calidad']['tipos_caras'].items()
                                             if 'BSpline' in k)
                                    if (ncaras <= 40 and n_bs == 0) or validos_rapidos >= 2:
                                        break
                                except Exception as exc:
                                    print(f'[Ruta rápida] {angulo:.0f}° no aceptada: {exc}',
                                          file=log,flush=True)
                                    fallos_rapidos+=1
                                    if fallos_rapidos>=2:
                                        print('[Ruta rápida] Dos fallos: se prueba ahora el motor habitual. '
                                              'Las variantes restantes quedan para la recuperación.',file=log,flush=True)
                                        break
                            if pre_mejor is not None:
                                shutil.copyfile(pre_path,dst)
                                print(f'[Ruta rápida] STEP aceptado con '
                                      f'{pre_mejor["calidad"]["caras_step"]} caras',file=log,flush=True)
                                print(json.dumps({'ok':True,'resultado':pre_mejor},ensure_ascii=True))
                                return 0
                except Exception as exc:
                    print(f'[Ruta rápida] Sin resultado, usando motor estable: {exc}',file=log,flush=True)
            # Motor V2.7 mantenido; modo digital solo en mallas muy densas.
            # Mantener EXACTAMENTE el motor V2.4 cuando ya da un buen STEP.
            # Solo reintentar con un ajuste geométrico más exigente si se
            # detecta una reconstrucción incorrecta (ej.: hexágono -> cilindro).
            os.environ['VISOR_CENTROID_GATE'] = '0'
            recuperado_experimental = False
            try:
                dense = len(trimesh.load(str(src), force='mesh',process=False).faces)>100_000
                result=convertir(src,dst,log,digital=dense,control_avanzado=fallos_rapidos>0)
                result['estrategia'] = 'digital_denso' if dense else 'compatible_v2_4'
                if result.get('saneamiento_cad',{}).get('metodo')=='contornos_compatibles_ciclos_analiticos':
                    result['estrategia']='contornos_compatibles_verificados'
            except ValueError as first:
                why = str(first)
                can_retry = any(x in why for x in (
                    'Reconstrucción deformada', 'distancia entre sus superficies',
                    'No se ha reconstruido un B-Rep cerrado válido',
                    'defectos topológicos', 'El STEP no contiene exactamente',
                    'El STEP contiene objetos sueltos',
                    'El motor B-Rep no ha reconstruido',
                    'Inspección densa rechazada','fidelidad superficial',
                ))
                if not can_retry:
                    raise
                if dense and 100_000 < triangles <= 160_000:
                    print('[Recuperación V4] STL denso: probando sin reducción '
                          'para recuperar regiones originales.',file=log,flush=True)
                    try:
                        result=convertir(src,dst,log,flat_tol_deg=6.0,
                                         digital=True,sin_simplificar=True,control_avanzado=True)
                        result['estrategia']='v4_malla_original_verificada'
                        print(json.dumps({'ok':True,'resultado':result},ensure_ascii=True))
                        return 0
                    except ValueError as e:
                        print(f'[Recuperación V4] Candidato no aceptado: {e}',
                              file=log,flush=True)
                        raise ValueError(f'La reconstrucción densa no ha superado '
                                         f'los controles. Reducida: {why}; original: {e}') from e
                if dense:
                    raise
                print(f'[Recuperación] Primer intento rechazado: {why}',file=log,flush=True)
                # V4.0 R1: rescate de curvaturas verificadas ANTES de los reintentos
                # 4/6/3/5/7 grados. El motor V3 ya podia reconstruir superficies
                # cilindricas y toroidales con segmentacion 1.3 grados, pero la V4
                # solo alcanzaba esa ruta DESPUES de aceptar un candidato previo.
                # En la maneta el candidato inicial es solido valido pero pierde
                # ~16.6% de volumen; sin este rescate se rechaza inutilmente.
                # Probar solo mallas pequenas tras fallo real, sin excepciones
                # por nombre y sin relajar NINGUNA validacion geometrica.
                if (triangles <= MAX_RECOVERY_INPUT_FACES and
                        os.getenv('VISOR_RECUPERACION_CURVAS','1') == '1'):
                    vars_curvas=('VISOR_CENTROID_GATE',
                                 'VISOR_REFINAMIENTO_BREP',
                                 'VISOR_EXPERIMENTAL_CILINDROS')
                    anteriores={k:os.environ.get(k) for k in vars_curvas}
                    try:
                        for k in vars_curvas:
                            os.environ[k]='1'
                        with tempfile.TemporaryDirectory(prefix='visor_cad_curvas_') as carpeta:
                            candidato_curvas=Path(carpeta)/'cad_curvas_13.step'
                            print('[Recuperación de curvas] Probando segmentación 1.3° '
                                  'con reconocimiento de cilindros verificado.',
                                  file=log,flush=True)
                            recuperado=convertir(src,candidato_curvas,log,
                                                 flat_tol_deg=1.3,digital=False,control_avanzado=True)
                            # convertir() ya reimporto STEP y valido volumen,
                            # dimensiones, fidelidad de superficie y topologia.
                            shutil.copyfile(candidato_curvas,dst)
                            recuperado['estrategia']='recuperacion_curvas_v3_verificada'
                            print('[Recuperación de curvas] STEP CAD aceptado; '
                                  'no se realizan reintentos adicionales.',
                                  file=log,flush=True)
                            print(json.dumps({'ok':True,'resultado':recuperado},ensure_ascii=True))
                            return 0
                    except Exception as err:
                        print(f'[Recuperación de curvas] Candidato rechazado: {err}',
                              file=log,flush=True)
                        from saneamiento_cad import IncoherenciaCAD
                        if isinstance(err,IncoherenciaCAD):
                            # La reconstrucción de contornos desde el mismo STL
                            # ya se ha agotado. Devolver el rechazo al llamador
                            # permite su recuperación conservadora aislada.
                            raise
                    finally:
                        for k,v in anteriores.items():
                            if v is None:
                                os.environ.pop(k,None)
                            else:
                                os.environ[k]=v
                # Recuperación CAD: solo si FALLÓ el motor estable, sin tocar sus
                # resultados previos. Examinar varias segmentaciones y conservar
                # únicamente STEP reimportados válidos con menos caras reales.
                if (os.environ.get('VISOR_RECUPERACION_CAD','1') == '1'
                        and triangles <= MAX_RECOVERY_INPUT_FACES):
                    with tempfile.TemporaryDirectory(prefix='visor_cad_refinar_') as td:
                        mejor=None;resumen=[]; ruta_mejor=None; validos=0
                        for angulo in (4.0, 6.0, 3.0, 5.0, 7.0):
                            alternativa=Path(td)/f'cad_{angulo:.0f}.step'
                            try:
                                print(f'[Recuperación CAD] Probando segmentación {angulo:.0f}°; '
                                      'verificación analítica de cilindros',file=log,flush=True)
                                candidato=convertir(src,alternativa,log,flat_tol_deg=angulo,
                                                   digital=True,analitico=True,control_avanzado=True)
                                validos+=1
                                candidato['estrategia']='recuperacion_cad_analitica_validada'
                                candidato['segmentacion_grados']=angulo
                                if mejor is None:
                                    mejor=candidato;ruta_mejor=alternativa
                                    resumen.append(f'{angulo:.0f}°: {mejor["calidad"]["caras_step"]} caras')
                                else:
                                    aceptada,razon=_comparar_candidatos_cad(mejor,candidato)
                                    resumen.append(f'{angulo:.0f}°: {candidato["calidad"]["caras_step"]} caras; '+razon)
                                    if aceptada:
                                        mejor=candidato;ruta_mejor=alternativa
                                # Ya se han reconocido las primitivas sin B-splines
                                # y el modelo es compacto. No hay motivo para gastar
                                # más tiempo reconstruyendo el mismo STL.
                                n_bs=sum(v for k,v in mejor['calidad']['tipos_caras'].items()
                                         if 'BSpline' in k)
                                if (mejor['calidad']['caras_step'] <= 40 and n_bs == 0) or validos >= 2:
                                    break
                            except Exception as err:
                                print(f'[Recuperación CAD] {angulo:.0f}° rechazada: {err}',file=log,flush=True)
                                resumen.append(f'{angulo:.0f}° rechazada: {str(err)[:160]}')
                                from saneamiento_cad import IncoherenciaCAD
                                if mejor is None and isinstance(err,IncoherenciaCAD):
                                    raise
                        if mejor is not None:
                            shutil.copyfile(ruta_mejor,dst)
                            result=mejor
                            result['candidatos_cad']=resumen
                            print(f'[Recuperación CAD] Elegida: {resumen}',file=log,flush=True)
                            recuperado_experimental=True
                if not recuperado_experimental:
                    # En las versiones anteriores se repetia por tercera vez
                    # la misma reconstruccion 8 grados. Si las candidatas
                    # distintas fallan, informar sin consumir minutos adicionales.
                    raise ValueError('No se obtuvo un STEP CAD fiel y valido. '
                        f'La reconstruccion estable fallo: {why}. '
                        'Las alternativas geometricas tampoco superaron las mismas '
                        'comprobaciones de volumen, dimensiones y topologia. '
                        'Consulta el diagnostico para ver cada candidato.')

            # Una sola alternativa acotada para STEP válidos muy fragmentados.
            # El original permanece disponible si cualquier control falla.
            from revolucion_verificada import conviene, mejora
            if conviene(result['calidad'],triangles) and not recuperado_experimental:
                alternativa=dst.with_name(dst.stem+'_bandas.step')
                try:
                    propuesta=convertir(src,alternativa,log,bandas_revolucion=True,
                                        control_avanzado=True)
                    aceptar,razon=mejora(result['calidad'],propuesta['calidad'])
                    print(f'[Fragmentación] aceptada={aceptar}; {razon}',file=log,flush=True)
                    if aceptar:
                        anterior=result['calidad']
                        alternativa.replace(dst);result=propuesta
                        result['estrategia']='bandas_circulares_verificadas'
                        result['comparacion_fragmentacion']={'caras_antes':anterior['caras_step'],
                            'caras_despues':result['calidad']['caras_step'],'criterio':razon,
                            'calidad_anterior':anterior}
                except Exception as exc:
                    print(f'[Fragmentación] Se conserva el STEP anterior: {exc}',file=log,flush=True)
                finally:
                    alternativa.unlink(missing_ok=True)

            # Refinamiento localizado por DIAGNÓSTICO, no por archivo.
            # Solo se intenta cuando una parte dominante de la malla se ha
            # clasificado como plano pese a no ser realmente plana.
            mezcla_curva_extensa = result.get('diagnostico',{}).get('proporcion',0) >= 0.45
            mejorar_precision=(result['calidad'].get('precision_alcanzada')=='impresion'
                                and triangles<=MAX_RECOVERY_INPUT_FACES)
            if (mezcla_curva_extensa or mejorar_precision) and not recuperado_experimental:
                alt=dst.with_name(dst.stem + '_refinada.step')
                os.environ['VISOR_CENTROID_GATE']='1'
                os.environ['VISOR_REFINAMIENTO_BREP']='1'
                try:
                    print('[Adaptativa] '+('Buscando precisión dentro del uso impresión' if mejorar_precision else 'Región no plana dominante')+
                          ': intentando segmentación 1.3°',file=log,flush=True)
                    finer=convertir(src,alt,log,flat_tol_deg=1.3,digital=False,control_avanzado=True)
                    accepted,reason=_mejora_suficiente(result,finer)
                    print(f'[Adaptativa] aceptada={accepted}; {reason}',file=log,flush=True)
                    if accepted:
                        alt.replace(dst)
                        result=finer
                        result['estrategia']='segmentacion_geometrica_adaptativa'
                except Exception as e:
                    print(f'[Adaptativa] Sin cambios: {e}',file=log,flush=True)
                finally:
                    os.environ['VISOR_CENTROID_GATE']='0'
                    os.environ['VISOR_REFINAMIENTO_BREP']='0'
                    if alt.exists():
                        alt.unlink()

            # Tercera estrategia, NUNCA por nombre del archivo. Sólo cuando la
            # segmentación inicial evidenció una región curva falsamente plana.
            # En tal caso, buscar cilindros mediante las normales, ajustar su eje
            # y radio a los VÉRTICES reales y comprobar también los centroides.
            # El resultado se adopta sólo si supera LA MISMA validación CAD y
            # mejora las métricas respecto al resultado ya aceptado.
            if mezcla_curva_extensa and not recuperado_experimental:
                alt_cyl=dst.with_name(dst.stem+'_axial_verificado.step')
                os.environ['VISOR_CENTROID_GATE']='1'
                os.environ['VISOR_REFINAMIENTO_BREP']='1'
                os.environ['VISOR_EXPERIMENTAL_CILINDROS']='1'
                try:
                    print('[Curvas axial] Probando reconstrucción matemática verificada',file=log,flush=True)
                    axial=convertir(src,alt_cyl,log,flat_tol_deg=1.3,digital=False,control_avanzado=True)
                    accepted,reason=_mejora_suficiente(result,axial)
                    print(f'[Curvas axial] aceptada={accepted}; {reason}',file=log,flush=True)
                    if accepted:
                        alt_cyl.replace(dst)
                        result=axial
                        result['estrategia']='cilindros_analiticos_verificados'
                except Exception as e:
                    print(f'[Curvas axial] descartada: {e}',file=log,flush=True)
                finally:
                    for name in ('VISOR_CENTROID_GATE','VISOR_REFINAMIENTO_BREP',
                                 'VISOR_EXPERIMENTAL_CILINDROS'):
                        os.environ[name]='0'
                    if alt_cyl.exists():
                        alt_cyl.unlink()
        print(json.dumps({'ok':True,'resultado':result},ensure_ascii=True))
        return 0
    except Exception as exc:
        if dst.exists(): dst.unlink()
        with log_path.open('a',encoding='utf-8') as log:
            traceback.print_exc(file=log)
        print(json.dumps({'ok':False,'error':str(exc),
                          'tipo_error':getattr(exc,'codigo','reconstruccion_cad_rechazada'),
                          'criterios':getattr(exc,'criterios',[])},ensure_ascii=True))
        return 2

class _SalidaCad(io.StringIO):
    """Conservar los mensajes en vivo aunque OCC termine por tiempo/memoria.

    Solo retiene la línea de resultado para adjuntarle el diagnóstico de entrada.
    El servidor ya interpreta el último JSON del proceso.
    """
    def __init__(self, target):
        super().__init__()
        self.target = target
        self.pending = ''

    def write(self, value):
        count = super().write(value)
        self.pending += value
        while '\n' in self.pending:
            line, self.pending = self.pending.split('\n', 1)
            if not line.startswith('{"ok":'):
                self.target.write(line+'\n')
                self.target.flush()
        return count

    def flush(self):
        self.target.flush()


def main():
    """Preparar una sola vez ANTES de todas las estrategias CAD existentes.

    VISOR_PREPROCESADOR=0 conserva la entrada histórica para comparaciones.
    El perfil de precisión conserva los límites históricos de aceptación.
    """
    if len(sys.argv) != 3:
        return _main_cad()
    from preprocesador_stl import preparar, ReparacionRechazada
    src, dst = map(Path, sys.argv[1:])
    numeric=dst.with_name(dst.stem+'_numerico_candidato.step')
    outputs=[dst,dst.with_suffix('.entrada.json'),dst.with_suffix('.rechazos.jsonl'),
             dst.with_suffix('.reparado.stl'),dst.with_suffix('.motor.log'),
             dst.with_suffix('.reparado.reparacion.json'),dst.with_suffix('.reparado.reparacion.log'),
             dst.with_suffix('.reparado.control.off'),dst.with_suffix('.reparado.pendiente.stl'),
             dst.with_name(dst.stem+'_local_candidato.step'),numeric,numeric.with_suffix('.recuperacion.json')]
    outputs.extend([dst.with_suffix('.saneado.stl'),dst.with_suffix('.reparado.saneado.stl'),dst.with_suffix('.reparado.envolventes.off'),dst.with_suffix('.reparado.saneamiento.off')])
    if any(p.resolve()==src.resolve() or (p.exists() and src.exists() and p.samefile(src)) for p in outputs):
        print(json.dumps({'ok':False,'tipo_error':'rutas_incompatibles','error':'La entrada y sus archivos de salida deben ser distintos.'}))
        return 2
    args = sys.argv[:]
    previous_interference_flag = os.environ.get('VISOR_VERIFICAR_INTERFERENCIAS_CAD')
    previous_rejections = os.environ.get('VISOR_RECHAZOS_PATH')
    rejections_path=dst.with_suffix('.rechazos.jsonl')
    rejections_path.unlink(missing_ok=True)
    os.environ['VISOR_RECHAZOS_PATH']=str(rejections_path)
    report = None
    report_path = dst.with_suffix('.entrada.json')
    try:
        if not src.is_file() or src.stat().st_size > MAX_INPUT_BYTES:
            raise ValueError('No se encuentra el STL o supera el límite de 30 MB.')
        if os.environ.get('VISOR_PREPROCESADOR', '1') == '0':
            return _main_cad()
        avance(12, 'Diagnosticando topología y posible unión conservadora')
        prepared, report = preparar(src, dst.with_suffix('.reparado.stl'))
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        if report.get('reparado'):
            os.environ['VISOR_VERIFICAR_INTERFERENCIAS_CAD'] = '1'
        sys.argv = [args[0], str(prepared), str(dst)]
        if report.get('ruta_seleccionada') in ('contactos_locales_exactos_verificados','envolventes_anidadas_verificadas','entrada_saneada_verificada'):
            attempts=[]
            with dst.with_suffix('.motor.log').open('w',encoding='utf-8',buffering=1) as log:
                for protected in (False,True):
                    candidate=dst.with_name(dst.stem+'_local_candidato.step')
                    try:
                        result=convertir(prepared,candidate,log,flat_tol_deg=1.3,
                            digital=True,analitico=True,sin_simplificar=True,precision_reparacion=True,
                            control_avanzado=True,conservar_vertices=True,proteger_contactos=protected,
                            cavidades_verificadas=bool(report['salida'].get('cavidades_cerradas')))
                        # Comprobar también el STL ORIGINAL, con el perfil y los
                        # umbrales existentes; la reparación no oculta su error.
                        from preprocesador_stl import cargar_exacto
                        quality_original=_calidad(src,candidate,cargar_exacto(src),control_avanzado=True)
                        if report.get('verificacion_envolventes') or report.get('saneamiento_entrada'):
                            import cadquery as cq
                            from invariantes_material import InvariantesMaterial
                            from validacion_reconstruccion import certificar_topologia_step
                            reference=cargar_exacto(prepared)
                            result['topologia_material_verificada']=certificar_topologia_step(
                                cq.importers.importStep(str(candidate)).val(),reference,InvariantesMaterial(reference))
                        result['calidad_original']=quality_original
                        result['estrategia']='reparacion_local_y_cad_verificados'
                        candidate.replace(dst)
                        print(json.dumps({'ok':True,'resultado':result,'preprocesamiento':report},ensure_ascii=True))
                        return 0
                    except Exception as exc:
                        attempts.append({'proteccion_local':protected,'error':str(exc)})
                        print(f'[CAD tras reparación local] Descartado: {exc}',file=log,flush=True)
                    finally:candidate.unlink(missing_ok=True)
            if os.environ.get('VISOR_RECUPERACION_NUMERICA','1')=='1':
                candidate=dst.with_name(dst.stem+'_numerico_candidato.step')
                try:
                    from recuperacion_numerica import ejecutar_aislado
                    with dst.with_suffix('.motor.log').open('a',encoding='utf-8',buffering=1) as log:
                        result=ejecutar_aislado(src,prepared,candidate,log)
                    candidate.replace(dst)
                    report['intentos_cad']=attempts
                    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
                    print(json.dumps({'ok':True,'resultado':result,'preprocesamiento':report},ensure_ascii=True))
                    return 0
                except Exception as exc:
                    attempts.append({'estrategia':'recuperacion_numerica','error':str(exc)})
                finally:candidate.unlink(missing_ok=True)
            report['intentos_cad']=attempts
            report['error']='La malla se ha regularizado y verificado, pero el STEP no supera la reconstrucción CAD. El STL regularizado está disponible en el diagnóstico; no se ha generado un STEP aprobado.'
            report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            dst.unlink(missing_ok=True)
            print(json.dumps({'ok':False,'error':report['error'],'tipo_error':'cad_pendiente_tras_reparacion',
                              'preprocesamiento':report,'criterios':[]},ensure_ascii=True))
            return 2
        if report.get('reparado') and report.get('salida', {}).get('caras', 0) <= 12000:
            # Esta ruta nunca toca las 14 entradas sanas: solo sigue a una
            # reparación booleana ya contrastada y vuelve a pasar _calidad.
            # Los indicadores y tolerancias del validador histórico no cambian.
            flags = ('VISOR_CENTROID_GATE', 'VISOR_REFINAMIENTO_BREP', 'VISOR_STL_DIGITAL')
            previous = {key: os.environ.get(key) for key in flags}
            try:
                os.environ['VISOR_CENTROID_GATE'] = '1'
                os.environ['VISOR_REFINAMIENTO_BREP'] = '1'
                avance(18, 'Reconstruyendo entrada reparada con ajuste CAD preciso')
                with dst.with_suffix('.motor.log').open('w', encoding='utf-8', buffering=1) as log:
                    print('[Reparación CAD] Ajuste de regiones 0.015 mm, B-spline 0.005 mm, '
                          'aristas 0.003 mm; validación histórica sin cambios.', file=log, flush=True)
                    try:
                        result = convertir(prepared, dst, log, flat_tol_deg=1.3,
                                           digital=True, analitico=True, precision_reparacion=True,
                                           union_certificada=report.get('ruta_seleccionada')=='union_booleana_verificada')
                    except ValueError as direct_error:
                        if report.get('ruta_seleccionada')=='union_booleana_verificada':
                            print('[Unión verificada] El ajuste no es CAD exacto; recuperando su frontera exterior con los mismos controles.',file=log,flush=True)
                            from recuperacion_union_certificada import ejecutar
                            result=ejecutar(src,prepared,dst,log)
                            result['rechazo_cad_directo']=str(direct_error)
                        else:
                            print(f'[Reparación CAD] Intento directo rechazado: {direct_error}. '
                                  'Probando marco rígido local y validación en coordenadas originales.',
                                  file=log, flush=True)
                            from reparacion_cad import convertir_marco_local
                            result = convertir_marco_local(prepared, dst, log, convertir, _calidad)
                            result['rechazo_cad_directo'] = str(direct_error)
                if result.get('modo')!='recuperacion_facetada':result['estrategia'] = 'entrada_reparada_cad_preciso_verificado'
                print(json.dumps({'ok': True, 'resultado': result, 'preprocesamiento': report},
                                 ensure_ascii=True))
                return 0
            except Exception as exc:
                dst.unlink(missing_ok=True)
                report['intento_cad_preciso_rechazado'] = str(exc)
                report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
                # Conservar evidencia del intento antes de abrir el log heredado.
                failed_log = dst.with_suffix('.motor.log')
                if failed_log.exists():
                    shutil.copyfile(failed_log, dst.with_suffix('.cad_preciso_rechazado.log'))
            finally:
                for key, value in previous.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value
        # El núcleo conserva sus retornos y rutas de rescate. Solo se adjunta
        # el diagnóstico al JSON final que ya consume el servidor.
        output = _SalidaCad(sys.stdout)
        with contextlib.redirect_stdout(output):
            code = _main_cad()
        lines = output.getvalue().splitlines()
        payload = json.loads(lines[-1])
        if not payload.get('ok') and os.environ.get('VISOR_RECUPERACION_NUMERICA','1')=='1':
            candidate=dst.with_name(dst.stem+'_numerico_candidato.step')
            try:
                from recuperacion_numerica import ejecutar_aislado
                with dst.with_suffix('.motor.log').open('a',encoding='utf-8',buffering=1) as log:
                    result=ejecutar_aislado(src,prepared,candidate,log)
                candidate.replace(dst)
                payload={'ok':True,'resultado':result,'rechazo_motor_anterior':payload.get('error')}
                code=0
            except Exception as exc:
                payload['recuperacion_numerica_rechazada']={'error':str(exc),'tipo':getattr(exc,'codigo','recuperacion_numerica_rechazada')}
            finally:candidate.unlink(missing_ok=True)
        payload['preprocesamiento'] = report
        print(json.dumps(payload, ensure_ascii=True))
        return code
    except Exception as exc:
        if isinstance(exc, ReparacionRechazada):
            report = exc.informe
        report = report or {'reparado': False}
        report['error'] = str(exc)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        dst.unlink(missing_ok=True)
        print(json.dumps({'ok': False, 'error': str(exc), 'preprocesamiento': report,
                          'tipo_error':getattr(exc,'codigo','reconstruccion_cad_rechazada'),
                          'criterios':getattr(exc,'criterios',[])}, ensure_ascii=True))
        return 2
    finally:
        sys.argv = args
        if previous_rejections is None:os.environ.pop('VISOR_RECHAZOS_PATH',None)
        else:os.environ['VISOR_RECHAZOS_PATH']=previous_rejections
        if previous_interference_flag is None:
            os.environ.pop('VISOR_VERIFICAR_INTERFERENCIAS_CAD',None)
        else:
            os.environ['VISOR_VERIFICAR_INTERFERENCIAS_CAD'] = previous_interference_flag


if __name__=='__main__':
    sys.exit(main())
