import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'motor_superficies'))
import numpy as np
import pytest
from OCP.Geom import Geom_BezierCurve,Geom_Ellipse
from OCP.TColgp import TColgp_Array1OfPnt
from OCP.gp import gp_Pnt,gp_Vec,gp_Ax2,gp_Dir
from parches_triangulares import bezier_local,superficie_triangular
from contornos_compatibles import acondicionar_conica

def curve(points):
    poles=TColgp_Array1OfPnt(1,len(points))
    for i,p in enumerate(points):poles.SetValue(i+1,gp_Pnt(*p))
    return Geom_BezierCurve(poles)

def test_parche_triangular_tiene_esquinas_regulares_y_contornos_exactos():
    original=[curve([(0,0,0),(.5,0,.004),(1,0,0)]),curve([(1,0,0),(0,1,0)]),curve([(0,1,0),(0,0,0)])]
    edges=[bezier_local(c,0.,1.,c.Value(0).Coord(),c.Value(1).Coord()) for c in original]
    surface=superficie_triangular(edges,np.array([1/3,1/3,0.]))
    for i,c in enumerate(original):
        for s in np.linspace(0,1,79):
            u,v=((s,0),(1-s,s),(0,1-s))[i]
            assert surface.Value(float(u),float(v)).Distance(c.Value(float(s)))<1e-8
    for u,v in [(0,0),(1,0),(0,1),(1/3,1/3)]:
        p=gp_Pnt();du=gp_Vec();dv=gp_Vec();surface.D1(u,v,p,du,dv)
        assert np.cross(du.Coord(),dv.Coord())[2]>.99
    assert surface.Value(1/3,1/3).Distance(gp_Pnt(1/3,1/3,0))<1e-9

def test_no_fuerza_anclaje_interior_incompatible():
    original=[curve([(0,0,0),(.5,0,.02),(1,0,0)]),curve([(1,0,0),(0,1,0)]),curve([(0,1,0),(0,0,0)])]
    edges=[bezier_local(c,0.,1.,c.Value(0).Coord(),c.Value(1).Coord()) for c in original]
    with pytest.raises(ValueError,match='excede'):
        superficie_triangular(edges,np.array([1/3,1/3,0.]))

def test_conica_enorme_se_representa_localmente_sin_polos_enormes():
    major=191480072.5;minor=16.4476;theta=1.85
    center=np.array([-major*np.cos(theta),-minor*np.sin(theta),0.])
    source=Geom_Ellipse(gp_Ax2(gp_Pnt(*map(float,center)),gp_Dir(0,0,1)),major,minor)
    first,last=theta-2e-9,theta+2e-9
    local,a,b=acondicionar_conica(source,first,last)
    assert (a,b)==(0.,1.)
    assert max(np.linalg.norm(local.Pole(i).Coord()) for i in range(1,local.NbPoles()+1))<1.
    for t in np.linspace(0,1,101):
        p=np.asarray(local.Value(float(t)).Coord(),dtype=np.longdouble)-center.astype(np.longdouble)
        residual=(p[0]/major)**2+(p[1]/minor)**2-1
        gradient=2*np.hypot(p[0]/major**2,p[1]/minor**2)
        assert abs(residual)/gradient<1e-8
    assert source.MajorRadius()==major
