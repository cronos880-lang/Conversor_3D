const {test} = require('node:test');
const assert = require('node:assert/strict');
const view = require('../src/conversor3d/resources/viewer/presentation.js');

test('only a downloaded STEP completes progress; elapsed time does not advance it', () => {
  assert.deepEqual(view.reportedProgress(15, {porcentaje:15, segundos:600}), {percent:15, kind:'running'});
  assert.equal(view.reportedProgress(15, {porcentaje:2}).percent, 15);
  assert.deepEqual(view.reportedProgress(92, {porcentaje:100, estado:'terminado'}), {percent:99, kind:'downloading'});
  assert.deepEqual(view.reportedProgress(99, {estado:'error'}), {percent:99, kind:'failed'});
  assert.deepEqual(view.reportedProgress(15, {estado:'cancelado'}), {percent:15, kind:'cancelled'});
  assert.deepEqual(view.reportedProgress(99, {estado:'terminado'}, true), {percent:100, kind:'complete'});
  assert.equal(view.reportedProgress(0, {porcentaje:'invalid'}).percent, 0);
});

function triangle(a, b, c) {
  const u=b.map((v,i)=>v-a[i]), v=c.map((x,i)=>x-a[i]);
  const n=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]];
  const length=Math.hypot(...n);
  return [a,b,c].flatMap(p=>[...p,...n.map(x=>x/length)]);
}

test('lighting normals smooth a shallow curve while retaining every display vertex exactly', () => {
  const angle=.2, cosine=Math.cos(angle), sine=Math.sin(angle);
  const data=new Float32Array([
    ...triangle([0,0,0],[0,1,0],[-1,0,0]),
    ...triangle([0,0,0],[cosine,0,-sine],[0,1,0]),
  ]);
  const before=data.slice();
  assert.equal(view.smoothNormals(data).applied,true);
  for(let i=0;i<data.length;i+=6) for(let k=0;k<3;k++) assert.equal(data[i+k],before[i+k]);
  assert.ok(data[3]>0 && data[3]<sine, 'shared vertex gets an interpolated lighting normal');
  assert.ok(Math.abs(Math.hypot(...data.slice(3,6))-1)<1e-6);
});

test('a sharp box edge retains flat normals and large meshes retain the bounded fallback', () => {
  const data=new Float32Array([
    ...triangle([0,0,0],[1,0,0],[0,1,0]),
    ...triangle([0,0,0],[0,0,1],[1,0,0]),
  ]);
  const before=data.slice();
  view.smoothNormals(data);
  assert.deepEqual(data,before);
  assert.deepEqual(view.smoothNormals(data,1),{applied:false,reason:'budget'});
  assert.deepEqual(data,before);
});

test('rendering and framing respect GPU limits and include all model corners', () => {
  const [w,h]=view.renderSize(1880,900,1,4096);
  assert.ok(w>1880 && h>900 && w<=4096 && h<=4096);
  const limited=view.renderSize(10000,5000,3,4096);
  assert.ok(limited.every(v=>v<=4096));
  const right=[1,0,0], up=[0,0,1], back=[0,-1,0], size=[40,10,2], aspect=.7;
  const distance=view.frameDistance(size,aspect,right,up,back), scale=3/40;
  for(const x of [-1,1])for(const y of [-1,1])for(const z of [-1,1]){
    const p=[x*size[0]*scale/2,y*size[1]*scale/2,z*size[2]*scale/2];
    const depth=distance+p[1];
    assert.ok(Math.abs(p[0])<depth*Math.tan(Math.PI/8)*aspect);
    assert.ok(Math.abs(p[2])<depth*Math.tan(Math.PI/8));
  }
});
