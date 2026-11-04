"""Source-supported planar sketches: shared endpoints, lines and native arcs."""
import numpy as np,cadquery as cq

def compact(P,tol=1e-8,mandatory=()):
 P=np.asarray(P,float)
 if np.linalg.norm(P[0]-P[-1])<1e-8:P=P[:-1]
 prev=np.roll(P,1,axis=0);nxt=np.roll(P,-1,axis=0);a=P-prev;b=nxt-P
 cr=abs(a[:,0]*b[:,1]-a[:,1]*b[:,0]);keep=cr>tol*np.maximum(np.linalg.norm(a,axis=1)+np.linalg.norm(b,axis=1),1e-30)
 for point in mandatory:keep[int(np.linalg.norm(P-point,axis=1).argmin())]=True
 P=P[keep]
 turn=np.linalg.norm(P-np.roll(P,1,axis=0),axis=1)
 # Start at strongest corner; circle-only profiles handled separately.
 aa=P-np.roll(P,1,axis=0);bb=np.roll(P,-1,axis=0)-P
 cos=np.sum(aa*bb,axis=1)/np.maximum(np.linalg.norm(aa,axis=1)*np.linalg.norm(bb,axis=1),1e-30)
 P=np.roll(P,-int(np.argmin(cos)),axis=0)
 return np.vstack([P,P[0]])

def circle(P):
 p=np.asarray(P,float);origin=p.mean(0);xy=p-origin
 x,y,k=np.linalg.lstsq(np.c_[2*xy,np.ones(len(p))],(xy*xy).sum(1),rcond=None)[0];c=origin+[x,y];r=np.sqrt(max(0,k+x*x+y*y));err=float(abs(np.linalg.norm(p-c,axis=1)-r).max())
 return c,float(r),err

def sketch(P,embed,tol=.00005,mandatory=()):
 P=compact(P,mandatory=mandatory);center,r,err=circle(P[:-1]);area=abs((P[:-1,0]*P[1:,1]-P[:-1,1]*P[1:,0]).sum()/2)
 radius=float(np.sqrt(area/np.pi));Q=P[:-1]-center;D=np.roll(Q,-1,axis=0)-Q;t=np.clip(-np.sum(Q*D,axis=1)/np.maximum(np.sum(D*D,axis=1),1e-30),0,1);rmin=np.linalg.norm(Q+t[:,None]*D,axis=1).min();rmax=np.linalg.norm(Q,axis=1).max()
 if len(Q)>=24 and max(abs(radius-rmin),abs(radius-rmax))<=.008:
  radius=float(np.sqrt(area/np.pi))
  # Embed establishes an orthonormal planar basis.
  o=np.asarray(embed(center));a=np.asarray(embed(center+[1,0]))-o;b=np.asarray(embed(center+[0,1]))-o
  wire=cq.Wire.makeCircle(radius,cq.Vector(*o),cq.Vector(*np.cross(a,b)))
  return wire,dict(type='circle',center=center.tolist(),radius=radius,nominal_radius=r,area=area,error=err)
 n=len(P)-1;edges=[];records=[];i=0
 critical=set([int(np.argmin(P[:-1,k])) for k in range(2)]+[int(np.argmax(P[:-1,k])) for k in range(2)])
 for point in mandatory:critical.add(int(np.linalg.norm(P[:-1]-point,axis=1).argmin()))
 while i<n:
  stop=min([v for v in critical if v>i]+[n]);best=(i+1,'line',None)
  for j in range(i+2,stop+1):
   Q=P[i:j+1];d=Q[-1]-Q[0];l=np.linalg.norm(d)
   if l<1e-10:break
   e=abs((Q[:,0]-Q[0,0])*d[1]-(Q[:,1]-Q[0,1])*d[0]).max()/l
   if e<tol:best=(j,'line',None);continue
   if j-i<3:continue
   A=Q[0];B=Q[len(Q)//2];C=Q[-1]
   mat=2*np.array([B-A,C-A]);rhs=np.array([B@B-A@A,C@C-A@A])
   if abs(np.linalg.det(mat))<1e-12:continue
   c=np.linalg.solve(mat,rhs);rr=np.linalg.norm(A-c)
   if rr>1e5:continue
   # Certify each entire source segment, including its closest point to
   # the circle centre. Vertex-only fitting can hide a large bowed arc.
   D=np.diff(Q,axis=0);A0=Q[:-1]-c
   t=np.clip(-np.sum(A0*D,axis=1)/np.maximum(np.sum(D*D,axis=1),1e-30),0,1)
   rmin=np.linalg.norm(A0+t[:,None]*D,axis=1).min()
   rmax=np.linalg.norm(Q-c,axis=1).max()
   residual=max(abs(rmin-rr),abs(rmax-rr))
   ang=np.unwrap(np.arctan2(Q[:,1]-c[1],Q[:,0]-c[0]));diff=np.diff(ang)
   if residual<tol and (np.all(diff>-1e-9) or np.all(diff<1e-9)) and abs(ang[-1]-ang[0])<np.pi*1.95:best=(j,'arc',B)
   elif j-i>8 and residual>tol*8:break
  j,kind,mid=best;v0=cq.Vector(*embed(P[i]));v1=cq.Vector(*embed(P[j]))
  edge=cq.Edge.makeLine(v0,v1) if kind=='line' else cq.Edge.makeThreePointArc(v0,cq.Vector(*embed(mid)),v1)
  edges.append(edge);records.append(dict(kind=kind,points=j-i+1));i=j
 wire=cq.Wire.assembleEdges(edges)
 if not wire.IsClosed():raise ValueError('Open source sketch')
 return wire,dict(type='arcs_lines',segments=records,area=area,points=len(P))
