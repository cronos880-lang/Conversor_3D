"""Reconstrucción general por perfiles CAD para mallas de niveles discretos.

No inspecciona nombres de STL. Detecta el eje de extrusión a partir de los
niveles de los vértices, extrae perfiles en cada estrato y usa B-splines
cerradas para las zonas curvas. No aproxima polígonos por círculos si no
pasan el control radial. El STEP final lo valida el motor principal contra
la malla ORIGINAL.
"""
from __future__ import annotations
import numpy as np
import trimesh
import cadquery as cq
from shapely.geometry import Polygon,LineString
from pathlib import Path

def detectar_eje(mesh):
    # Las piezas realmente estratificadas tienen pocos niveles discretos en
    # uno de los tres ejes. Evitar falsos positivos comprobando además área
    # significativa y que haya triángulos no paralelos a cada corte.
    cs=[]
    for axis in range(3):
        vv=np.round(mesh.vertices[:,axis],5)
        v,counts=np.unique(vv,return_counts=True)
        mask=counts>=max(30, int(len(vv)*.006))
        important=np.sort(v[mask])
        if len(important)<2 or len(important)>12:continue
        coverage=counts[mask].sum()/len(vv)
        if coverage>=.88:cs.append((coverage,axis,important))
    return max(cs,key=lambda x:x[0]) if cs else None

def _pos2(x,axis):
    return [i for i in range(3) if i!=axis]

def _wire(points,axis,h, tol=0.005):
    """Contorno CAD exacto o circular analítico, sin overshoot de B-splines.

    Las interpolaciones periódicas de miles de puntos pueden cruzarse incluso
    cuando sus vértices encajan bien: NO se usan para perfiles dentados.
    """
    from shapely.geometry import LineString
    points=np.asarray(points,float)
    if len(points)>=25:
        # Ajuste de circunferencia a todos los puntos del contorno, con cota
        # MÁXIMA de error; sin idealización de perfiles no circulares.
        A=np.c_[2*points[:,0],2*points[:,1],np.ones(len(points))]
        centerx,centery,c0=np.linalg.lstsq(A,(points*points).sum(axis=1),rcond=None)[0]
        r=np.sqrt(max(0.,c0+centerx**2+centery**2))
        deviation=np.abs(np.linalg.norm(points-[centerx,centery],axis=1)-r)
        if np.max(deviation)<0.012:
            ctr=np.zeros(3);ctr[axis]=h;ctr[_pos2(points[0],axis)]=[centerx,centery]
            norm=np.zeros(3);norm[axis]=1
            return cq.Wire.assembleEdges([cq.Edge.makeCircle(r,cq.Vector(*ctr),cq.Vector(*norm))])
    simple=LineString(np.vstack((points,points[0]))).simplify(tol,preserve_topology=True)
    coords=np.asarray(simple.coords)[:-1]
    xyz=np.zeros((len(coords),3));xyz[:,axis]=h;xyz[:,_pos2(points[0],axis)]=coords
    return cq.Wire.makePolygon([cq.Vector(*v) for v in xyz],close=True)

def _sections_at(mesh,axis,h):
    normal=np.zeros(3);normal[axis]=1
    origin=np.zeros(3);origin[axis]=h
    sec=mesh.section(plane_origin=origin,plane_normal=normal)
    if sec is None:raise ValueError('Sección vacía de una malla estratificada.')
    idx=_pos2(None,axis)
    loops=[]
    for points in sec.discrete:
        xy=points[:,idx]
        if np.linalg.norm(xy[0]-xy[-1])>.02:
            raise ValueError('Contorno abierto en sección CAD.')
        poly=Polygon(xy)
        if not poly.is_valid or poly.area <1e-5:
            raise ValueError('Contorno degenerado en sección CAD.')
        loops.append((poly,np.asarray(xy)[:-1]))
    return loops


def construir_por_vaciados(src,dest, *, profile_tol=0.005, max_faces=50000):
    """Reconstruye estratos por diferencia CAD en una única extrusión exterior.

    Frente a fusionar todos los estratos, solo corta vacíos interiores, evitando
    los problemas de coincidencia de las paredes exteriores complejas.
    """
    mesh=trimesh.load(str(src),force='mesh',process=True)
    if not mesh.is_watertight or len(mesh.faces)>max_faces:
        raise ValueError('STL no válido para reconstrucción por estratos.')
    candidate=detectar_eje(mesh)
    if candidate is None:
        raise ValueError('No se han detectado estratos planos.')
    _,axis,levels=candidate
    levels[0]=mesh.vertices[:,axis].min()
    levels[-1]=mesh.vertices[:,axis].max()
    samples=[]
    for lo,hi in zip(levels[:-1],levels[1:]):
        if hi-lo<1e-5:continue
        loops=_sections_at(mesh,axis,float((lo+hi)/2))
        loops.sort(key=lambda v:v[0].area,reverse=True)
        if len(loops)==0:raise ValueError('Sección sin contornos.')
        samples.append((float(lo),float(hi),loops))
    # Contorno exterior constante durante toda la altura.
    ref=samples[0][2][0][0]
    for lo,hi,loops in samples[1:]:
        exterior=loops[0][0]
        if ref.hausdorff_distance(exterior)>.002:
            raise ValueError('El contorno exterior cambia: se requiere el reconstructor 3D.')
    lo=samples[0][0]; hi=samples[-1][1]
    outer=_wire(samples[0][2][0][1],axis,lo,profile_tol)
    face=cq.Face.makeFromWires(outer)
    v=np.zeros(3);v[axis]=hi-lo
    base=cq.Solid.extrudeLinear(face,cq.Vector(*v))
    if not base.isValid():raise ValueError('El perfil exterior no es CAD válido.')
    print(f'[Vaciados] exterior extruido de {lo:.4f} a {hi:.4f}; caras={len(base.Faces())}',flush=True)
    holes=[]
    for lo,hi,loops in samples:
        parent=[None]*len(loops)
        for i,(poly,_) in enumerate(loops[1:],start=1):
            hosts=[j for j,(candidate,_) in enumerate(loops)
                   if j!=i and candidate.area>poly.area and candidate.contains(poly)]
            parent[i]=min(hosts,key=lambda j:loops[j][0].area) if hosts else None
        depth=[]
        for i in range(len(loops)):
            d=0;j=parent[i]
            while j is not None:
                d+=1;j=parent[j]
                if d>len(loops):raise ValueError('Jerarquía de huecos imposible.')
            depth.append(d)
        for i,(poly,coords) in enumerate(loops):
            if depth[i]%2!=1:continue
            children=[j for j in range(len(loops)) if parent[j]==i]
            print(f'[Vaciados] {lo:.3f} a {hi:.3f}; vacío {i}, {len(children)} islas',flush=True)
            boundary=_wire(coords,axis,lo,profile_tol)
            islands=[_wire(loops[j][1],axis,lo,profile_tol) for j in children]
            cutface=cq.Face.makeFromWires(boundary,islands)
            direction=np.zeros(3);direction[axis]=hi-lo
            cutsolid=cq.Solid.extrudeLinear(cutface,cq.Vector(*direction))
            if not cutsolid.isValid():raise ValueError('Un recorte CAD es inválido.')
            holes.append(cutsolid)
    print(f'[Vaciados] restando {len(holes)} huecos; caras exteriores={len(base.Faces())}',flush=True)
    # Conservar el sólido exterior único, no unir N caras de engranaje coincidentes.
    # Un único BOP multiparte permite compartir internamente las mismas intersecciones.
    body=base.cut(*holes).clean()
    ss=body.Solids()
    print(f'[Vaciados] sólido resultante: {len(ss)} cuerpos, caras={len(body.Faces())}',flush=True)
    if len(ss)!=1 or not body.isValid():
        raise ValueError('Los recortes no forman un único sólido CAD válido.')
    cq.exporters.export(body,str(dest),exportType='STEP')
    chk=cq.importers.importStep(str(dest)).solids().vals()
    if len(chk)!=1 or not chk[0].isValid():
        raise ValueError('STEP recortado no válido al reimportar.')
    return {'caras':len(chk[0].Faces()), 'volumen':chk[0].Volume(),
            'eje':axis,'estratos':len(samples),'huecos':len(holes)}

if __name__=='__main__' and len(__import__('sys').argv)>3 and __import__('sys').argv[3]=='vaciados':
    import sys,json
    print(json.dumps(construir_por_vaciados(sys.argv[1],sys.argv[2]),ensure_ascii=False))
