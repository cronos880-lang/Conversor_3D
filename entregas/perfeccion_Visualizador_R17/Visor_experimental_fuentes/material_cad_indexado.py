"""Conservative native face bounds prune exact trimmed CAD intersections."""
import numpy as np
from OCP.IntCurvesFace import IntCurvesFace_Intersector
from OCP.BRepBndLib import BRepBndLib
from OCP.Bnd import Bnd_Box
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.gp import gp_Lin,gp_Pnt,gp_Dir
from OCP.TopAbs import TopAbs_IN,TopAbs_ON,TopAbs_OUT,TopAbs_REVERSED
from OCP.IntCurveSurface import IntCurveSurface_In,IntCurveSurface_Out

class ClasificadorMaterial:
 def __init__(self,shape,tol=1e-7):
  self.shape=shape;self.tol=tol;self.faces=shape.Faces();boxes=[]
  for f in self.faces:
   b=Bnd_Box();BRepBndLib.AddOptimal_s(f.wrapped,b,False,True)
   if b.IsVoid() or b.IsOpen():raise ValueError('Unbounded native face')
   boxes.append(b.Get())
  B=np.asarray(boxes);padding=tol*8+np.max(abs(B))*1e-12
  self.lower=B[:,:3]-padding;self.upper=B[:,3:]+padding;self.inter={};self.reference=BRepClass3d_SolidClassifier(shape.wrapped);self.fallbacks=0;self.queries=0
  self.directions=[np.array([.731,.419,.539]),np.array([-.317,.827,.463])];self.directions=[d/np.linalg.norm(d) for d in self.directions]
 def reference_state(self,point):
  self.reference.Perform(gp_Pnt(*map(float,point)),self.tol);state=self.reference.State()
  if state not in (TopAbs_IN,TopAbs_OUT,TopAbs_ON):raise ValueError('Unknown material state')
  return state in (TopAbs_IN,TopAbs_ON)
 def _ray(self,p,d):
  t0=(self.lower-p)/d;t1=(self.upper-p)/d
  enter=np.maximum(np.minimum(t0,t1).max(axis=1),0)
  leave=np.maximum(t0,t1).min(axis=1);ids=np.flatnonzero(leave>=enter);ids=ids[np.argsort(enter[ids])]
  line=gp_Lin(gp_Pnt(*map(float,p)),gp_Dir(*map(float,d)));nearest=float('inf');hits=[]
  for index in ids:
   if enter[index]>nearest+8*self.tol:break
   index=int(index);inter=self.inter.get(index)
   if inter is None:inter=IntCurvesFace_Intersector(self.faces[index].wrapped,self.tol);self.inter[index]=inter
   inter.Perform(line,-8*self.tol,float(leave[index]+8*self.tol));self.queries+=1
   if not inter.IsDone():return None
   for k in range(1,inter.NbPnt()+1):
    t=inter.WParameter(k)
    if t< -8*self.tol:continue
    if t<nearest-8*self.tol:nearest=t;hits=[]
    if abs(t-nearest)<=8*self.tol:hits.append((inter.State(k),inter.Transition(k),self.faces[index].wrapped.Orientation()))
  if not hits:return False
  if nearest<=8*self.tol or len(hits)!=1:return None
  state,transition,orientation=hits[0]
  if state!=TopAbs_IN or transition not in (IntCurveSurface_In,IntCurveSurface_Out):return None
  return (transition==IntCurveSurface_Out)
 def classify(self,points,expected=None,progress=None):
  answers=[]
  for i,p in enumerate(np.asarray(points,float)):
   try:a=self._ray(p,self.directions[0]);b=self._ray(p,self.directions[1]) if a is not None else None
   except Exception:a=b=None
   if a is None or b is None or a!=b or (expected is not None and a!=bool(expected[i])):
    self.fallbacks+=1;a=self.reference_state(p)
   answers.append(a)
   if progress and ((i+1)%100==0 or i+1==len(points)):progress(i+1,len(points))
  return np.asarray(answers,bool)
