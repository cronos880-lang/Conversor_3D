/* Display helpers only: no source vertices, STL bytes or CAD tolerances change. */
(function (root) {
  'use strict';
  const dot = (a, b) => a[0]*b[0] + a[1]*b[1] + a[2]*b[2];

  function reportedProgress(previous, state, downloaded = false) {
    const value = Number(state.porcentaje);
    const last = Number.isFinite(previous) ? Math.max(0, Math.min(99, previous)) : 0;
    const percent = downloaded ? 100 : Math.max(last, Number.isFinite(value) ? Math.max(0, Math.min(99, value)) : 0);
    const kind = downloaded ? 'complete' : state.estado === 'error' ? 'failed'
      : ['cancelado', 'cancelando'].includes(state.estado) ? 'cancelled'
      : state.estado === 'terminado' ? 'downloading' : 'running';
    return {percent, kind};
  }

  function renderSize(width, height, dpr, maxSize = 8192) {
    const ratio = Math.min(Math.max(Number(dpr) || 1, 1.5), 2,
      Math.max(1, Math.sqrt(8000000 / Math.max(1, width*height))),
      maxSize/Math.max(1, width), maxSize/Math.max(1, height));
    return [Math.max(1, Math.round(width*ratio)), Math.max(1, Math.round(height*ratio))];
  }

  function frameDistance(size, aspect, right, up, back) {
    const scale = 3/Math.max(...size);
    const tanY = Math.tan(Math.PI/8), tanX = tanY*Math.max(.1, aspect);
    let distance = .6;
    for (const x of [-1, 1]) for (const y of [-1, 1]) for (const z of [-1, 1]) {
      const p = [x*size[0]*scale/2, y*size[1]*scale/2, z*size[2]*scale/2];
      distance = Math.max(distance, dot(p, back) + 1.22*Math.max(Math.abs(dot(p,right))/tanX, Math.abs(dot(p,up))/tanY) + .1);
    }
    return distance;
  }

  function smoothNormals(data, maxTriangles = 200000) {
    if (data.length/18 > maxTriangles) return {applied: false, reason: 'budget'};
    const vertices = new Map(), threshold = Math.cos(35*Math.PI/180);
    const key = i => `${data[i]},${data[i+1]},${data[i+2]}`;
    // Group exact display coordinates only. No welding, quantization or averaging of positions.
    for (let i = 0; i < data.length; i += 18) {
      const a = [data[i+6]-data[i], data[i+7]-data[i+1], data[i+8]-data[i+2]];
      const b = [data[i+12]-data[i], data[i+13]-data[i+1], data[i+14]-data[i+2]];
      const cross = [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]];
      const weight = Math.hypot(...cross);
      if (weight < 1e-20) continue;
      const normal = cross.map(v => v/weight);
      for (const corner of [i, i+6, i+12]) {
        const k = key(corner), bucket = vertices.get(k) || [];
        if (!vertices.has(k)) vertices.set(k, bucket);
        const group = bucket.find(g => dot(g.normal, normal) > 1-1e-8);
        if (group) group.weight += weight;
        else {
          // Bound pathological coincident input. Keep the original flat normals on refusal.
          if (bucket.length >= 32) return {applied: false, reason: 'directions'};
          bucket.push({normal, weight});
        }
      }
    }
    for (let i = 0; i < data.length; i += 6) {
      const normal = [data[i+3], data[i+4], data[i+5]], sum = [0,0,0];
      for (const g of vertices.get(key(i)) || []) {
        if (dot(normal,g.normal) >= threshold) for (let k=0;k<3;k++) sum[k] += g.normal[k]*g.weight;
      }
      const length = Math.hypot(...sum);
      if (length > 1e-20) for (let k=0;k<3;k++) data[i+3+k] = sum[k]/length;
    }
    return {applied: true};
  }

  const api = {reportedProgress, renderSize, frameDistance, smoothNormals};
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.VisorPresentation = Object.freeze(api);
})(globalThis);
