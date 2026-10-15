"""Pruebas del motor WebAssembly real sobre un servidor estático en el puerto 8010."""
from pathlib import Path
from tempfile import TemporaryDirectory
import trimesh
from playwright.sync_api import sync_playwright
from OCP.STEPControl import STEPControl_Reader
from OCP.IFSelect import IFSelect_RetDone
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps

with TemporaryDirectory() as tmp, sync_playwright() as p:
    root=Path(tmp)
    browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--enable-unsafe-swiftshader'])
    page=browser.new_page(accept_downloads=True)
    errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto('http://127.0.0.1:8010/')
    box=trimesh.creation.box((2,3,4))
    multiple=trimesh.util.concatenate([box,box.copy().apply_translation([5,0,0])])
    torus=trimesh.creation.torus(major_radius=3,minor_radius=1,major_sections=16,minor_sections=8)
    cases=[('caja',box,'mm','stl'),('cilindro',trimesh.creation.cylinder(radius=2,height=3,sections=24),'mm','stl'),('esfera',trimesh.creation.icosphere(subdivisions=1),'mm','stl'),('piezas',multiple,'mm','stl'),('toro',torus,'mm','stl'),('cm',box,'cm','stl_ascii'),('pulgadas',box,'in','stl'),('repeticion',box,'mm','stl')]
    for name,mesh,units,fmt in cases:
        source=root/f'{name}.stl';source.write_bytes(mesh.export(file_type=fmt).encode() if fmt=='stl_ascii' else mesh.export(file_type=fmt))
        page.locator('#file').set_input_files(str(source));page.wait_for_function("!document.querySelector('#convert').disabled")
        page.locator('#units').select_option(units)
        with page.expect_download(timeout=60000) as event:page.locator('#convert').click()
        step=root/f'{name}.step';event.value.save_as(str(step))
        reader=STEPControl_Reader();assert reader.ReadFile(str(step))==IFSelect_RetDone
        assert reader.TransferRoots()>0
        shape=reader.OneShape();assert BRepCheck_Analyzer(shape).IsValid()
        props=GProp_GProps();BRepGProp.VolumeProperties_s(shape,props)
        expected=mesh.volume*{'mm':1,'cm':1000,'in':25.4**3}[units]
        assert abs(props.Mass()-expected)<expected*1e-5,(name,props.Mass(),expected)
        assert 'STEP generado' in page.locator('#status').inner_text()
        print(f'PASS {name}: STEP WebAssembly reimportado, sólido válido y volumen conservado',flush=True)
    open_mesh=box.copy();open_mesh.update_faces(list(range(11)))
    inner=trimesh.creation.box();inner.invert()
    nested=trimesh.util.concatenate([box,inner])
    for name,mesh in [('abierta',open_mesh),('anidada',nested)]:
        source=root/f'{name}.stl';mesh.export(str(source))
        page.locator('#file').set_input_files(str(source));page.wait_for_function("!document.querySelector('#convert').disabled")
        page.locator('#convert').click();page.wait_for_function("!document.querySelector('#convert').disabled")
        assert 'STEP generado' not in page.locator('#status').inner_text()
        print(f'PASS {name}: rechazo explícito',flush=True)
    bad=root/'invalid.stl';bad.write_bytes(b'not a mesh')
    page.locator('#file').set_input_files(str(bad));page.wait_for_timeout(300)
    assert page.locator('#convert').is_disabled()
    print('PASS inválido: conversión deshabilitada',flush=True)
    assert not errors,errors
    browser.close()
    print('11 pruebas WebAssembly superadas',flush=True)
