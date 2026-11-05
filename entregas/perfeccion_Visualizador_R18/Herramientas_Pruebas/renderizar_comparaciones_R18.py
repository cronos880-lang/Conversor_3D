"""Draw native STEP edges; never expose triangulation edges as CAD features."""
from pathlib import Path
import json,hashlib,cadquery as cq,numpy as np,vtk,sys,gc
W=Path(__file__).resolve().parent
sources=dict(flame=[Path('/workspace/attachments/8f34962b-1afd-4526-828e-7f3ca34a9749/Flame_Base.step'),W/'navegador_flame_R18.step'],base=[W/'referencia_R17/Base.step',W/'navegador_base_R18.step'])
metadata=[]
for kind in sys.argv[1:]or['flame','base']:
 window=vtk.vtkRenderWindow();window.SetOffScreenRendering(1);window.SetSize(1800,1400);window.SetMultiSamples(4)
 for col,path in enumerate(sources[kind]):
  print('Importando',kind,col,flush=True);solid=cq.importers.importStep(str(path)).val();vertices,triangles=solid.copy().tessellate(.01,angularTolerance=.05);pts=vtk.vtkPoints();cells=vtk.vtkCellArray()
  for p in vertices:pts.InsertNextPoint(*p.toTuple())
  for tri in triangles:
   cells.InsertNextCell(3)
   for i in tri:cells.InsertCellPoint(int(i))
  data=vtk.vtkPolyData();data.SetPoints(pts);data.SetPolys(cells);normals=vtk.vtkPolyDataNormals();normals.SetInputData(data);normals.SplittingOff();normals.Update();face_mapper=vtk.vtkPolyDataMapper();face_mapper.SetInputConnection(normals.GetOutputPort())
  pts=vtk.vtkPoints();lines=vtk.vtkCellArray();index=0
  for edge in solid.Edges():
   samples=[edge.positionAt(k/(1 if edge.geomType()=='LINE'else 64))for k in range(2 if edge.geomType()=='LINE'else 65)];lines.InsertNextCell(len(samples))
   for p in samples:pts.InsertNextPoint(*p.toTuple());lines.InsertCellPoint(index);index+=1
  data=vtk.vtkPolyData();data.SetPoints(pts);data.SetLines(lines);edge_mapper=vtk.vtkPolyDataMapper();edge_mapper.SetInputData(data);edge_mapper.SetResolveCoincidentTopologyToPolygonOffset();box=solid.BoundingBox();center=np.array([(box.xmin+box.xmax)/2,(box.ymin+box.ymax)/2,(box.zmin+box.zmax)/2]);size=max(box.xlen,box.ylen,box.zlen)
  for row,direction in enumerate([(1,-1,-1.4),(1,-1,.9)]):
   ren=vtk.vtkRenderer();ren.SetViewport(col/2,row/2,(col+1)/2,(row+1)/2);ren.SetBackground(.965,.975,.985);window.AddRenderer(ren);actor=vtk.vtkActor();actor.SetMapper(face_mapper);actor.GetProperty().SetColor(.48,.70,.86);actor.GetProperty().SetInterpolationToPhong();ren.AddActor(actor);actor=vtk.vtkActor();actor.SetMapper(edge_mapper);actor.GetProperty().SetColor(.12,.20,.28);actor.GetProperty().SetLineWidth(1);ren.AddActor(actor);text=vtk.vtkTextActor();title=('Referencia facetada'if col==0 else'R18: superficies medidas')+' / '+str(len(solid.Faces()))+' caras';text.SetInput(title+('\nVista inferior; detalles originales'if row==0 else'\nAristas nativas del STEP real'));text.GetTextProperty().SetColor(.1,.17,.23);text.GetTextProperty().SetFontSize(23);text.SetPosition(22,635);ren.AddViewProp(text);camera=ren.GetActiveCamera();camera.SetPosition(*(center+size*np.array(direction)));camera.SetFocalPoint(*center);camera.SetViewUp(0,0,1);camera.ParallelProjectionOn();ren.ResetCamera();camera.Zoom(1.05)
  metadata.append(dict(pieza=kind,version='referencia'if col==0 else'R18',archivo=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),caras=len(solid.Faces()),aristas=len(solid.Edges()),nota='Superficies y aristas nativas del STEP; no valida Onshape.'))
 window.Render();capture=vtk.vtkWindowToImageFilter();capture.SetInput(window);capture.Update();writer=vtk.vtkPNGWriter();writer.SetFileName(str(W/(kind+'_R17_R18.png')));writer.SetInputConnection(capture.GetOutputPort());writer.Write();window.Finalize();gc.collect();print('Guardado',kind,flush=True)
(W/'RENDER_CAD_R18.json').write_text(json.dumps(metadata,indent=2))
