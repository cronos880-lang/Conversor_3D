import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'motor_superficies'))
import numpy as np
from OCP.Geom import Geom_BSplineSurface
from OCP.TColgp import TColgp_Array2OfPnt
from OCP.TColStd import TColStd_Array1OfReal,TColStd_Array1OfInteger
from OCP.gp import gp_Pnt
from planos_canonicos import plano_demostrado

def superficie(bump=0.):
    points=TColgp_Array2OfPnt(1,4,1,4)
    for i in range(1,5):
        for j in range(1,5):points.SetValue(i,j,gp_Pnt(i/3,j/3,(i+2*j)/30+(bump if i==j==2 else 0)))
    knots=TColStd_Array1OfReal(1,2);knots.SetValue(1,0.);knots.SetValue(2,1.)
    mult=TColStd_Array1OfInteger(1,2);mult.SetValue(1,4);mult.SetValue(2,4)
    return Geom_BSplineSurface(points,knots,knots,mult,mult,3,3)

def test_plano_canonico_conserva_toda_la_superficie_inclinada():
    source=superficie();before=np.array([source.Pole(i,j).Coord() for i in range(1,5) for j in range(1,5)])
    plane=plano_demostrado(source)
    assert plane is not None
    for u in np.linspace(0,1,23):
        for v in np.linspace(0,1,23):assert abs(plane.Pln().Distance(source.Value(float(u),float(v))))<1e-10
    assert np.array_equal(before,np.array([source.Pole(i,j).Coord() for i in range(1,5) for j in range(1,5)]))

def test_no_aplana_una_superficie_curva_con_contorno_plano():
    source=superficie(.001)
    assert plano_demostrado(source) is None
    # Toda la frontera coincide con el plano; el abombamiento es interior.
    plane=plano_demostrado(superficie())
    for t in np.linspace(0,1,25):
        for u,v in [(0,t),(1,t),(t,0),(t,1)]:assert plane.Pln().Distance(source.Value(float(u),float(v)))<1e-10
    assert plane.Pln().Distance(source.Value(.5,.5))>1e-5
