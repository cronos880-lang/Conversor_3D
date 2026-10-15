from io import BytesIO
from tempfile import NamedTemporaryFile
import pytest
import trimesh
from fastapi.testclient import TestClient
from OCP.STEPControl import STEPControl_Reader
from OCP.IFSelect import IFSelect_RetDone
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp
from app import app
client = TestClient(app)

@pytest.mark.parametrize('kind', ['box','cylinder','sphere','multiple'])
def test_roundtrip(kind):
    mesh = {'box': lambda: trimesh.creation.box((2,3,4)), 'cylinder':lambda:trimesh.creation.cylinder(radius=2,height=3,sections=24), 'sphere':lambda:trimesh.creation.icosphere(subdivisions=1), 'multiple':lambda:trimesh.util.concatenate([trimesh.creation.box(),trimesh.creation.box().apply_translation([3,0,0])])}[kind]()
    result=client.post('/api/convert',files={'file':('test.stl',mesh.export(file_type='stl'))})
    assert result.status_code==200,result.text
    with NamedTemporaryFile(suffix='.step') as f:
        f.write(result.content);f.flush()
        reader=STEPControl_Reader()
        assert reader.ReadFile(f.name)==IFSelect_RetDone
        assert reader.TransferRoots()>0
        shape=reader.OneShape()
        assert BRepCheck_Analyzer(shape).IsValid()
        props=GProp_GProps();BRepGProp.VolumeProperties_s(shape,props)
        assert props.Mass()==pytest.approx(mesh.volume,rel=1e-5)

def test_reject_open_mesh():
    m=trimesh.creation.box();m.update_faces(list(range(11)))
    assert client.post('/api/convert',files={'file':('open.stl',m.export(file_type='stl'))}).status_code==422

def test_reject_garbage():
    assert client.post('/api/convert',files={'file':('x.stl',b'invalid')}).status_code==422

def test_ui():
    assert client.get('/').status_code==200
    assert client.get('/static/app.js').status_code==200

@pytest.mark.parametrize('units,volume', [('mm',1),('cm',1000),('in',25.4**3)])
def test_units_and_repeated_conversion(units,volume):
    mesh=trimesh.creation.box()
    for _ in range(2):
        result=client.post('/api/convert',data={'units':units},files={'file':('box.stl',mesh.export(file_type='stl_ascii'))})
        assert result.status_code==200,result.text
        with NamedTemporaryFile(suffix='.step') as f:
            f.write(result.content);f.flush()
            reader=STEPControl_Reader();assert reader.ReadFile(f.name)==IFSelect_RetDone
            reader.TransferRoots();props=GProp_GProps()
            BRepGProp.VolumeProperties_s(reader.OneShape(),props)
            assert props.Mass()==pytest.approx(volume,rel=1e-6)

def test_reject_nested_shells():
    inner=trimesh.creation.box();inner.invert()
    mesh=trimesh.util.concatenate([trimesh.creation.box((3,3,3)),inner])
    result=client.post('/api/convert',files={'file':('hollow.stl',mesh.export(file_type='stl'))})
    assert result.status_code==422

def test_reject_large_file():
    assert client.post('/api/convert',files={'file':('large.stl',b'0'*(20*1024*1024+1))}).status_code==413
