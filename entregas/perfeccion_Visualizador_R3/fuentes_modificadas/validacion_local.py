"""Control localizado STL <-> B-Rep, sin sustituir la validación global.

Inspecciona sobre todo aristas características y encuentros entre superficies:
son zonas que un muestreo uniforme puede ignorar. Distancias geométricas al
B-Rep exacto del STEP; no a una triangulación para la dirección STL->CAD.
Las medidas siguen siendo MUESTREADAS, nunca una garantía Hausdorff exacta.
"""
from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree


def _esparcir(puntos, limite):
    """Muestra determinista distribuida en el espacio sin sesgo por orden STL."""
    pts=np.asarray(puntos,dtype=float)
    if len(pts)<=limite:
        return pts
    mn=pts.min(axis=0); span=np.maximum(np.ptp(pts,axis=0),1e-9)
    # Dividir por celdas espaciadas para cubrir zonas separadas y pequeñas.
    bins=np.floor((pts-mn)/span*max(1,int(round(limite**(1/3))))).astype(int)
    _,idx=np.unique(bins,axis=0,return_index=True)
    idx=np.sort(idx)
    if len(idx)>=limite:
        idx=idx[np.linspace(0,len(idx)-1,limite,dtype=int)]
    else:
        rem=np.setdiff1d(np.arange(len(pts)),idx,assume_unique=False)
        idx=np.r_[idx,rem[np.linspace(0,len(rem)-1,min(len(rem),limite-len(idx)),dtype=int)]]
    return pts[idx]


def puntos_caracteristicos(mesh, total=240):
    """Cubre aristas vivas (encuentros planos/cilindros) y transiciones suaves.

    La triangulación de un cilindro introduce diedros moderados. Se incluye un
    subconjunto de esos bordes, además de las esquinas con diedro alto.
    """
    adj=np.asarray(mesh.face_adjacency_edges)
    ang=np.asarray(mesh.face_adjacency_angles)
    if not len(adj):
        return _esparcir(mesh.vertices,total)
    out=[]
    for cutoff,share in ((np.radians(25),0.45),(np.radians(4),0.35),(0,0.20)):
        mask=ang>=cutoff
        # Incluir puntos de bordes y puntos medios (sobre STL facetado).
        ed=adj[mask]
        if not len(ed):
            continue
        cloud=np.vstack((mesh.vertices[np.unique(ed)],mesh.vertices[ed].mean(axis=1)))
        out.append(_esparcir(cloud,max(12,int(total*share))))
    return _esparcir(np.vstack(out) if out else mesh.vertices,total)


def _distancias_cad(solido,puntos,progreso=None):
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from OCP.gp import gp_Pnt
    shell=solido.Shells()[0].wrapped
    # Conservar los índices internos del shell entre puntos; LoadS1 invalida
    # únicamente el punto consultado. Misma distancia exacta de OpenCascade.
    ext=BRepExtrema_DistShapeShape()
    ext.LoadS2(shell)
    distances=[]
    for i,p in enumerate(puntos):
        if progreso is not None and i % 100 == 0:
            progreso(i,len(puntos))
        vert=BRepBuilderAPI_MakeVertex(gp_Pnt(*map(float,p))).Vertex()
        ext.LoadS1(vert)
        ext.Perform()
        if not ext.IsDone():
            raise ValueError('No se pudo evaluar distancia local STL->STEP.')
        distances.append(float(ext.Value()))
    if progreso is not None:
        progreso(len(puntos),len(puntos))
    return np.asarray(distances,dtype=float)


def _puntos_brep(solido,limite=180):
    """Muestra aristas CAD genuinas, no solamente la superficie tessellada."""
    # .discretize(n) sigue la geometría analítica de cada arista, incluso circular.
    edges=solido.Edges()
    pts=[]
    for e in edges:
        try:
            samples=[e.positionAt(float(t)) for t in np.linspace(0.0,1.0,6)]
        except Exception:
            continue
        for p in samples:
            if hasattr(p,'toTuple'):
                pts.append(p.toTuple())
            else:
                pts.append((float(p.x),float(p.y),float(p.z)))
    return _esparcir(pts,limite) if pts else np.empty((0,3))


def proyectar_en_brep(solido,puntos):
    """Puntos genuinos sobre el shell exacto, nunca sobre su teselación."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from OCP.gp import gp_Pnt
    ext=BRepExtrema_DistShapeShape();ext.LoadS2(solido.Shells()[0].wrapped)
    out=[];distances=[]
    for p in puntos:
        ext.LoadS1(BRepBuilderAPI_MakeVertex(gp_Pnt(*map(float,p))).Vertex());ext.Perform()
        if not ext.IsDone() or ext.NbSolution()<1:raise ValueError('No se pudo proyectar la muestra al B-Rep exacto.')
        out.append(ext.PointOnShape2(1).Coord());distances.append(float(ext.Value()))
    return np.asarray(out),np.asarray(distances)


def inspeccionar_local(path_stl,solido,*,puntos_stl=240,puntos_cad=180,
                       tolerancia_max=0.060):
    import trimesh
    import vtk
    from vtk.util.numpy_support import vtk_to_numpy
    mesh=trimesh.load(str(path_stl),force='mesh',process=True)
    pts=puntos_caracteristicos(mesh,puntos_stl)
    stl_cad=_distancias_cad(solido,pts)
    reader=vtk.vtkSTLReader(); reader.SetFileName(str(path_stl));reader.Update()
    query=vtk.vtkImplicitPolyDataDistance();query.SetInput(reader.GetOutput())
    edpts=_puntos_brep(solido,puntos_cad)
    cad_stl=np.array([abs(query.EvaluateFunction(p)) for p in edpts],dtype=float)
    def stats(a,cloud):
        if not len(a):
            return {'muestras':0,'p95_mm':None,'max_mm':None,'zonas_sospechosas':[]}
        order=np.argsort(-a)[:min(12,len(a))]
        hot=[{'xyz_mm':[round(float(x),4) for x in cloud[i]],
              'desviacion_mm':round(float(a[i]),6)} for i in order if a[i]>tolerancia_max/2]
        return {'muestras':len(a),'p95_mm':round(float(np.percentile(a,95)),6),
                'max_mm':round(float(a.max()),6),'zonas_sospechosas':hot}
    a=stats(stl_cad,pts);b=stats(cad_stl,edpts)
    return {'stl_caracteristicas_a_step':a,'aristas_step_a_stl':b,
            'tolerancia_informativa_mm':tolerancia_max,
            'supera_umbral_observado':bool((len(stl_cad) and stl_cad.max()>tolerancia_max) or
                                     (len(cad_stl) and cad_stl.max()>tolerancia_max)),
            'nota':'Diagnóstico muestreado; validar si cada discrepancia proviene del STL facetado.'}
