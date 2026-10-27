import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'motor_superficies'))
import numpy as np
import pytest
from OCP.Geom import Geom_Plane,Geom_CylindricalSurface,Geom_Circle,Geom_TrimmedCurve
from OCP.gp import gp_Pln,gp_Ax3,gp_Ax2,gp_Pnt,gp_Dir
from OCP.GeomFill import GeomFill_BSplineCurves,GeomFill_StretchStyle
from OCP.GeomConvert import GeomConvert
from contornos_compatibles import _interpolar
from pcurvas_compartidas import crear_pcurva,LIMITE_PARAMETRICO_MM

def test_pcurva_cilindrica_no_modifica_curva3d_ni_superficie():
    surface=Geom_CylindricalSurface(gp_Ax3(),2.)
    curve=Geom_Circle(gp_Ax2(gp_Pnt(0,0,3),gp_Dir(0,0,1)),2.)
    params=np.linspace(.2,2*np.pi+.2,79)
    before=np.array([curve.Value(float(t)).Coord() for t in params])
    uv,proof=crear_pcurva(curve,.2,2*np.pi+.2,surface)
    assert proof['max_desacuerdo_mm']<=LIMITE_PARAMETRICO_MM
    assert np.array_equal(before,np.array([curve.Value(float(t)).Coord() for t in params]))
    for t in params:
        p=uv.Value(float(t));assert curve.Value(float(t)).Distance(surface.Value(p.X(),p.Y()))<1e-7

def test_no_oculta_curva_fuera_de_la_superficie():
    surface=Geom_Plane(gp_Pln(gp_Pnt(),gp_Dir(0,0,1)))
    curve=_interpolar(np.array([[0,0,.001],[1,0,.001]]))
    with pytest.raises(ValueError,match='no representa'):
        crear_pcurva(curve,curve.FirstParameter(),curve.LastParameter(),surface)

def test_pcurva_respeta_arco_analitico_en_parche_transfinito():
    circle=Geom_Circle(gp_Ax2(gp_Pnt(),gp_Dir(0,0,1)),1.)
    arc=Geom_TrimmedCurve(circle,0,np.pi/2)
    lines=[_interpolar(np.array([[0,1,0],[0,0,1]])),_interpolar(np.array([[0,0,1],[1,0,0]]))]
    boundary=[GeomConvert.CurveToBSplineCurve_s(c) for c in [arc,*lines]]
    surface=GeomFill_BSplineCurves(*boundary,GeomFill_StretchStyle).Surface()
    uv,proof=crear_pcurva(arc,0,np.pi/2,surface)
    assert proof['isoparametrica']
    assert proof['max_desacuerdo_mm']<=LIMITE_PARAMETRICO_MM
    for t in np.linspace(0,np.pi/2,101):
        p=uv.Value(float(t));assert arc.Value(float(t)).Distance(surface.Value(p.X(),p.Y()))<1e-7
