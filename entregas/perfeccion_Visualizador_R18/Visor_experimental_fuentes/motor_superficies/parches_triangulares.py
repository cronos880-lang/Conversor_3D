"""Parches polinómicos triangulares con dominio UV regular, sin ápice colapsado."""
from math import comb,factorial
import numpy as np
from numpy.polynomial import Chebyshev,Polynomial
from OCP.Geom import Geom_BezierCurve,Geom_BezierSurface
from OCP.GeomConvert import GeomConvert
from OCP.Geom import Geom_TrimmedCurve
from OCP.TColgp import TColgp_Array1OfPnt,TColgp_Array2OfPnt
from OCP.gp import gp_Pnt,gp_Vec

def bezier_local(curve,first,last,start,end):
    origin=np.asarray(start,float);end=np.asarray(end,float)
    for degree in (3,5,7,9):
        s=(1+np.cos((np.arange(33)+.5)*np.pi/33))/2
        values=np.array([curve.Value(float(first+(last-first)*t)).Coord() for t in s])-origin
        coefficients=[]
        for dimension in range(3):
            p=Chebyshev.fit(s,values[:,dimension],degree,domain=[0,1]).convert(kind=Polynomial)
            a=np.zeros(degree+1);a[:len(p.coef)]=p.coef
            delta0=-Polynomial(a)(0.);delta1=(end-origin)[dimension]-Polynomial(a)(1.)
            a[0]+=delta0;a[1]+=delta1-delta0;coefficients.append(a)
        coefficients=np.asarray(coefficients).T;poles=TColgp_Array1OfPnt(1,degree+1)
        for k in range(degree+1):
            point=origin+sum(coefficients[j]*comb(k,j)/comb(degree,j) for j in range(k+1))
            poles.SetValue(k+1,gp_Pnt(*map(float,point)))
        result=Geom_BezierCurve(poles)
        probes=list(np.linspace(0,1,257))
        if hasattr(curve,'NbKnots'):
            knots=[first]+[curve.Knot(i) for i in range(1,curve.NbKnots()+1) if first<curve.Knot(i)<last]+[last]
            probes.extend((t-first)/(last-first) for a,b in zip(knots[:-1],knots[1:]) for t in np.linspace(a,b,9))
        error=max(result.Value(float(t)).Distance(curve.Value(float(first+(last-first)*t))) for t in probes)
        if error<=4e-8:return result,0.,1.
    raise ValueError('El contorno no admite un tramo de Bézier local dentro del presupuesto numérico.')

def superficie_triangular(edges,anchor):
    curves=[GeomConvert.CurveToBSplineCurve_s(Geom_TrimmedCurve(c,a,b)) for c,a,b in edges]
    if any(c.NbKnots()!=2 or c.IsRational() for c in curves):raise ValueError('La frontera triangular debe ser polinómica de un tramo.')
    degree=max(c.Degree() for c in curves)
    for c in curves:c.IncreaseDegree(degree)
    P=[np.array([c.Pole(i).Coord() for i in range(1,c.NbPoles()+1)]) for c in curves]
    if any(np.linalg.norm(P[i][-1]-P[(i+1)%3][0])>1e-10 for i in range(3)):
        raise ValueError('Los contornos triangulares no comparten esquinas exactas.')
    A,B,C=P[0][0],P[0][-1],P[1][-1];controls={}
    for i in range(degree+1):
        for j in range(degree+1-i):
            k=degree-i-j;controls[i,j,k]=(i*A+j*B+k*C)/degree
    for r in range(degree+1):
        controls[degree-r,r,0]=P[0][r];controls[0,degree-r,r]=P[1][r];controls[r,0,degree-r]=P[2][r]
    center=np.zeros(3);interior_weight=0.
    for (i,j,k),point in controls.items():
        weight=factorial(degree)/factorial(i)/factorial(j)/factorial(k)/3**degree
        center+=weight*point
        if min(i,j,k)>0:interior_weight+=weight
    delta=(np.asarray(anchor)-center)/interior_weight
    if np.linalg.norm(delta)>.012:raise ValueError('La corrección interior del parche excede el movimiento previsto.')
    for key in controls:
        if min(key)>0:controls[key]=controls[key]+delta
    power=np.zeros((degree+1,degree+1,3))
    for (i,j,k),point in controls.items():
        for a in range(i+1):
            for b in range(i-a+1):
                coefficient=factorial(degree)/factorial(j)/factorial(k)/factorial(a)/factorial(b)/factorial(i-a-b)*(-1)**(a+b)
                power[j+a,k+b]+=coefficient*(point-A)
    poles=TColgp_Array2OfPnt(1,degree+1,1,degree+1)
    for r in range(degree+1):
        for s in range(degree+1):
            point=A.copy()
            for a in range(r+1):
                for b in range(s+1):point+=power[a,b]*comb(r,a)/comb(degree,a)*comb(s,b)/comb(degree,b)
            poles.SetValue(r+1,s+1,gp_Pnt(*map(float,point)))
    surface=Geom_BezierSurface(poles)
    for index,(curve,first,last) in enumerate(edges):
        for s in np.linspace(0,1,129):
            uv=((s,0),(1-s,s),(0,1-s))[index]
            if surface.Value(*map(float,uv)).Distance(curve.Value(float(first+(last-first)*s)))>5e-8:
                raise ValueError('El parche triangular no conserva uno de sus contornos.')
    if surface.Value(1/3,1/3).Distance(gp_Pnt(*map(float,anchor)))>1e-8:raise ValueError('El parche no conserva el anclaje interior.')
    return surface
