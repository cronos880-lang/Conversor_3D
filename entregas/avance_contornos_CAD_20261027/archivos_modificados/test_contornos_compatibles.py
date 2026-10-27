import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'motor_superficies'))
import numpy as np
import pytest
from OCP.Geom import Geom_Plane,Geom_CylindricalSurface
from OCP.gp import gp_Pln,gp_Ax3,gp_Pnt,gp_Dir
from OCP.GeomAPI import GeomAPI_ProjectPointOnSurf
from contornos_compatibles import _interseccion,_superficie_libre,_interpolar,separar_planos_aproximados,_sobre_superficie

def test_circulo_cerrado_cruza_costura_sin_retroceder():
    cylinder=Geom_CylindricalSurface(gp_Ax3(),2.)
    plane=Geom_Plane(gp_Pln(gp_Pnt(0,0,1),gp_Dir(0,0,1)))
    theta=np.linspace(1.7,1.7+2*np.pi,65)
    points=np.column_stack((2*np.cos(theta),2*np.sin(theta),np.ones(len(theta))))
    curve,first,last=_interseccion(cylinder,plane,points,.001,True)
    assert abs((last-first)-2*np.pi)<1e-7
    assert curve.Value(first).Distance(curve.Value(last))<1e-7
    for t in np.linspace(first,last,71):
        p=curve.Value(float(t));assert abs(np.hypot(p.X(),p.Y())-2.)<1e-7
        assert abs(p.Z()-1.)<1e-7

def test_interseccion_alejada_no_desplaza_contorno():
    a=Geom_Plane(gp_Pln(gp_Pnt(),gp_Dir(0,0,1)))
    b=Geom_Plane(gp_Pln(gp_Pnt(0,0,.1),gp_Dir(1e-4,0,1)))
    with pytest.raises(ValueError,match='próximo'):
        _interseccion(a,b,np.array([[0,0,0],[0,1,0]]),.012,False)

def test_seccion_plano_cilindro_conserva_oblicuidad_muy_pequena():
    cylinder=Geom_CylindricalSurface(gp_Ax3(),2.)
    normal=np.array([1e-7,-2e-7,1.]);normal/=np.linalg.norm(normal)
    plane=Geom_Plane(gp_Pln(gp_Pnt(0,0,1),gp_Dir(*map(float,normal))))
    t=np.linspace(.8,.8+2*np.pi,101);x=2*np.cos(t);y=2*np.sin(t)
    points=np.column_stack((x,y,1-(normal[0]*x+normal[1]*y)/normal[2]))
    curve,first,last=_interseccion(cylinder,plane,points,.001,True)
    for u in np.linspace(first,last,1025):
        p=np.array(curve.Value(float(u)).Coord())
        assert abs((p-np.array([0,0,1]))@normal)<1e-10
        assert abs(np.hypot(p[0],p[1])-2.)<1e-10

def test_interseccion_cilindros_cerrada_con_costura_bspline():
    a=Geom_CylindricalSurface(gp_Ax3(),2.)
    b=Geom_CylindricalSurface(gp_Ax3(gp_Pnt(),gp_Dir(1,0,0)),3.)
    t=np.linspace(1.7,1.7+2*np.pi,129)
    points=np.column_stack((2*np.cos(t),2*np.sin(t),np.sqrt(9-4*np.sin(t)**2)))
    curve,first,last=_interseccion(a,b,points,.001,True)
    assert curve.Value(first).Distance(curve.Value(last))<1e-7
    for u in np.linspace(first,last,131):
        p=curve.Value(float(u))
        assert abs(np.hypot(p.X(),p.Y())-2.)<2e-7
        assert abs(np.hypot(p.Y(),p.Z())-3.)<2e-7

def test_parche_libre_respeta_contornos_curvos_compartidos():
    original=Geom_Plane(gp_Pln(gp_Pnt(),gp_Dir(0,0,1)))
    curves=[_interpolar(np.array([[0,0,0],[.5,0,.01],[1,0,0]])),
            _interpolar(np.array([[1,0,0],[0,1,0]])),
            _interpolar(np.array([[0,1,0],[0,0,0]]))]
    edges=[(c,c.FirstParameter(),c.LastParameter()) for c in curves]
    result=_superficie_libre(original,edges,np.array([[.2,.2,0],[.5,.2,0],[.2,.5,0]]))
    for curve,first,last in edges:
        for t in np.linspace(first,last,41):
            projection=GeomAPI_ProjectPointOnSurf(curve.Value(float(t)),result)
            assert projection.NbPoints()>0
            assert projection.LowerDistance()<2e-6

def test_nucleo_plano_no_absorbe_redondeo_ni_modifica_stl():
    import trimesh
    from meshfit_brep import _FrozenMesh,_Proj
    vertices=np.array([[0,0,0],[1,0,0],[2,0,.004],[0,1,0],[1,1,0],[2,1,.004]],float)
    faces=np.array([[0,1,4],[0,4,3],[1,2,5],[1,5,4]])
    mesh=trimesh.Trimesh(vertices.copy(),faces.copy(),process=False)
    labels=np.zeros(4,dtype=int);original=labels.copy()
    surface=Geom_Plane(gp_Pln(gp_Pnt(),gp_Dir(0,0,1)))
    new,surfaces=separar_planos_aproximados(_FrozenMesh(mesh),labels,{0:surface})
    assert np.array_equal(mesh.vertices,vertices)
    assert np.array_equal(mesh.faces,faces)
    assert np.array_equal(labels,original)
    assert new[0]==new[1] and new[2]!=new[0] and new[3]!=new[0]
    for i in range(4):
        points=vertices[faces[i]]
        assert np.linalg.norm(_Proj(surfaces[new[i]]).batch(points)-points,axis=1).max()<1e-7

def test_contorno_plano_conserva_esquina_recta_entre_vertices():
    from meshfit_brep import _Proj
    plane=Geom_Plane(gp_Pln(gp_Pnt(),gp_Dir(0,0,1)))
    points=np.array([[0,0,0],[2,0,0],[2,1,0]],float)
    curve,first,last=_sobre_superficie(plane,points,False,_Proj(plane))
    for t in np.linspace(first,last,301):
        p=np.array(curve.Value(float(t)).Coord())
        assert min(abs(p[1]),abs(p[0]-2))<1e-10

def test_contorno_cilindrico_conserva_encuentro_arco_generatriz():
    from meshfit_brep import _Proj
    from pcurvas_compartidas import crear_pcurva
    surface=Geom_CylindricalSurface(gp_Ax3(),1.)
    points=np.array([[1,0,0],[np.cos(1),np.sin(1),0],[np.cos(1),np.sin(1),1.]])
    curve,first,last=_sobre_superficie(surface,points,False,_Proj(surface))
    uv,proof=crear_pcurva(curve,first,last,surface)
    assert proof['max_desacuerdo_mm']<=5e-8
    for t in np.linspace(first,last,301):
        p=np.array(curve.Value(float(t)).Coord());theta=np.arctan2(p[1],p[0])
        assert min(abs(p[2]),abs(theta-1))<1e-7

def test_esquinas_explicitas_conservan_tres_lados_de_un_parche():
    import trimesh
    from meshfit_brep import _FrozenMesh,_boundary_chains
    mesh=_FrozenMesh(trimesh.Trimesh([[0,0,0],[1,0,0],[0,1,0],[0,0,1]],
                                   [[0,2,1],[0,1,3],[1,2,3],[2,0,3]],process=False))
    labels=np.array([0,1,1,1]);chains,loops,_=_boundary_chains(mesh,labels)
    assert len(loops[0][0])==1
    mesh.esquinas_contorno_compartido={0,1,2}
    chains,loops,_=_boundary_chains(mesh,labels)
    assert len(loops[0][0])==3
    assert all(len(chains[key]['verts'])==2 for key,_ in loops[0][0])
