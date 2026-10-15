import initOpenCascade from './vendor/replicad_single.js';

// Validate exact STL vertices and oriented edge pairs before sewing. Never repair silently.
export function prepareParts(positions, scale) {
  if (!positions.length || positions.length % 9 || positions.length > 180000) throw new Error('STL vacío o superior a 20.000 triángulos.');
  const vertices = [], ids = [], vertexMap = new Map(), edges = new Map();
  for (let i=0;i<positions.length;i+=3) {
    const p=Array.from(positions.slice(i,i+3),x=>x*scale);
    if (!p.every(Number.isFinite)) throw new Error('Coordenadas no válidas.');
    const key=p.join(',');
    if(!vertexMap.has(key)){vertexMap.set(key,vertices.length);vertices.push(p);}
    ids.push(vertexMap.get(key));
  }
  const faces=ids.length/3, parent=Array.from({length:faces},(_,i)=>i);
  const find=i=>{while(parent[i]!==i){parent[i]=parent[parent[i]];i=parent[i];}return i;};
  for(let f=0;f<faces;f++){
    const t=ids.slice(f*3,f*3+3);
    if(new Set(t).size!==3)throw new Error('El STL contiene triángulos degenerados.');
    const [a,b,c]=t.map(i=>vertices[i]);
    const u=b.map((x,i)=>x-a[i]),v=c.map((x,i)=>x-a[i]);
    const cross=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]];
    if(Math.hypot(...cross)<1e-14)throw new Error('El STL contiene triángulos sin área.');
    for(let k=0;k<3;k++){
      const a=t[k], b=t[(k+1)%3],key=a<b?`${a}:${b}`:`${b}:${a}`, direction=a<b?1:-1;
      if(!edges.has(key))edges.set(key,{f,count:1,direction});
      else{const edge=edges.get(key);edge.count++;edge.direction+=direction;parent[find(f)]=find(edge.f);}
    }
  }
  if([...edges.values()].some(e=>e.count!==2||e.direction!==0))throw new Error('Se requiere una malla cerrada y con orientación coherente. Repara el STL antes de convertir.');
  const groups=new Map();
  for(let f=0;f<faces;f++){const root=find(f);if(!groups.has(root))groups.set(root,[]);groups.get(root).push(f);}
  const parts=[];
  for(const group of groups.values()){
    let volume=0;const min=[Infinity,Infinity,Infinity],max=[-Infinity,-Infinity,-Infinity];
    const origin=vertices[ids[group[0]*3]];
    for(const f of group){
      const points=ids.slice(f*3,f*3+3).map(i=>vertices[i]);
      for(const p of points)for(let j=0;j<3;j++){min[j]=Math.min(min[j],p[j]);max[j]=Math.max(max[j],p[j]);}
      const [a,b,c]=points.map(p=>p.map((v,j)=>v-origin[j]));
      volume+=(a[0]*(b[1]*c[2]-b[2]*c[1])+a[1]*(b[2]*c[0]-b[0]*c[2])+a[2]*(b[0]*c[1]-b[1]*c[0]))/6;
    }
    if(Math.abs(volume)<1e-12)throw new Error('El STL no encierra un volumen válido.');
    if(parts.some(p=>min.every((v,j)=>Math.min(max[j],p.max[j])>Math.max(v,p.min[j]))))throw new Error('Componentes superpuestos o envolventes anidadas: esta versión no admite cavidades separadas.');
    const data=new ArrayBuffer(84+group.length*50),view=new DataView(data);view.setUint32(80,group.length,true);
    group.forEach((f,index)=>{
      const t=ids.slice(f*3,f*3+3);if(volume<0)[t[1],t[2]]=[t[2],t[1]];
      let offset=84+index*50+12;
      for(const id of t)for(const value of vertices[id]){view.setFloat32(offset,value,true);offset+=4;}
    });
    parts.push({data:new Uint8Array(data),volume:Math.abs(volume),min,max});
  }
  return parts;
}

self.onmessage=async ({data})=>{
  try{
    const scale={mm:1,cm:10,in:25.4}[data.units];if(!scale)throw new Error('Unidad no válida.');
    self.postMessage({status:'Validando la malla…'});
    const parts=prepareParts(new Float32Array(data.positions),scale);
    self.postMessage({status:'Cargando el motor CAD (22 MB la primera vez)…'});
    const oc=await initOpenCascade({locateFile:()=>new URL('./vendor/replicad_single.wasm',import.meta.url).href,print:()=>{},printErr:()=>{}});
    const compound=new oc.TopoDS_Compound(),builder=new oc.TopoDS_Builder();builder.MakeCompound(compound);
    const progress=new oc.Message_ProgressRange();
    const valid=shape=>{const check=new oc.BRepCheck_Analyzer(shape,true,false,false);const result=check.IsValid();check.delete();return result;};
    for(let i=0;i<parts.length;i++){
      self.postMessage({status:`Construyendo sólido ${i+1} de ${parts.length}…`});
      oc.FS.writeFile('/input.stl',parts[i].data);
      const input=new oc.TopoDS_Shape(),reader=new oc.StlAPI_Reader();
      if(!reader.Read(input,'/input.stl'))throw new Error('No se pudo leer la geometría STL.');
      const sewing=new oc.BRepBuilderAPI_Sewing(1e-7,true,true,true,false);
      sewing.Add(input);sewing.Perform(progress);
      if(sewing.NbFreeEdges()!==0)throw new Error('La malla no forma una envolvente cerrada.');
      const explorer=new oc.TopExp_Explorer(sewing.SewedShape(),oc.TopAbs_ShapeEnum.TopAbs_SHELL,oc.TopAbs_ShapeEnum.TopAbs_SHAPE);
      if(!explorer.More())throw new Error('No se pudo construir una envolvente CAD.');
      const maker=new oc.BRepBuilderAPI_MakeSolid(oc.TopoDS.Shell(explorer.Current()));
      const solid=maker.Solid();explorer.Next();
      if(explorer.More()||!valid(solid))throw new Error('El STL no produce un sólido CAD válido.');
      const unify=new oc.ShapeUpgrade_UnifySameDomain(solid,true,true,false);unify.Build();
      const result=unify.Shape();if(!valid(result))throw new Error('El sólido simplificado no es válido.');
      builder.Add(compound,result);
      explorer.delete();unify.delete();solid.delete();maker.delete();sewing.delete();reader.delete();input.delete();result.delete();
      oc.FS.unlink('/input.stl');
    }
    self.postMessage({status:'Exportando STEP y comprobando el resultado…'});
    const writer=new oc.STEPControl_Writer();
    const done=oc.IFSelect_ReturnStatus.IFSelect_RetDone;
    if(writer.Transfer(compound,oc.STEPControl_StepModelType.STEPControl_AsIs,true,progress)!==done||writer.Write('/modelo.step')!==done)throw new Error('No se pudo exportar STEP.');
    const checkReader=new oc.STEPControl_Reader();
    if(checkReader.ReadFile('/modelo.step')!==done||!checkReader.TransferRoots(progress))throw new Error('No se puede volver a abrir el STEP exportado.');
    const restored=checkReader.OneShape(),props=new oc.GProp_GProps();
    oc.BRepGProp.VolumeProperties(restored,props,true,false,false);
    const expected=parts.reduce((sum,p)=>sum+p.volume,0);
    if(!valid(restored)||Math.abs(props.Mass()-expected)>Math.max(1e-10,expected*1e-5))throw new Error('El STEP exportado no conserva un sólido válido y su volumen.');
    const bytes=oc.FS.readFile('/modelo.step');self.postMessage({result:bytes.buffer},[bytes.buffer]);
  }catch(error){self.postMessage({error:typeof error==='number'?'El motor CAD rechazó esta geometría.':error.message||String(error)});}
};
