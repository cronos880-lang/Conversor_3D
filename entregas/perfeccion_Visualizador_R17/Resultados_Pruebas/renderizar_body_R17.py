"""Compare native STEP surfaces and edges, without displaying tessellation edges."""
from pathlib import Path
import json, hashlib
import cadquery as cq
import numpy as np
import vtk

W = Path(__file__).resolve().parent
paths = [W/'referencia_R16/body.step', W/'navegador_body_R17.step']
if not paths[0].exists():
    paths[0] = next(p for p in (W/'referencia_R16').glob('*.step') if 'body' in p.name.lower())
window = vtk.vtkRenderWindow()
window.SetOffScreenRendering(1)
window.SetSize(1800, 1400)
window.SetMultiSamples(4)
metadata = []
for col, path in enumerate(paths):
    print('Importando', path.name, flush=True)
    solid = cq.importers.importStep(str(path)).val()
    vertices, triangles = solid.copy().tessellate(.01, angularTolerance=.05)
    pts = vtk.vtkPoints(); cells = vtk.vtkCellArray()
    for p in vertices:
        pts.InsertNextPoint(*p.toTuple())
    for tri in triangles:
        cells.InsertNextCell(3)
        for i in tri:
            cells.InsertCellPoint(int(i))
    data = vtk.vtkPolyData(); data.SetPoints(pts); data.SetPolys(cells)
    # CQ keeps separate vertex indices at native face borders. Smooth only
    # triangles sharing vertices within each face; never weld native faces.
    normals = vtk.vtkPolyDataNormals(); normals.SetInputData(data)
    normals.SplittingOff(); normals.Update()
    face_mapper = vtk.vtkPolyDataMapper(); face_mapper.SetInputConnection(normals.GetOutputPort())
    pts = vtk.vtkPoints(); lines = vtk.vtkCellArray(); index = 0
    for edge in solid.Edges():
        samples = [edge.positionAt(k/(1 if edge.geomType() == 'LINE' else 64))
                   for k in range(2 if edge.geomType() == 'LINE' else 65)]
        lines.InsertNextCell(len(samples))
        for p in samples:
            pts.InsertNextPoint(*p.toTuple()); lines.InsertCellPoint(index); index += 1
    data = vtk.vtkPolyData(); data.SetPoints(pts); data.SetLines(lines)
    edge_mapper = vtk.vtkPolyDataMapper(); edge_mapper.SetInputData(data)
    edge_mapper.SetResolveCoincidentTopologyToPolygonOffset()
    box = solid.BoundingBox()
    center = np.array([(box.xmin+box.xmax)/2, (box.ymin+box.ymax)/2, (box.zmin+box.zmax)/2])
    size = max(box.xlen, box.ylen, box.zlen)
    for row, direction in enumerate([(1, -1, -1.4), (1, -1, .75)]):
        ren = vtk.vtkRenderer(); ren.SetViewport(col/2, row/2, (col+1)/2, (row+1)/2)
        ren.SetBackground(.965, .975, .985); window.AddRenderer(ren)
        actor = vtk.vtkActor(); actor.SetMapper(face_mapper)
        actor.GetProperty().SetColor(.48, .70, .86); actor.GetProperty().SetInterpolationToPhong()
        ren.AddActor(actor)
        actor = vtk.vtkActor(); actor.SetMapper(edge_mapper)
        actor.GetProperty().SetColor(.12, .20, .28); actor.GetProperty().SetLineWidth(1)
        ren.AddActor(actor)
        text = vtk.vtkTextActor()
        title = ('R16: 11.667 caras planas' if col == 0 else 'R17: 426 caras / 5 cilindros / 3 conos')
        text.SetInput(title + ('\nCara inferior: grabados conservados' if row == 0 else '\nAristas nativas del STEP exportado'))
        text.GetTextProperty().SetColor(.1, .17, .23); text.GetTextProperty().SetFontSize(23)
        text.SetPosition(22, 635); ren.AddViewProp(text)
        camera = ren.GetActiveCamera(); camera.SetPosition(*(center+size*np.array(direction)))
        camera.SetFocalPoint(*center); camera.SetViewUp(0, 0, 1)
        camera.ParallelProjectionOn(); ren.ResetCamera(); camera.Zoom(1.1)
    metadata.append(dict(archivo=path.name, sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                         caras=len(solid.Faces()), aristas=len(solid.Edges()),
                         nota='Render de superficies y aristas nativas; no valida Onshape.'))
window.Render(); capture = vtk.vtkWindowToImageFilter(); capture.SetInput(window); capture.Update()
writer = vtk.vtkPNGWriter(); writer.SetFileName(str(W/'Body_R16_R17.png'))
writer.SetInputConnection(capture.GetOutputPort()); writer.Write()
(W/'RENDER_CAD_R17.json').write_text(json.dumps(metadata, indent=2))
print('Comparación CAD guardada.', flush=True)
