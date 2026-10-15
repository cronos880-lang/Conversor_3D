from pathlib import Path
from tempfile import gettempdir
from playwright.sync_api import sync_playwright
import trimesh
trimesh.creation.box((2,3,4)).export(str(Path(gettempdir()) / 'browser-box.stl'))
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
    page=browser.new_page(accept_downloads=True)
    errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto('http://127.0.0.1:8001')
    page.locator('#file').set_input_files(str(Path(gettempdir()) / 'browser-box.stl'))
    page.wait_for_function("document.querySelector('#status').textContent.includes('Listo')")
    page.mouse.move(700,300);page.mouse.down();page.mouse.move(800,350,steps=10);page.mouse.up()
    page.mouse.wheel(0,200)
    page.locator('#fit').click();page.locator('#wire').click()
    with page.expect_download(timeout=60000) as event:
        page.locator('#convert').click()
    download=event.value
    assert download.suggested_filename=='browser-box.step'
    download.save_as(str(Path(gettempdir()) / 'browser-box.step'))
    assert 'STEP generado' in page.locator('#status').inner_text()
    assert not errors,errors
    page.screenshot(path=str(Path(gettempdir()) / 'conversor.png'))
    print('Browser: STL upload, WebGL, orbit, zoom, fit, edges and STEP download passed')
    browser.close()
