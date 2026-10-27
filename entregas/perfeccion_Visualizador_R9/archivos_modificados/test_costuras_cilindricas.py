"""Costuras sobre soportes coincidentes y separación de cilindros distintos."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'motor_superficies'))
import numpy as np
import pytest
from OCP.Geom import Geom_CylindricalSurface
from OCP.gp import gp_Ax3,gp_Pnt,gp_Dir
from contornos_compatibles import _interseccion


def cilindro(*,radius=2.,center=(0,0,0),axis=(0,0,1),x=(1,0,0)):
    return Geom_CylindricalSurface(gp_Ax3(gp_Pnt(*center),gp_Dir(*axis),gp_Dir(*x)),radius)


def test_costura_generatriz_con_marcos_uv_distintos():
    a=cilindro();b=cilindro(center=(0,0,7),axis=(0,0,-1),x=(0,1,0))
    points=np.array([[2,0,0],[2,0,3]],float)
    curve,first,last=_interseccion(a,b,points,.001,False)
    for t in np.linspace(first,last,31):
        p=np.array(curve.Value(float(t)).Coord())
        assert np.linalg.norm(p[:2]-[2,0])<1e-10
        assert -1e-10<=p[2]<=3+1e-10


def test_costura_circular_cerrada_no_acorta_la_vuelta():
    a=cilindro();b=cilindro(x=(0,1,0))
    theta=np.linspace(1.8,1.8+2*np.pi,65,endpoint=False)
    points=np.c_[2*np.cos(theta),2*np.sin(theta),np.ones(len(theta))]
    curve,first,last=_interseccion(a,b,points,.001,True)
    assert curve.Value(first).Distance(curve.Value(last))<1e-8
    samples=np.array([curve.Value(float(t)).Coord() for t in np.linspace(first,last,513)])
    assert np.max(abs(np.linalg.norm(samples[:,:2],axis=1)-2))<2e-8
    assert np.ptp(np.unwrap(np.arctan2(samples[:,1],samples[:,0])))>2*np.pi-1e-5


def test_cilindros_coaxiales_de_radios_distintos_no_se_confunden():
    with pytest.raises(ValueError,match='encuentro'):
        _interseccion(cilindro(),cilindro(radius=2.001),np.array([[2,0,0],[2,0,2]]),1e-5,False)


def test_ejes_proximos_no_se_tratan_como_el_mismo_soporte():
    with pytest.raises(ValueError,match='encuentro'):
        _interseccion(cilindro(),cilindro(center=(.001,0,0)),np.array([[2,0,0],[2,0,2]]),1e-6,False)


def test_medias_canas_solo_se_activan_en_la_ruta_compartida():
    import trimesh
    from meshfit_brep import _presplit_holed_rings
    mesh=trimesh.creation.cylinder(radius=2,height=3,sections=128)
    ids=np.flatnonzero(abs(mesh.face_normals[:,2])<.1)
    labels=np.full(len(mesh.faces),-1,int);labels[ids]=0
    original=labels.copy();surfaces={0:cilindro()}
    _presplit_holed_rings(mesh,labels,surfaces,.003)
    assert np.array_equal(labels,original)
    _presplit_holed_rings(mesh,labels,surfaces,.003,completos=True)
    assert len(np.unique(labels[ids]))==2
    assert np.array_equal(labels[np.setdiff1d(np.arange(len(labels)),ids)],original[np.setdiff1d(np.arange(len(labels)),ids)])
