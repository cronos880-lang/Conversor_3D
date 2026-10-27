"""Curvas2D con el parámetro de la curva3D y verificación numérica completa.

No mueve curvas3D, superficies ni tolerancias de aristas. Una proyección que no
supera el control se rechaza, aunque algunas muestras parezcan coincidir.
"""
import numpy as np
from OCP.gp import gp_Pnt2d,gp_Vec2d
from OCP.Geom2d import Geom2d_TrimmedCurve,Geom2d_BSplineCurve
from OCP.Geom2dConvert import Geom2dConvert
from OCP.Geom import Geom_BSplineSurface
from OCP.GeomAPI import GeomAPI_ProjectPointOnCurve
from OCP.ShapeAnalysis import ShapeAnalysis_Surface
from OCP.Geom2dAPI import Geom2dAPI_Interpolate
from OCP.TColgp import TColgp_HArray1OfPnt2d
from OCP.TColgp import TColgp_Array1OfPnt2d
from OCP.TColStd import TColStd_HArray1OfReal,TColStd_Array1OfReal,TColStd_Array1OfInteger
from OCP.GeomAdaptor import GeomAdaptor_Curve,GeomAdaptor_Surface
from OCP.Geom2dAdaptor import Geom2dAdaptor_Curve
from OCP.Adaptor3d import Adaptor3d_CurveOnSurface
from OCP.GeomLib import GeomLib_CheckCurveOnSurface

LIMITE_PARAMETRICO_MM=5e-8

def _error(curve,uv,surface,first,last):
    checker=GeomLib_CheckCurveOnSurface(GeomAdaptor_Curve(curve,first,last),1e-10)
    checker.SetParallel(False);checker.Perform(Adaptor3d_CurveOnSurface(
        Geom2dAdaptor_Curve(uv,first,last),GeomAdaptor_Surface(surface)))
    if not checker.IsDone():return float('inf')
    knots=[first,last]
    for obj in (curve,uv):
        if hasattr(obj,'NbKnots'):
            knots.extend(obj.Knot(i) for i in range(1,obj.NbKnots()+1) if first<obj.Knot(i)<last)
    knots=np.unique(knots);maximum=float(checker.MaxDistance())
    for a,b in zip(knots[:-1],knots[1:]):
        for t in np.linspace(a,b,9):
            p=uv.Value(float(t));maximum=max(maximum,curve.Value(float(t)).Distance(surface.Value(p.X(),p.Y())))
    return maximum

def _lineal_uv(first,last,start,end):
    points=TColgp_HArray1OfPnt2d(1,2);params=TColStd_HArray1OfReal(1,2)
    points.SetValue(1,gp_Pnt2d(*map(float,start)));points.SetValue(2,gp_Pnt2d(*map(float,end)))
    params.SetValue(1,first);params.SetValue(2,last)
    fit=Geom2dAPI_Interpolate(points,params,False,1e-12);fit.Perform()
    return fit.Curve()

def _unir_sin_reparametrizar(parts,surface):
    degree=max(p.Degree() for p in parts);parts=[p.Copy() for p in parts]
    for p in parts:p.IncreaseDegree(degree)
    poles=[];weights=[];knots=[];multiplicities=[]
    for index,part in enumerate(parts):
        if index:
            previous=poles[-1];current=part.Pole(1);shift=[0.,0.]
            for dim,periodic in [(0,surface.IsUPeriodic()),(1,surface.IsVPeriodic())]:
                if periodic:
                    period=surface.UPeriod() if dim==0 else surface.VPeriod()
                    shift[dim]=round((previous.Coord()[dim]-current.Coord()[dim])/period)*period
            if any(shift):part.Translate(gp_Vec2d(*shift))
            if part.Pole(1).Distance(previous)>1e-8:raise ValueError('Las curvasUV no comparten el extremo paramétrico.')
            factor=weights[-1]/part.Weight(1);multiplicities[-1]=degree
        else:factor=1.
        for j in range(1+int(index>0),part.NbPoles()+1):
            poles.append(part.Pole(j));weights.append(part.Weight(j)*factor)
        for j in range(1+int(index>0),part.NbKnots()+1):
            knots.append(part.Knot(j));multiplicities.append(part.Multiplicity(j))
    P=TColgp_Array1OfPnt2d(1,len(poles));W=TColStd_Array1OfReal(1,len(weights))
    K=TColStd_Array1OfReal(1,len(knots));M=TColStd_Array1OfInteger(1,len(knots))
    for i,(p,w) in enumerate(zip(poles,weights)):P.SetValue(i+1,p);W.SetValue(i+1,w)
    for i,(k,m) in enumerate(zip(knots,multiplicities)):K.SetValue(i+1,k);M.SetValue(i+1,m)
    return Geom2d_BSplineCurve(P,W,K,M,degree,False)

def _iso_comun(curve,first,last,surface):
    if not isinstance(surface,Geom_BSplineSurface):return None
    u0,u1,v0,v1=surface.Bounds()
    possibilities=[(surface.UIso(u0),0,u0,v0,v1),(surface.UIso(u1),0,u1,v0,v1),
                   (surface.VIso(v0),1,v0,u0,u1),(surface.VIso(v1),1,v1,u0,u1)]
    best=None
    for iso,constant,value,lo,hi in possibilities:
        for start,end in [(lo,hi),(hi,lo)]:
            maximum=max(curve.Value(float(t)).Distance(iso.Value(float(start+(end-start)*(t-first)/(last-first))))
                        for t in np.linspace(first,last,17))
            if maximum<1e-10:return iso,constant,value,lo,hi
    for iso,constant,value,lo,hi in possibilities:
        try:probes=[GeomAPI_ProjectPointOnCurve(curve.Value(float(t)),iso,lo,hi) for t in np.linspace(first,last,17)]
        except Exception:continue
        if any(p.NbPoints()==0 for p in probes):continue
        maximum=max(p.LowerDistance() for p in probes)
        if maximum<1e-8 and (best is None or maximum<best[0]):best=(maximum,iso,constant,value,lo,hi)
    return best[1:] if best else None

def crear_pcurva(curve,first,last,surface):
    iso=_iso_comun(curve,first,last,surface);sas=ShapeAnalysis_Surface(surface)
    c3=GeomAdaptor_Curve(curve,first,last);s3=GeomAdaptor_Surface(surface)
    if iso is not None:
        geometry,dim,value,lo,hi=iso
        for start,end in [(lo,hi),(hi,lo)]:
            a,b=((value,start),(value,end)) if dim==0 else ((start,value),(end,value))
            uv=_lineal_uv(first,last,a,b)
            mismatch=0.
            for t in np.linspace(first,last,9):
                point=uv.Value(float(t));mismatch=max(mismatch,curve.Value(float(t)).Distance(surface.Value(point.X(),point.Y())))
            if mismatch>LIMITE_PARAMETRICO_MM:continue
            error=_error(curve,uv,surface,first,last)
            if error<=LIMITE_PARAMETRICO_MM:
                return uv,{'max_desacuerdo_mm':error,'puntos_parametricos':2,'isoparametrica':True,
                           'geometria3D_modificada':False,'tolerancia_modificada':False}
    if iso is None:
        from OCP.GeomProjLib import GeomProjLib
        uv=GeomProjLib.Curve2d_s(curve,first,last,surface,1e-10)
        if uv is not None:
            check=GeomLib_CheckCurveOnSurface(c3,1e-10);check.SetParallel(False)
            check.Perform(Adaptor3d_CurveOnSurface(Geom2dAdaptor_Curve(uv,first,last),s3))
            error=_error(curve,uv,surface,first,last)
            if error<=LIMITE_PARAMETRICO_MM:
                return uv,{'max_desacuerdo_mm':error,'puntos_parametricos':0,
                           'isoparametrica':False,'geometria3D_modificada':False,'tolerancia_modificada':False}
    if hasattr(curve,'NbKnots'):
        epsilon=1e-12*max(1.,abs(last-first))
        breaks=[first]+[curve.Knot(i) for i in range(1,curve.NbKnots()+1)
                       if first+epsilon<curve.Knot(i)<last-epsilon and curve.Multiplicity(i)>=curve.Degree()]+[last]
        if len(breaks)>2:
            parts=[]
            for lo,hi in zip(breaks[:-1],breaks[1:]):
                part,_=crear_pcurva(curve,float(lo),float(hi),surface)
                parts.append(Geom2dConvert.CurveToBSplineCurve_s(Geom2d_TrimmedCurve(part,float(lo),float(hi))))
            uv=_unir_sin_reparametrizar(parts,surface);error=_error(curve,uv,surface,first,last)
            if error>LIMITE_PARAMETRICO_MM:raise ValueError('La uniónUV por esquinas no supera la verificación.')
            return uv,{'max_desacuerdo_mm':error,'fragmentos_c0':len(parts),'isoparametrica':bool(iso),
                       'geometria3D_modificada':False,'tolerancia_modificada':False}
    last_error=None
    for count in (17,33,65,129,257,513):
        parameters=np.linspace(first,last,count);points=[]
        for t in parameters:
            p=curve.Value(float(t))
            if iso:
                geometry,dim,value,lo,hi=iso
                projection=GeomAPI_ProjectPointOnCurve(p,geometry,lo,hi)
                if projection.NbPoints()==0:raise ValueError('No se verifica el contorno isoparamétrico.')
                variable=projection.LowerDistanceParameter()
                points.append((value,variable) if dim==0 else (variable,value))
            else:
                uv=sas.ValueOfUV(p,1e-10);points.append(uv.Coord())
        points=np.asarray(points)
        for dim,periodic in [(0,surface.IsUPeriodic()),(1,surface.IsVPeriodic())]:
            if periodic:points[:,dim]=np.unwrap(points[:,dim],period=surface.UPeriod() if dim==0 else surface.VPeriod())
        array=TColgp_HArray1OfPnt2d(1,count);params=TColStd_HArray1OfReal(1,count)
        for i,(p,t) in enumerate(zip(points,parameters)):
            array.SetValue(i+1,gp_Pnt2d(*map(float,p)));params.SetValue(i+1,float(t))
        interpolate=Geom2dAPI_Interpolate(array,params,False,1e-12);interpolate.Perform()
        if not interpolate.IsDone():raise ValueError('La parametrización no converge.')
        uv=interpolate.Curve();check=GeomLib_CheckCurveOnSurface(c3,1e-10);check.SetParallel(False)
        check.Perform(Adaptor3d_CurveOnSurface(Geom2dAdaptor_Curve(uv,first,last),s3))
        if not check.IsDone():raise ValueError('No se comprueba el desacuerdo paramétrico.')
        last_error=_error(curve,uv,surface,first,last)
        if last_error<=LIMITE_PARAMETRICO_MM:
            return uv,{'max_desacuerdo_mm':last_error,'puntos_parametricos':count,'isoparametrica':bool(iso),
                       'geometria3D_modificada':False,'tolerancia_modificada':False}
    raise ValueError(f'La curva2D no representa la curva3D sobre la superficie: {last_error:.12g} mm.')
