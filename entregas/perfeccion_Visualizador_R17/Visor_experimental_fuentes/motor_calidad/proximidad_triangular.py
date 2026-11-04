"""Proximidad a triángulos sin umbrales absolutos dependientes de la escala."""
import numpy as np

def baricentricas(triangles,points):
 T=np.asarray(triangles,float);P=np.asarray(points,float);u=T[:,1]-T[:,0];v=T[:,2]-T[:,0];w=P-T[:,0];n=np.cross(u,v);den=np.einsum('ij,ij->i',n,n)
 b=np.divide(np.einsum('ij,ij->i',np.cross(w,v),n),den,out=np.zeros(len(T)),where=den>0);c=np.divide(np.einsum('ij,ij->i',np.cross(u,w),n),den,out=np.zeros(len(T)),where=den>0)
 return np.c_[1-b-c,b,c]

def punto_mas_cercano(triangles,points):
 T=np.asarray(triangles,float);P=np.asarray(points,float);u=T[:,1]-T[:,0];v=T[:,2]-T[:,0];n=np.cross(u,v);den=np.einsum('ij,ij->i',n,n);h=np.divide(np.einsum('ij,ij->i',P-T[:,0],n),den,out=np.zeros(len(T)),where=den>0);plane=P-h[:,None]*n;bary=baricentricas(T,plane);inside=(den>0)&np.all(bary>=0,axis=1)
 starts=T;ends=np.roll(T,-1,axis=1);edges=ends-starts;dd=np.einsum('ijk,ijk->ij',edges,edges);ts=np.divide(np.einsum('ijk,ijk->ij',P[:,None,:]-starts,edges),dd,out=np.zeros_like(dd),where=dd>0);q=starts+np.clip(ts,0,1)[:,:,None]*edges;dist=np.sum((q-P[:,None,:])**2,axis=2);ix=np.argmin(dist,axis=1);answer=q[np.arange(len(T)),ix];answer[inside]=plane[inside];return answer
