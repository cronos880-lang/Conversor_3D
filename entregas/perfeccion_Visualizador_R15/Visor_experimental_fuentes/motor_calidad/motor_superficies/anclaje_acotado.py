"""Ajuste lineal de polos en un polígono INSCRITO en la cota euclídea previa."""
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import csr_matrix,coo_matrix,hstack,vstack,eye,block_diag

def resolver(basis,rhs,axis,limite=.003):
 axis=np.asarray(axis,float);helper=np.eye(3)[np.argmin(abs(axis))];e=np.cross(axis,helper);e/=np.linalg.norm(e);f=np.cross(axis,e)
 if np.linalg.norm(rhs,axis=1).max()>limite+1e-10:raise ValueError('Un objetivo requiere un movimiento mayor que la cota de polos: '+str(float(np.linalg.norm(rhs,axis=1).max())))
 n=basis.shape[1];A=block_diag([csr_matrix(basis)]*2);target=np.r_[rhs@e,rhs@f];angles=np.arange(32)*2*np.pi/32;row=np.repeat(np.arange(32*n),2);col=[];values=[]
 for j in range(n):
  for angle in angles:col.extend([j,n+j]);values.extend([np.cos(angle),np.sin(angle)])
 polygon=coo_matrix((values,(row,col)),shape=(32*n,2*n)).tocsr();Z=csr_matrix(polygon.shape);I=eye(2*n);constraints=vstack([hstack([I,-I]),hstack([-I,-I]),hstack([polygon,Z])]).tocsr();bounds=np.r_[np.zeros(4*n),np.full(32*n,(limite-1e-8)*np.cos(np.pi/32))]
 fit=linprog(np.r_[np.zeros(2*n),np.ones(2*n)],A_ub=constraints,b_ub=bounds,A_eq=hstack([A,csr_matrix(A.shape)]),b_eq=target,bounds=[(None,None)]*(2*n)+[(0,None)]*(2*n),method='highs',options={'primal_feasibility_tolerance':1e-9,'dual_feasibility_tolerance':1e-9,'time_limit':20.})
 if not fit.success:raise ValueError('No existe ajuste de polos dentro de .003 mm: '+fit.message)
 edits=np.outer(fit.x[:n],e)+np.outer(fit.x[n:2*n],f)
 if np.linalg.norm(edits,axis=1).max()>limite or np.linalg.norm(basis@edits-rhs,axis=1).max()>5e-8:raise ValueError('El ajuste acotado no supera la verificación independiente')
 return edits
