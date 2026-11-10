"""Parche B-spline con recorte triangular y tres contornos compuestos.

El dominio es regular (u,v>=0, u+v<=1): no se colapsa un lado a un ápice.
Las restricciones de cada tramo se imponen a su grado completo, incluida
la diagonal tensorial; después se verifica toda la curva UV/3D con OCC.
"""
from recorte_exacto import recortar
import numpy as np
from scipy.interpolate import BSpline
from scipy.linalg import lstsq
from OCP.Geom import Geom_TrimmedCurve,Geom_BSplineSurface
from OCP.GeomConvert import GeomConvert
from OCP.TColgp import TColgp_Array2OfPnt
from OCP.TColStd import TColStd_Array1OfReal,TColStd_Array1OfInteger
from OCP.gp import gp_Pnt


def _knots(curve,first,last):
    return [(float((curve.Knot(i)-first)/(last-first)),curve.Degree()-curve.Multiplicity(i))
            for i in range(1,curve.NbKnots()+1) if first<curve.Knot(i)<last]

def _axis(conditions,degree):
    data={0.:degree+1,1.:degree+1}
    for t,continuity in conditions:
        if not 1e-14<t<1-1e-14:continue
        # Mantener al menos la continuidad que exige la curva correspondiente.
        data[t]=max(data.get(t,1),degree-max(0,continuity))
    knots=np.array(sorted(data));mult=np.array([data[t] for t in knots],int)
    return knots,mult,np.repeat(knots,mult)

def _samples(breaks,degree):
    # Nodos interiores Chebyshev y extremos en CADA tramo polinómico.
    nodes=(1-np.cos(np.linspace(0,np.pi,degree+1)))*.5
    values=[]
    for a,b in zip(breaks[:-1],breaks[1:]):values.extend(a+(b-a)*nodes)
    return np.unique(np.asarray(values))

def construir(edges,anchor,*,anclaje_geometrico=False):
    curves=[recortar(c,float(a),float(b)) for c,a,b in edges]
    if len(curves)!=3:raise ValueError('Se requieren tres contornos')
    if any(c.IsRational() for c in curves):raise ValueError('El parche regular compuesto aún requiere contornos polinómicos')
    degree=max(3,max(c.Degree() for c in curves))
    if degree>9:raise ValueError('El grado del contorno excede el presupuesto')
    ends=[np.array(c.Value(c.FirstParameter()).Coord()) for c in curves]
    for i,c in enumerate(curves):
        if c.Value(c.LastParameter()).Distance(gp_Pnt(*ends[(i+1)%3]))>1e-10:raise ValueError('Los contornos compuestos no comparten las esquinas')
    A,B,C=ends
    if np.linalg.norm(np.cross(B-A,C-A))<1e-14:raise ValueError('El dominio triangular es degenerado')
    descriptions=[_knots(c,c.FirstParameter(),c.LastParameter()) for c in curves]
    # U conserva el primer contorno; V conserva el tercero y el segundo diagonal.
    diagonal=[(1-t,k) for t,k in descriptions[0]]+descriptions[1]+[(1-t,k) for t,k in descriptions[2]]
    ku,mu,tu=_axis([(1-t,k) for t,k in diagonal],degree)
    kv,mv,tv=_axis(diagonal,degree)
    nu,nv=len(tu)-degree-1,len(tv)-degree-1
    if nu*nv>1024:raise ValueError('El parche compuesto excede 1024 polos')
    def basis(u,v):
        bu=BSpline.design_matrix(np.array([u]),tu,degree).toarray()[0]
        bv=BSpline.design_matrix(np.array([v]),tv,degree).toarray()[0]
        return np.outer(bu,bv).ravel()
    rows=[];targets=[]
    for index,c in enumerate(curves):
        own=np.array([0.,*[t for t,k in descriptions[index]],1.])
        breaks=(np.unique(np.r_[own,ku]) if index==0 else
                np.unique(np.r_[own,1-ku,kv]) if index==1 else
                np.unique(np.r_[own,1-kv]))
        count=2*degree if index==1 else degree
        for t in _samples(breaks,count):
            u,v=((t,0.),(1-t,t),(0.,1-t))[index]
            parameter=c.FirstParameter()+t*(c.LastParameter()-c.FirstParameter())
            rows.append(basis(float(u),float(v)));targets.append(np.array(c.Value(float(parameter)).Coord())-A)
    if not anclaje_geometrico:
        rows.append(basis(1/3,1/3));targets.append(np.asarray(anchor)-A)
    matrix=np.array(rows);targets=np.array(targets)
    gu=np.array([np.mean(tu[i+1:i+degree+1]) for i in range(nu)])
    gv=np.array([np.mean(tv[i+1:i+degree+1]) for i in range(nv)])
    baseline=np.array([u*(B-A)+v*(C-A) for u in gu for v in gv])
    edits=lstsq(matrix,targets-matrix@baseline,cond=1e-12,lapack_driver='gelsd')[0]
    residual=float(np.linalg.norm(matrix@(baseline+edits)-targets,axis=1).max())
    if residual>1e-9:raise ValueError('No se conservan los contornos compuestos: '+str(residual))
    maximum=float(np.linalg.norm(edits,axis=1).max())
    if maximum>.012:raise ValueError('La corrección de polos del parche excede .012 mm: '+str(maximum))
    P=TColgp_Array2OfPnt(1,nu,1,nv);coordinates=(baseline+edits+A).reshape(nu,nv,3)
    for i in range(nu):
        for j in range(nv):P.SetValue(i+1,j+1,gp_Pnt(*map(float,coordinates[i,j])))
    def arrays(knots,multiplicities):
        K=TColStd_Array1OfReal(1,len(knots));M=TColStd_Array1OfInteger(1,len(knots))
        for i,(k,m) in enumerate(zip(knots,multiplicities),1):K.SetValue(i,float(k));M.SetValue(i,int(m))
        return K,M
    KU,MU=arrays(ku,mu);KV,MV=arrays(kv,mv)
    surface=Geom_BSplineSurface(P,KU,KV,MU,MV,degree,degree,False,False)
    from pcurvas_compartidas import _lineal_uv,_error
    for index,(curve,first,last) in enumerate(edges):
        start,end=[((0.,0.),(1.,0.)),((1.,0.),(0.,1.)),((0.,1.),(0.,0.))][index]
        uv=_lineal_uv(first,last,start,end);error=_error(curve,uv,surface,first,last)
        if error>5e-8:raise ValueError('La frontera compuesta no supera el control UV/3D: '+str(error))
    if anclaje_geometrico:
        from parches_triangulares import certificar_anclaje_geometrico
        certificar_anclaje_geometrico(surface,edges,anchor)
    elif surface.Value(1/3,1/3).Distance(gp_Pnt(*map(float,anchor)))>1e-8:raise ValueError('No se conserva el anclaje interior')
    print('PARCHE COMPUESTO REGULAR',dict(polos=[nu,nv],grado=degree,max_correccion_mm=maximum,residual_restricciones_mm=residual),flush=True)
    return surface
