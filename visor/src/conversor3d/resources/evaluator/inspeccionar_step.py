from pathlib import Path
import sys,json,collections
import cadquery as cq
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRep import BRep_Tool
source=Path(sys.argv[1]);report=Path(sys.argv[2]);d={'ok':False}
try:
 shape=cq.importers.importStep(str(source)).val()
 if not isinstance(shape,cq.Shape):raise ValueError('Sin forma CAD transferida')
 bounds=shape.BoundingBox();d.update(ok=True,solids=len(shape.Solids()),shells=len(shape.Shells()),faces=len(shape.Faces()),exact_valid=bool(BRepCheck_Analyzer(shape.wrapped,True,False,True).IsValid()),types=dict(collections.Counter(str(BRepAdaptor_Surface(f.wrapped).GetType()) for f in shape.Faces())),max_edge_tolerance_mm=max(BRep_Tool.Tolerance_s(e.wrapped) for e in shape.Edges()),volume_mm3=shape.Volume(),dimensions_mm=[bounds.xlen,bounds.ylen,bounds.zlen])
except Exception as e:d['error']=str(e)
report.write_text(json.dumps(d,indent=2));print(json.dumps(d))
