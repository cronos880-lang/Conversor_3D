const {chromium}=require('playwright');const fs=require('fs'),path=require('path'),crypto=require('crypto');
const root=__dirname,app=path.join(root,'prueba paquete R18 con espacios','perfeccion_Visualizador_R18','Visor_experimental_fuentes'),url='http://127.0.0.1:8781';
const digest=b=>crypto.createHash('sha256').update(b).digest('hex');const inputs=JSON.parse(fs.readFileSync(path.join(root,'ENTRADAS_SHA256.json'),'utf8'));
(async()=>{
 const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
 for(const kind of ['flame','base','body']){
  const profile='precision',page=await browser.newPage({acceptDownloads:true});const errors=[];let job;page.on('pageerror',e=>errors.push(String(e)));page.on('response',async r=>{if(r.url().endsWith('/iniciar-conversion'))try{job=(await r.json()).id}catch{}});
  const report={ok:false,extraido:app,pieza:kind,perfil:profile,inicio_utc:new Date().toISOString()},source=inputs[kind+'_stl'].path;
  try{
   for(let i=0;i<120;i++){try{if((await page.request.get(url+'/version')).ok())break}catch{}await page.waitForTimeout(500)}
   report.identidad=await(await page.request.get(url+'/version')).json();if(report.identidad.version!=='R18 experimental'||report.identidad.instancia!==digest(Buffer.from(path.resolve(app))).slice(0,20))throw Error('Servidor o versión distintos de la copia R18');
   await page.goto(url);await page.waitForFunction(()=>!document.getElementById('openBtn').disabled);report.titulo=await page.title();if(!report.titulo.includes('R18'))throw Error('Título incorrecto');
   if(await page.locator('#conversionProfile').inputValue()!=='precision')throw Error('Cambió el perfil predeterminado');await page.locator('#conversionProfile').selectOption(profile);
   await page.locator('#fileInput').setInputFiles(source);await page.waitForFunction(()=>!document.getElementById('convertBtn').disabled);const start=Date.now();await page.locator('#convertBtn').click();
   await page.waitForFunction(()=>document.getElementById('conversionPercent').textContent==='100 %'||document.getElementById('conversionPercent').classList.contains('failed'),{},{timeout:1800000});report.segundos_conversion=(Date.now()-start)/1000;
   if(await page.locator('#conversionPercent').evaluate(e=>e.classList.contains('failed')))throw Error(await page.locator('#error').innerText());
   page.once('dialog',d=>d.accept(kind+'_R18'));const [file]=await Promise.all([page.waitForEvent('download',{timeout:60000}),page.locator('#exportBtn').click({timeout:60000})]);const destination=path.join(root,'navegador_'+kind+'_R18.step');await file.saveAs(destination);
   const bytes=fs.readFileSync(destination);report.descarga_identica_backend=bytes.equals(fs.readFileSync(path.join(app,'Registros_Conversion',job+'.step')));report.sha256_step=digest(bytes);report.diagnostico=JSON.parse(fs.readFileSync(path.join(app,'Registros_Conversion',job+'.json')));report.job=job;
   const result=typeof report.diagnostico.resultado==='object'?report.diagnostico.resultado:report.diagnostico,q=result.calidad||report.diagnostico.calidad;report.calidad=q;
   if(q.perfil_validacion.id!==profile)throw Error('El perfil validado no es el seleccionado');
   const revision=kind==='body'?'r17':'r18';const response=await page.request.get(url+'/reparacion/'+job+'/'+revision+'_nucleo');if(!response.ok())throw Error('Falta la evidencia oficial '+revision);const e=await response.json();report.evidencia=e;
   if(!e.ok||e.step_sha256!==report.sha256_step||e.original_sha256!==inputs[kind+'_stl'].sha256)throw Error('La evidencia no corresponde a los archivos');
   if(e.mallado_fino.resoluciones.length!==3||e.mallado_fino.resoluciones.some(r=>!r.cerrado||!r.orientado||r.intersecciones_cgal!==0)||e.material_original.discrepancias!==0||e.material_original.banda_excluida_mm!==.002||e.detalles_original.discrepancias!==0)throw Error('Control final incompleto');
   const expected={flame:422,base:463,body:426};if(q.caras_step!==expected[kind]||q.tipos_caras.GeomAbs_Cylinder<1||q.desviacion_max_verificada_mm>.01)throw Error('La mejora no coincide con lo verificado');
   if(kind==='base'&&(e.construccion.refuerzos.length!==4||e.detalles_original.refuerzos.discrepancias!==0))throw Error('Falta conservar los cuatro refuerzos');
   if(kind==='flame'&&e.construccion.rebajes.length!==10)throw Error('Falta el vaciado profundo o alguno de los nueve grabados');
   if(kind==='body'){
    const prior=fs.readFileSync(inputs.body_step.path);report.DATA_identico_usuario=prior.subarray(prior.indexOf('DATA;')).equals(bytes.subarray(bytes.indexOf('DATA;')));
    if(!report.DATA_identico_usuario||e.construccion.rebajes.length!==9)throw Error('Body ha cambiado');
   }
   report.original_conservado=digest(fs.readFileSync(source))===inputs[kind+'_stl'].sha256;report.ok=report.descarga_identica_backend&&report.original_conservado&&errors.length===0;
   await page.screenshot({path:path.join(root,'navegador_'+kind+'_R18.png')});
  }catch(e){report.error=String(e)}finally{report.errores_js=errors;report.fin_utc=new Date().toISOString();fs.writeFileSync(path.join(root,'prueba_navegador_'+kind+'_R18.json'),JSON.stringify(report,null,2));console.log(JSON.stringify({ok:report.ok,error:report.error,pieza:kind,segundos:report.segundos_conversion}));await page.close()}
  if(!report.ok){await browser.close();process.exitCode=2;return}
 }
 await browser.close();
})().catch(e=>{console.error(e);process.exitCode=1});
