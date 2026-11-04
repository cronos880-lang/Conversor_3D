const {chromium}=require('playwright');const fs=require('fs'),path=require('path'),crypto=require('crypto');
const root=__dirname,app=path.join(root,'prueba paquete R17 con espacios','perfeccion_Visualizador_R17','Visor_experimental_fuentes'),url='http://127.0.0.1:8780';
const digest=b=>crypto.createHash('sha256').update(b).digest('hex');const inputs=JSON.parse(fs.readFileSync(path.join(root,'ENTRADAS_SHA256.json'),'utf8'));
(async()=>{
 const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
 for(const [kind,profile]of [['body','precision'],['guia','impresion']]){
  const page=await browser.newPage({acceptDownloads:true});const errors=[];let job;page.on('pageerror',e=>errors.push(String(e)));page.on('response',async r=>{if(r.url().endsWith('/iniciar-conversion'))try{job=(await r.json()).id}catch{}});
  const report={ok:false,extraido:app,pieza:kind,perfil:profile,inicio_utc:new Date().toISOString()},source=inputs[kind+'_stl'].path;
  try{
   for(let i=0;i<120;i++){try{if((await page.request.get(url+'/version')).ok())break}catch{}await page.waitForTimeout(500)}
   report.identidad=await(await page.request.get(url+'/version')).json();if(report.identidad.version!=='R17 experimental'||report.identidad.instancia!==digest(Buffer.from(path.resolve(app))).slice(0,20))throw Error('Servidor o versión distintos de la copia R17');
   await page.goto(url);await page.waitForFunction(()=>!document.getElementById('openBtn').disabled);report.titulo=await page.title();if(!report.titulo.includes('R17'))throw Error('Título incorrecto');
   if(await page.locator('#conversionProfile').inputValue()!=='precision')throw Error('Cambió el perfil predeterminado');await page.locator('#conversionProfile').selectOption(profile);
   await page.locator('#fileInput').setInputFiles(source);await page.waitForFunction(()=>!document.getElementById('convertBtn').disabled);const start=Date.now();await page.locator('#convertBtn').click();
   await page.waitForFunction(()=>document.getElementById('conversionPercent').textContent==='100 %'||document.getElementById('conversionPercent').classList.contains('failed'),{},{timeout:1800000});report.segundos_conversion=(Date.now()-start)/1000;
   if(await page.locator('#conversionPercent').evaluate(e=>e.classList.contains('failed')))throw Error(await page.locator('#error').innerText());
   page.once('dialog',d=>d.accept(kind+'_R17'));const [file]=await Promise.all([page.waitForEvent('download',{timeout:60000}),page.locator('#exportBtn').click({timeout:60000})]);const destination=path.join(root,'navegador_'+kind+'_R17.step');await file.saveAs(destination);
   const bytes=fs.readFileSync(destination);report.descarga_identica_backend=bytes.equals(fs.readFileSync(path.join(app,'Registros_Conversion',job+'.step')));report.sha256_step=digest(bytes);report.diagnostico=JSON.parse(fs.readFileSync(path.join(app,'Registros_Conversion',job+'.json')));report.job=job;
   const result=typeof report.diagnostico.resultado==='object'?report.diagnostico.resultado:report.diagnostico;const q=result.calidad||report.diagnostico.calidad;report.calidad=q;
   if(q.perfil_validacion.id!==profile)throw Error('El perfil validado no es el seleccionado');
   if(kind==='body'){
    const response=await page.request.get(url+'/reparacion/'+job+'/r17_nucleo');if(!response.ok())throw Error('Falta el registro oficial completo R17');report.evidencia_r17=await response.json();const e=report.evidencia_r17;
    if(!e.ok||e.step_sha256!==report.sha256_step||e.original_sha256!==inputs.body_stl.sha256)throw Error('La evidencia no corresponde a los archivos');
    if(q.caras_step>=1000||q.tipos_caras.GeomAbs_Cylinder<4||q.desviacion_max_verificada_mm>.01||e.construccion.rebajes.length!==9||e.detalles_original.puntos!==780||e.detalles_original.discrepancias!==0)throw Error('La mejora o los detalles no coinciden con lo esperado');
    report.control_r17_aprobado=true;
   }else{
    const prior=fs.readFileSync(path.join(root,'referencia_R16','guia.step'));report.DATA_identico_R16=prior.subarray(prior.indexOf('DATA;')).equals(bytes.subarray(bytes.indexOf('DATA;')));
    if(!report.DATA_identico_R16||q.caras_step!==248)throw Error('La guía ha cambiado sin una mejora aprobada');
   }
   report.original_conservado=digest(fs.readFileSync(source))===inputs[kind+'_stl'].sha256;report.ok=report.descarga_identica_backend&&report.original_conservado&&errors.length===0;
   await page.screenshot({path:path.join(root,'navegador_'+kind+'_R17.png')});
  }catch(e){report.error=String(e)}finally{report.errores_js=errors;report.fin_utc=new Date().toISOString();fs.writeFileSync(path.join(root,'prueba_navegador_'+kind+'_R17.json'),JSON.stringify(report,null,2));console.log(JSON.stringify({ok:report.ok,error:report.error,pieza:kind,segundos:report.segundos_conversion}));await page.close()}
  if(!report.ok){await browser.close();process.exitCode=2;return}
 }
 await browser.close();
})().catch(e=>{console.error(e);process.exitCode=1});
