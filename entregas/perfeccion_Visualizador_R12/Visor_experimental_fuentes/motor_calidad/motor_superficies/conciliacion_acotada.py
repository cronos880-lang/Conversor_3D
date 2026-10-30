"""Encuentros exactos con intervalos fuente; factibilidad y movimiento L1."""
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import csr_matrix,hstack,vstack,eye

def resolver(matrix,rhs,lower,upper):
 matrix,rhs,lower,upper=map(np.asarray,(matrix,rhs,lower,upper))
 if np.any(lower>upper):raise ValueError('Intervalos geométricos incompatibles')
 original=np.linalg.lstsq(matrix,rhs,rcond=1e-11)[0]
 if np.all(original>=lower) and np.all(original<=upper) and (not len(rhs) or abs(matrix@original-rhs).max()<=1e-9):return original,0
 n=matrix.shape[1];A=csr_matrix(matrix);zeros=csr_matrix(A.shape)
 constraints=vstack([hstack([eye(n),-eye(n)]),hstack([-eye(n),-eye(n)])]).tocsr()
 result=linprog(np.r_[np.zeros(n),np.ones(n)],A_ub=constraints,b_ub=np.zeros(2*n),A_eq=hstack([A,zeros]).tocsr(),b_eq=rhs,bounds=list(zip(lower,upper))+[(0,None)]*n,method='highs',options={'dual_feasibility_tolerance':1e-9,'primal_feasibility_tolerance':1e-9,'time_limit':30.})
 if not result.success:raise ValueError('No hay encuentro exacto con cotas fuente: '+result.message)
 answer=np.minimum(upper,np.maximum(lower,result.x[:n]))
 residual=float(abs(matrix@answer-rhs).max()) if len(rhs) else 0.
 if residual>1e-9:raise ValueError(f'La solución acotada no es un encuentro CAD exacto: {residual}')
 active=int(np.count_nonzero(np.isclose(answer,lower,atol=1e-12,rtol=0)|np.isclose(answer,upper,atol=1e-12,rtol=0)))
 return answer,active
