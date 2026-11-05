from pathlib import Path
import json,hashlib,numpy as np,trimesh,cadquery as cq
from OCP.gp import gp_Trsf
W=Path(__file__).parent;out=W/'controles_independientes';out.mkdir(exist_ok=True);rows=[]
def guardar(shape,name,description,rotate=False):
 if rotate:
  T=trimesh.transformations.rotation_matrix(.43,[1,2,-3]);T[:3,3]=[13,-9,21];tr=gp_Trsf();tr.SetValues(*map(float,T[:3].ravel()));shape=shape.transformShape(cq.Matrix(tr))
 directory=out/name;directory.mkdir(exist_ok=True);cq.exporters.export(shape,str(directory/'referencia_CAD.step'));V,F=shape.copy().tessellate(.0005,angularTolerance=.035);mesh=trimesh.Trimesh([v.toTuple()for v in V],F,process=True);p=directory/'entrada.stl';p.write_bytes(mesh.export(file_type='stl'));rows.append(dict(id=name,source=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),modelo=description,perfil='precision',euler=int(mesh.euler_number),caras=len(mesh.faces),volumen_CAD=shape.Volume()));print(name,mesh.euler_number,len(mesh.faces),flush=True)
guardar(cq.Solid.makeCylinder(6,3),'disco_macizo','CAD independiente: disco macizo, radio6 y altura3')
shape=cq.Solid.makeCylinder(6,9).cut(cq.Solid.makeBox(2,2,6,cq.Vector(-1,-1,3))).cut(cq.Solid.makeBox(1.2,.8,.12,cq.Vector(2.5,-.4,0))).clean();guardar(shape,'cilindro_vaciado_profundo_oblicuo','CAD independiente: cilindro, cavidad cuadrada profunda y rebaje inferior0.12; giro/traslación',True)
for count in [2,4]:
 shape=cq.Solid.makeCylinder(6,10).cut(cq.Solid.makeCylinder(3,10))
 for k in range(count):
  angle=k*360/count;slot=cq.Solid.makeBox(4,1.6,10.5 if k%2==0 else 8.5,cq.Vector(5,-.8,0)).rotate((0,0,0),(0,0,1),angle);shape=shape.cut(slot)
 for k in range(count):
  points=[cq.Vector(x,-.8,z)for x,z in [(5,0),(9,0),(9,3),(5,10)]];fin=cq.Solid.extrudeLinear(cq.Wire.makePolygon(points,close=True),[],cq.Vector(0,1.6,0)).rotate((0,0,0),(0,0,1),k*360/count);shape=shape.fuse(fin)
 shape=shape.clean();guardar(shape,f'casquillo_refuerzos_{count}'+('_oblicuo'if count==2 else''),'CAD independiente: casquillo con'+str(count)+'refuerzos y vaciados abiertos/cubiertos sobre techos inclinados; radios6/3, altura10',count==2)
(W/'CONTROLES_INDEPENDIENTES.json').write_text(json.dumps(rows,indent=2))
