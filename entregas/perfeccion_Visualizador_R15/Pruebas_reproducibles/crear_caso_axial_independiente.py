from pathlib import Path
import cadquery as cq,trimesh,numpy as np,json,hashlib,io
W=Path(__file__).parent
# New geometry independent of the supplied conector: different dimensions,
# station heights, hole positions and topology; no borrowed STL vertices.
s=cq.Solid.makeCylinder(12,10)
s=s.fuse(cq.Solid.makeCylinder(17,2,cq.Vector(0,0,10)))
s=s.cut(cq.Solid.makeCylinder(8.5,12))
for x,y in [(14,0),(-14,0),(0,14),(0,-14)]:s=s.cut(cq.Solid.makeCylinder(1.2,2,cq.Vector(x,y,10)))
s=s.clean();vertices,faces=s.tessellate(.0001,angularTolerance=.015);mesh=trimesh.Trimesh([v.toTuple() for v in vertices],faces,process=True)
# Reproduce the same planar four-way subdivision after STL float32 roundtrip.
mesh=trimesh.load(io.BytesIO(mesh.export(file_type='stl')),file_type='stl',force='mesh',process=True)
vv,ff=trimesh.remesh.subdivide(mesh.vertices,mesh.faces);mesh=trimesh.Trimesh(vv,ff,process=False)
p=W/'brida_independiente_R15.stl';p.write_bytes(mesh.export(file_type='stl'));print('triangles',len(mesh.faces),'volume',mesh.volume,'nativefaces',len(s.Faces()),flush=True)
(W/'brida_independiente_ORIGEN.json').write_text(json.dumps(dict(procedencia='Generada por construcción CAD reproducible; independiente de los STL del usuario',triangulos=len(mesh.faces),volumen_STL=mesh.volume,volumen_CAD_origen=s.Volume(),sha256=hashlib.sha256(p.read_bytes()).hexdigest()),indent=2))
