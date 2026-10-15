from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import numpy as np
import trimesh
from fastapi import FastAPI, UploadFile, HTTPException, Form
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from OCP.gp import gp_Pnt
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakePolygon, BRepBuilderAPI_MakeFace, BRepBuilderAPI_Sewing, BRepBuilderAPI_MakeSolid
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain
from OCP.TopoDS import TopoDS
from OCP.TopAbs import TopAbs_SHELL
from OCP.TopExp import TopExp_Explorer
from OCP.STEPControl import STEPControl_Writer, STEPControl_Reader, STEPControl_AsIs
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp
from OCP.IFSelect import IFSelect_RetDone

app = FastAPI()
ROOT = Path(__file__).parent
lock = threading.Lock()
MAX_BYTES = 20 * 1024 * 1024
MAX_FACES = 20000

@app.get('/')
def index():
    return FileResponse(ROOT / 'static/index.html')

@app.post('/api/convert')
def convert(file: UploadFile, units: str = Form('mm')):
    if units not in ('mm', 'cm', 'in'):
        raise HTTPException(422, 'Unidad no válida.')
    data = file.file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, 'Máximo 20 MB.')
    try:
        mesh = trimesh.load(BytesIO(data), file_type='stl', force='mesh', process=True)
        if not len(mesh.faces) or not np.isfinite(mesh.vertices).all():
            raise ValueError('STL vacío o coordenadas no válidas.')
        if len(mesh.faces) > MAX_FACES:
            raise ValueError('Máximo 20.000 triángulos para esta versión.')
        if not mesh.is_watertight or not mesh.is_winding_consistent or abs(mesh.volume) < 1e-12:
            raise ValueError('Se requiere una malla cerrada, con volumen y orientación coherente. Repara el STL antes de convertir.')
        mesh.apply_scale({'mm': 1, 'cm': 10, 'in': 25.4}[units])
        with lock, TemporaryDirectory() as tmp:
            from OCP.BRep import BRep_Builder
            from OCP.TopoDS import TopoDS_Compound
            compound = TopoDS_Compound()
            builder = BRep_Builder()
            builder.MakeCompound(compound)
            parts = list(mesh.split(only_watertight=False))
            for i, part in enumerate(parts):
                for other in parts[:i]:
                    if np.all(np.minimum(part.bounds[1], other.bounds[1]) > np.maximum(part.bounds[0], other.bounds[0])):
                        raise ValueError('Componentes superpuestos o envolventes anidadas: esta versión no admite cavidades separadas. No se ha modificado la pieza.')
            expected_volume = sum(abs(part.volume) for part in parts)
            for part in parts:
                if part.volume < 0:
                    part.invert()
                sewing = BRepBuilderAPI_Sewing(1e-7)
                for triangle in part.triangles:
                    poly = BRepBuilderAPI_MakePolygon()
                    for point in triangle:
                        poly.Add(gp_Pnt(*map(float, point)))
                    poly.Close()
                    face = BRepBuilderAPI_MakeFace(poly.Wire())
                    if not face.IsDone():
                        raise ValueError('No se pudo construir una cara válida.')
                    sewing.Add(face.Face())
                sewing.Perform()
                shells = TopExp_Explorer(sewing.SewedShape(), TopAbs_SHELL)
                count = 0
                while shells.More():
                    solid = BRepBuilderAPI_MakeSolid(TopoDS.Shell(shells.Current())).Solid()
                    if not BRepCheck_Analyzer(solid).IsValid():
                        raise ValueError('La malla no genera un sólido CAD válido.')
                    unify = ShapeUpgrade_UnifySameDomain(solid, True, True, False)
                    unify.Build()
                    shape = unify.Shape()
                    if not BRepCheck_Analyzer(shape).IsValid():
                        raise ValueError('El sólido simplificado no es válido.')
                    builder.Add(compound, shape)
                    count += 1
                    shells.Next()
                if count != 1:
                    raise ValueError('Topología ambigua: se esperaba una envolvente por componente.')
            writer = STEPControl_Writer()
            if writer.Transfer(compound, STEPControl_AsIs) != IFSelect_RetDone:
                raise ValueError('Fallo de transferencia STEP.')
            path = str(Path(tmp) / 'modelo.step')
            if writer.Write(path) != IFSelect_RetDone:
                raise ValueError('No se pudo exportar STEP.')
            reader = STEPControl_Reader()
            if reader.ReadFile(path) != IFSelect_RetDone or reader.TransferRoots() == 0:
                raise ValueError('El STEP exportado no se puede volver a abrir.')
            restored = reader.OneShape()
            props = GProp_GProps()
            BRepGProp.VolumeProperties_s(restored, props)
            if not BRepCheck_Analyzer(restored).IsValid() or not np.isclose(props.Mass(), expected_volume, rtol=1e-5, atol=1e-10):
                raise ValueError('La comprobación del STEP no conserva un sólido válido y su volumen.')
            result = Path(path).read_bytes()
        return Response(result, media_type='application/step', headers={'Content-Disposition': 'attachment; filename="modelo.step"'})
    except (ValueError, IndexError) as error:
        raise HTTPException(422, str(error)) from error
    except Exception as error:
        import logging
        logging.exception('STL conversion failed')
        raise HTTPException(422, 'No se pudo convertir este STL. Comprueba su geometría.') from error

app.mount('/static', StaticFiles(directory=ROOT / 'static'), name='static')
