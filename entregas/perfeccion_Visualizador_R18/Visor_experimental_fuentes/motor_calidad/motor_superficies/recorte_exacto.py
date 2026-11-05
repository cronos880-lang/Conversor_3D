"""Recortar curvas sin ajustar extremos B-spline a nudos próximos."""
from OCP.Geom import Geom_BSplineCurve,Geom_BezierCurve,Geom_TrimmedCurve
from OCP.GeomConvert import GeomConvert
from OCP.TColStd import TColStd_Array1OfReal
import numpy as np


def _recortar(curve,first,last):
    first,last=float(first),float(last)
    if last<=first:raise ValueError('Intervalo de recorte no creciente')
    if isinstance(curve,(Geom_BSplineCurve,Geom_BezierCurve)):
        result=(curve.Copy() if isinstance(curve,Geom_BSplineCurve) else GeomConvert.CurveToBSplineCurve_s(curve).Copy())
        result.Segment(first,last,0.)
        a,b=result.FirstParameter(),result.LastParameter()
        if a!=first or b!=last:
            # OCCT todavía puede igualar parámetros separados por una ULP.
            # Cambiar sólo la parametrización y medir el efecto físico real.
            knots=TColStd_Array1OfReal(1,result.NbKnots())
            for i in range(1,result.NbKnots()+1):
                value=first+(result.Knot(i)-a)*(last-first)/(b-a)
                knots.SetValue(i,first if i==1 else last if i==result.NbKnots() else float(value))
            result.SetKnots(knots)
        probes=np.unique(np.r_[np.linspace(first,last,65),[curve.Knot(i) for i in range(1,curve.NbKnots()+1) if first<curve.Knot(i)<last]]) if isinstance(curve,Geom_BSplineCurve) else np.linspace(first,last,65)
        if max(result.Value(float(t)).Distance(curve.Value(float(t))) for t in probes)>1e-10:
            raise ValueError('La parametrización del recorte no conserva la curva física')
    else:
        result=GeomConvert.CurveToBSplineCurve_s(Geom_TrimmedCurve(curve,first,last)).Copy()
    if max(result.Value(result.FirstParameter()).Distance(curve.Value(first)),
           result.Value(result.LastParameter()).Distance(curve.Value(last)))>1e-10:
        raise ValueError('El recorte no conserva los extremos físicos')
    return result


def recortar(curve,first,last):
    try:return _recortar(curve,first,last)
    except Exception as exc:
        import os,json,hashlib
        from pathlib import Path
        folder=os.environ.get('PILOTO_CORTES_DIR')
        if folder and isinstance(curve,Geom_BSplineCurve):
            row=dict(first=float(first),last=float(last),error=str(exc),grado=curve.Degree(),periodica=curve.IsPeriodic(),
                     polos=[curve.Pole(i).Coord() for i in range(1,curve.NbPoles()+1)],
                     pesos=[curve.Weight(i) for i in range(1,curve.NbPoles()+1)],
                     nudos=[curve.Knot(i) for i in range(1,curve.NbKnots()+1)],
                     multiplicidades=[curve.Multiplicity(i) for i in range(1,curve.NbKnots()+1)])
            text=json.dumps(row,indent=2);target=Path(folder);target.mkdir(parents=True,exist_ok=True)
            (target/('recorte_'+hashlib.sha256(text.encode()).hexdigest()[:12]+'.json')).write_text(text)
        raise
