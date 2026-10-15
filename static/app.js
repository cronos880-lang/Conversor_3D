import * as THREE from 'three';
import { OrbitControls } from './vendor/OrbitControls.js';
import { STLLoader } from './vendor/STLLoader.js';
const $ = id => document.getElementById(id);
const container = $('view'), status = $('status');
let renderer;
try { renderer = new THREE.WebGLRenderer({antialias:true}); }
catch { status.textContent='Este navegador no permite WebGL. Actívalo para visualizar el objeto.'; throw new Error('WebGL unavailable'); }
renderer.setPixelRatio(Math.min(devicePixelRatio,2)); container.append(renderer.domElement);
const scene = new THREE.Scene(); scene.background=new THREE.Color('#111820');
const camera=new THREE.PerspectiveCamera(45,1,.01,100000);
const controls=new OrbitControls(camera,renderer.domElement); controls.enableDamping=true;
scene.add(new THREE.HemisphereLight(0xffffff,0x47586b,3));
const light=new THREE.DirectionalLight(0xffffff,3); light.position.set(3,5,4); scene.add(light);
let object, selected, busy=false, generation=0, radius=10;
function fit(){controls.target.set(0,0,0); const dist=radius/Math.sin(THREE.MathUtils.degToRad(22.5))/Math.min(1,camera.aspect)*1.15; camera.position.set(dist*.65,dist*.45,dist);camera.near=Math.max(radius/1000,1e-6);camera.far=dist*20;camera.updateProjectionMatrix();controls.update();}
function clear(){if(!object)return;scene.remove(object);object.traverse(x=>{x.geometry?.dispose();if(x.material)x.material.dispose();});object=null;}
new ResizeObserver(()=>{const w=container.clientWidth,h=container.clientHeight;renderer.setSize(w,h);camera.aspect=w/h;camera.updateProjectionMatrix();}).observe(container);
$('file').addEventListener('change',async e=>{const ticket=++generation;selected=null;$('convert').disabled=true;clear();const file=e.target.files[0];if(!file)return;if(file.size>20*1024*1024){status.textContent='Máximo 20 MB.';return;}
try{const geometry=new STLLoader().parse(await file.arrayBuffer());if(ticket!==generation)return;const positions=geometry.getAttribute('position');if(!positions?.count||positions.count/3>20000||!Array.from(positions.array).every(Number.isFinite))throw new Error('STL vacío, no válido o superior a 20.000 triángulos.');geometry.computeBoundingSphere();if(!(geometry.boundingSphere.radius>0))throw new Error('El modelo no tiene dimensiones.');geometry.center();geometry.computeVertexNormals();radius=geometry.boundingSphere.radius;object=new THREE.Group();object.add(new THREE.Mesh(geometry,new THREE.MeshStandardMaterial({color:0x67b7ee,metalness:.15,roughness:.55,side:THREE.DoubleSide})));object.add(new THREE.LineSegments(new THREE.EdgesGeometry(geometry,25),new THREE.LineBasicMaterial({color:0x173653})));scene.add(object);fit();selected=file;$('convert').disabled=busy;status.textContent=`${file.name}\n${positions.count/3} triángulos. Listo para validar y convertir.`;}catch(error){if(ticket===generation)status.textContent=error.message;}});
$('fit').onclick=fit;$('wire').onclick=()=>{if(object)object.children[1].visible=!object.children[1].visible;};
$('convert').onclick=async()=>{if(!selected||busy)return;busy=true;$('convert').disabled=true;$('file').disabled=true;status.textContent='Validando sólido y convirtiendo…';const file=selected;try{const body=new FormData();body.append('file',file);body.append('units',$('units').value);const response=await fetch('/api/convert',{method:'POST',body});if(!response.ok){const error=await response.json();throw new Error(typeof error.detail==='string'?error.detail:'Error al convertir.');}const url=URL.createObjectURL(await response.blob());const a=document.createElement('a');a.href=url;a.download=file.name.replace(/\.stl$/i,'')+'.step';a.click();setTimeout(()=>URL.revokeObjectURL(url),10000);status.textContent='STEP generado y sólido validado. Descarga iniciada.';}catch(error){status.textContent=error.message;}finally{busy=false;$('file').disabled=false;$('convert').disabled=!selected;}};
fit();renderer.setAnimationLoop(()=>{controls.update();renderer.render(scene,camera);});
