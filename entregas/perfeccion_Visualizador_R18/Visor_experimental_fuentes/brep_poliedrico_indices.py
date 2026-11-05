"""B-Rep de facetas con vértices y aristas compartidos por índice."""
import numpy as np

def construir(mesh,*,unificar=True,proteger_micro=False,conservar_nodos=None,tolerancia_plana=1e-9,tolerancia_angular=1e-8,umbral_proteccion=1e-5):
 import cadquery as cq
 from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace,BRepBuilderAPI_MakeSolid
 from OCP.BRep import BRep_Builder
 from OCP.TopoDS import TopoDS,TopoDS_Shell,TopoDS_Vertex,TopoDS_Edge,TopoDS_Wire
 from OCP.gp import gp_Pnt,gp_Dir,gp_Pln
 from OCP.Geom import Geom_Line
 from OCP.TopAbs import TopAbs_FORWARD,TopAbs_REVERSED
 from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain
 import trimesh
 V,F=mesh.vertices,mesh.faces;groups=list(trimesh.graph.connected_components(mesh.face_adjacency,nodes=np.arange(len(F)),min_len=1));labels=np.empty(len(F),int)
 for gi,group in enumerate(groups):labels[group]=gi
 T=V[F];cross=np.cross(T[:,1]-T[:,0],T[:,2]-T[:,0]);areas=np.linalg.norm(cross,axis=1)
 if np.any(areas==0):raise ValueError('Hay facetas exactamente degeneradas')
 normals=cross/areas[:,None];builder=BRep_Builder();vertices=[];tol=1e-10
 for p in V:
  v=TopoDS_Vertex();builder.MakeVertex(v,gp_Pnt(*map(float,p)),tol);vertices.append(v)
 edges={};shells=[]
 for _ in groups:
  shell=TopoDS_Shell();builder.MakeShell(shell);shells.append(shell)
 for fi,face in enumerate(F):
  shell=shells[labels[fi]]
  wire=TopoDS_Wire();builder.MakeWire(wire)
  for a,b in zip(face,np.roll(face,-1)):
   key=tuple(sorted((int(a),int(b))))
   if key not in edges:
    p0,p1=V[list(key)];distance=float(np.linalg.norm(p1-p0));edge=TopoDS_Edge();curve=Geom_Line(gp_Pnt(*map(float,p0)),gp_Dir(*map(float,p1-p0)));builder.MakeEdge(edge,curve,tol);builder.Range(edge,0.,distance);va=TopoDS.Vertex_s(vertices[key[0]].Oriented(TopAbs_FORWARD));vb=TopoDS.Vertex_s(vertices[key[1]].Oriented(TopAbs_REVERSED));builder.Add(edge,va);builder.Add(edge,vb);builder.UpdateVertex(va,0.,edge,tol);builder.UpdateVertex(vb,distance,edge,tol);builder.SameParameter(edge,True);builder.SameRange(edge,True);edges[key]=edge
   builder.Add(wire,edges[key] if a<b else TopoDS.Edge_s(edges[key].Reversed()))
  wire.Closed(True);plane=gp_Pln(gp_Pnt(*map(float,V[face[0]])),gp_Dir(*map(float,normals[fi])));builder.Add(shell,BRepBuilderAPI_MakeFace(plane,wire,True).Face())
 maker=BRepBuilderAPI_MakeSolid()
 for shell in shells:shell.Closed(True);maker.Add(shell)
 shape=cq.Shape.cast(maker.Solid())
 if unificar:
  unify=ShapeUpgrade_UnifySameDomain(shape.wrapped,True,True,False);unify.SetLinearTolerance(tolerancia_plana);unify.SetAngularTolerance(tolerancia_angular)
  if proteger_micro:
   longest=np.linalg.norm(T-np.roll(T,-1,axis=1),axis=2).max(1);bad=areas/longest<umbral_proteccion
   for face in F[bad]:
    for a,b in zip(face,np.roll(face,-1)):
     key=tuple(sorted((int(a),int(b))));unify.KeepShape(edges[key]);unify.KeepShape(vertices[int(a)])
  if conservar_nodos is not None:
   keep=set(map(int,conservar_nodos))
   for key,edge in edges.items():
    if any(v in keep for v in key):unify.KeepShape(edge)
   for v in keep:unify.KeepShape(vertices[v])
  unify.Build();shape=cq.Shape.cast(unify.Shape())
 return shape
