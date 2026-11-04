"""Hipótesis CAD provisional desde el STL; nunca se entrega como resultado."""
from pathlib import Path
import copy,os
import cadquery as cq
from meshfit_step import export_step

def generar(source,result,mesh,destination):
 from meshfit_detect import detect
 from axial_recognition import inject_verified_cylinders
 records=[]
 for angle in (8.,1.3):
  try:
   if angle==8.:seed,work=copy.deepcopy(result),mesh.copy()
   else:
    seed,work=detect(str(source),angle_tol_deg=32.,rms_tol_rel=.01,flat_tol_deg=angle,scan_mode=False,mesh_input=mesh.copy())
    os.environ['VISOR_CENTROID_GATE']='1';os.environ['VISOR_REFINAMIENTO_BREP']='1';inject_verified_cylinders(seed,work)
   export_step(copy.deepcopy(seed),work.copy(),str(destination),organic=True,solid=True,organic_smooth=0.,ajuste_ia=False,require_solid=True,precision_reparacion=False)
   shape=cq.importers.importStep(str(destination)).val();error=100*abs(shape.Volume()/mesh.volume-1)
   if not 3<=len(shape.Faces())<=256 or error>.5:raise ValueError('La hipótesis no conserva volumen o excede 256 caras')
   print('SEMILLA FUENTE',angle,'caras',len(shape.Faces()),'volumen_error_pct',error,flush=True)
   return shape
  except Exception as exc:records.append(dict(segmentacion=angle,error=str(exc)))
 raise ValueError('No hay hipótesis compacta útil: '+str(records))
