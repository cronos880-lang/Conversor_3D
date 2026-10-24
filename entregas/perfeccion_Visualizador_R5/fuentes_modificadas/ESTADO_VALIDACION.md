# R5 experimental: progreso de reparación, validación CAD independiente

No es una actualización estable. Una malla regularizada no se presenta como STEP
aprobado. El informe de esta entrega recoge los resultados reales y las pruebas
pendientes, incluidos los rechazos.

El reparador trata solo una clase concreta de contactos en STL cerrados y
orientados. Obtiene la frontera de material de número de giro positivo, separa
las incidencias locales y verifica los contactos con predicados exactos.
Solo actúa sobre contactos geométricos preexistentes: no une cuerpos por cercanía
ni elimina cuerpos pequeños. La regularización local se contrasta contra la
frontera obtenida: máximo 0,002 mm, volumen 0,001 % y cotas 0,002 mm.
También se mide el STL original completo y se mantiene su límite superficial.
No se ocultan las superficies internas retiradas al resolver las intersecciones.

Las rutas sanas conservan su comportamiento. Los cambios del núcleo CAD están
condicionados a entradas reparadas verificadas: lectura exacta, protección local
y conservación de shells de cavidades. Un STEP debe pasar reimportación,
medidas, superficies y ausencia de interferencias; si falla no se ofrece como
conversión terminada. Las distancias y la ocupación de material se muestrean;
no constituyen una prueba Hausdorff global.

La prueba de navegador Linux corresponde al servidor Python local. No certifica
Windows, WebAssembly, edición Move face en Onshape ni impresión física K1C.
