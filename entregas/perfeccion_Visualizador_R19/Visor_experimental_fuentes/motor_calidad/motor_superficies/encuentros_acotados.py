"""Piloto: conciliación conjunta de normales y offsets con cotas fuente.

Cada plano se escribe n+t1*a+t2*b sin normalizar durante el solver. Las
restricciones sobre TODOS los vértices fuente son lineales y conservadoras,
pues su norma es >=1. Ninguna cota final de geometría se modifica.
"""
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix,hstack,eye,vstack,csr_matrix

def resolver(datos,points,keys,incidence,relations,families,limite=1e-4,nativas=None):
    nativas=nativas or {}
    points=np.asarray(points,float);keys=list(map(int,keys));lookup={v:i for i,v in enumerate(keys)};nv=len(keys);np_=len(datos);size=3*nv+3*np_
    centers=[];bases=[];normals=[];offsets=[];weights=np.ones(size)
    for j,item in enumerate(datos):
        P=np.asarray(item['points']);c=P.mean(0);n=np.asarray(item['n']);helper=np.eye(3)[np.argmin(abs(n))];t1=np.cross(n,helper);t1/=np.linalg.norm(t1);t2=np.cross(n,t1)
        centers.append(c);bases.append(np.column_stack([t1,t2]));normals.append(n);offsets.append(float(item['d']-n@c))
        width=max(float(np.linalg.norm(P-c,axis=1).max()),1.)
        weights[3*nv+3*j:3*nv+3*j+3]=np.array([1.,width,width])*np.sqrt(max(float(item['area']),.01))
    centers=np.array(centers);normals=np.array(normals);bases=np.array(bases);offsets=np.array(offsets)
    # Restricciones absolutas respecto de los vértices fuente originales.
    ui=[];uj=[];uv=[];ub=[]
    for j,item in enumerate(datos):
        P=np.asarray(item['points'])-centers[j];h=P@normals[j]-offsets[j];T=P@bases[j]
        for k in range(len(P)):
            for sign in (1.,-1.):
                row=len(ub);ui.extend([row]*3);uj.extend([3*nv+3*j,3*nv+3*j+1,3*nv+3*j+2]);uv.extend([sign*-1.,sign*T[k,0],sign*T[k,1]]);ub.append(limite-1e-8-sign*h[k])
    source=coo_matrix((uv,(ui,uj)),shape=(len(ub),size)).tocsr()
    abs_constraints=vstack([hstack([eye(size),-eye(size)]),hstack([-eye(size),-eye(size)]),hstack([source,csr_matrix(source.shape)])]).tocsr();upper=np.r_[np.zeros(2*size),ub]
    bounds=[(-.02,.02)]*(3*nv)+sum(([(-.001,.001),(-.05,.05),(-.05,.05)] for j in range(np_)),[])+[(0,None)]*size
    for v in nativas:
        if v not in lookup:raise ValueError('El anclaje nativo no tiene variable compartida')
        for k in range(3):bounds[3*lookup[v]+k]=(-.0025/np.sqrt(3),.0025/np.sqrt(3))
    def native_value(point,item):
        D=point-np.asarray(item['centro'])
        if item['tipo']=='cilindro':
            a=np.asarray(item['eje']);D-=a*(D@a)
        norm=np.linalg.norm(D)
        if norm<1e-12:raise ValueError('Anclaje en eje singular')
        return float(norm-item['radio']),D/norm
    x=np.zeros(size);history=[]
    for iteration in range(8):
        ri=[];ci=[];vv=[];rhs=[];res=[]
        for v in keys:
            vi=lookup[v];p=points[v];delta=x[3*vi:3*vi+3]
            for j in incidence[v]:
                start=3*nv+3*j;h,a,b=x[start:start+3];n=normals[j]+bases[j]@np.array([a,b]);D=p+delta-centers[j];F=float(n@D-offsets[j]-h);row=len(rhs)
                coeff=list(n)+[-1.,float(D@bases[j,:,0]),float(D@bases[j,:,1])];columns=list(range(3*vi,3*vi+3))+list(range(start,start+3));ri.extend([row]*6);ci.extend(columns);vv.extend(coeff);rhs.append(float(np.dot(coeff,x[columns])-F));res.append(F)
        for first,second,axis in relations:
            a=np.asarray(axis);helper=np.eye(3)[np.argmin(abs(a))];e=np.cross(a,helper);e/=np.linalg.norm(e);f=np.cross(a,e)
            for normal in (e,f):
                row=len(rhs);columns=list(range(3*lookup[first],3*lookup[first]+3))+list(range(3*lookup[second],3*lookup[second]+3));coeff=list(normal)+list(-normal);ri.extend([row]*6);ci.extend(columns);vv.extend(coeff);rhs.append(float(-normal@(points[first]-points[second])))
        for v,items in nativas.items():
            start=3*lookup[v];point=points[v]+x[start:start+3]
            for item in items:
                F,g=native_value(point,item);row=len(rhs);ri.extend([row]*3);ci.extend(range(start,start+3));vv.extend(g);rhs.append(float(g@x[start:start+3]-F))
        # Las paredes laterales compartidas mantienen su dirección de extrusión.
        for j,n in enumerate(normals):
            for axis in families:
                a=np.asarray(axis)
                if abs(n@a)>1e-8:continue
                coeff=bases[j].T@a
                if np.linalg.norm(coeff)<1e-10:continue
                row=len(rhs);ri.extend([row,row]);ci.extend([3*nv+3*j+1,3*nv+3*j+2]);vv.extend(coeff);rhs.append(float(-n@a))
        eq=coo_matrix((vv,(ri,ci)),shape=(len(rhs),size)).tocsr();matrix=hstack([eq,csr_matrix(eq.shape)]).tocsr()
        lp=linprog(np.r_[np.zeros(size),weights],A_ub=abs_constraints,b_ub=upper,A_eq=matrix,b_eq=np.array(rhs),bounds=bounds,method='highs',options={'dual_feasibility_tolerance':1e-9,'primal_feasibility_tolerance':1e-9,'time_limit':30.})
        if not lp.success:raise ValueError('No hay encuentro con normales y cotas fuente: '+lp.message)
        x=lp.x[:size];actual=[]
        for v in keys:
            delta=x[3*lookup[v]:3*lookup[v]+3]
            for j in incidence[v]:
                h,a,b=x[3*nv+3*j:3*nv+3*j+3];n=normals[j]+bases[j]@np.array([a,b]);actual.append(float(n@(points[v]+delta-centers[j])-offsets[j]-h))
        for v,items in nativas.items():
            point=points[v]+x[3*lookup[v]:3*lookup[v]+3]
            actual.extend(native_value(point,item)[0] for item in items)
        error=float(np.max(abs(np.array(actual)))) if actual else 0.;history.append(dict(iteracion=iteration,error_encuentro_mm=error));print('CONCILIACION NORMAL',history[-1],flush=True)
        if error<=1e-9:break
    if error>1e-9:raise ValueError('No converge el encuentro con normales medidas')
    result=[];source_max=0.
    for j,item in enumerate(datos):
        h,a,b=x[3*nv+3*j:3*nv+3*j+3];n=normals[j]+bases[j]@np.array([a,b]);d=offsets[j]+h+n@centers[j];length=np.linalg.norm(n);n/=length;d/=length
        err=float(abs(np.asarray(item['points'])@n-d).max());source_max=max(source_max,err)
        if err>limite:raise ValueError('La normal conciliada supera la cota fuente '+str(err))
        result.append(dict(n=n,d=float(d),error_mm=err))
    # Revisar todas las relaciones con la solución real, además del LP linealizado.
    for first,second,axis in relations:
        a=np.asarray(axis);D=points[first]+x[3*lookup[first]:3*lookup[first]+3]-points[second]-x[3*lookup[second]:3*lookup[second]+3]
        if np.linalg.norm(D-a*(D@a))>1e-9:raise ValueError('La conciliación no conserva una generatriz compartida')
    for v in nativas:
        if np.linalg.norm(x[3*lookup[v]:3*lookup[v]+3])>.0025:raise ValueError('El encuentro nativo excede la reserva de .0025 mm')
    canonical={int(v):(points[v]+x[3*lookup[v]:3*lookup[v]+3]).copy() for v in keys}
    if any(np.linalg.norm(point-points[v])>.003 for v,point in canonical.items()):raise ValueError('El grafo de esquinas excede .003 mm')
    return result,dict(puntos_canonicos=canonical,anclajes_nativos=len(nativas),iteraciones=history,max_fuente_mm=source_max,max_movimiento_coordenada_mm=float(abs(x[:3*nv]).max()) if nv else 0.)
