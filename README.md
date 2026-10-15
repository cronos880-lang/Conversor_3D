# Conversor 3D: STL → STEP

Aplicación con interfaz HTML en español. Carga STL binario o ASCII, visualiza la pieza con giro, zoom, desplazamiento, centrado y aristas, y descarga un STEP generado con Open CASCADE. Three.js está incluido: el visor no necesita una CDN.

## Abrir el programa

Requiere **Python 3.12 de 64 bits**, navegador con WebGL y conexión durante la primera instalación. Descarga el repositorio, descomprime y ejecuta:

```sh
python iniciar.py
```

En Windows puedes abrir `Iniciar.bat` con doble clic. Instala las dependencias en `.venv` y abre el navegador automáticamente. Mantén la consola abierta; para terminar, pulsa Ctrl+C. La instalación CAD ocupa varios cientos de MB.

La interfaz es HTML, pero la conversión necesita el servidor Python local. Abrir `static/index.html` directamente o alojarlo en GitHub Pages no ejecuta la conversión. No se ha desplegado un servicio público.

## Qué convierte realmente

STL contiene triángulos, no el diseño original. Se construyen sólidos B-rep, se unen caras coplanares y se exporta STEP; cada resultado se vuelve a importar, se valida y se comprueba su volumen antes de entregarlo. El archivo permite edición directa de geometría en aplicaciones CAD que importen STEP.

**No recupera historial paramétrico, cotas, restricciones, cilindros ni curvas originales. Las curvas quedan facetadas como en el STL. No existe garantía de conversión perfecta de cualquier STL.** La compatibilidad específica con Onshape y Autodesk requiere importar el resultado en esos productos; todavía no se ha probado allí.

Límites: 20 MB, 20.000 triángulos; malla cerrada, con volumen y orientación coherente. No repara automáticamente archivos. Se rechazan componentes cuyas cajas envolventes se superponen (incluye envolventes anidadas y algunas piezas separadas de geometría compleja) para evitar rellenar cavidades por error. La validación topológica y de volumen no garantiza detectar todas las autointersecciones. Las unidades de entrada se eligen explícitamente porque STL no las declara; el STEP se exporta en milímetros. Los controles del visor solo cambian la vista, no las coordenadas exportadas.

Los STL se procesan en el equipo que ejecuta el servidor y los archivos temporales de conversión se eliminan al terminar. Sin cuentas, claves API ni servicios externos. El servidor de desarrollo escucha solo en el equipo local por defecto; no está preparado para un servicio público con usuarios no confiables.

## Desarrollo y pruebas

```sh
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pytest -q
.venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 8001
```

En Windows usa `.venv\Scripts\python.exe`. Las pruebas convierten caja, cilindro, esfera y varias piezas, vuelven a abrir el STEP y comparan volumen. Incluyen unidades, conversiones repetidas, STL ASCII, mallas abiertas, archivos inválidos, cavidades no soportadas y tamaño excesivo.

Prueba opcional de navegador, con el servidor en el puerto 8001:

```sh
.venv/bin/python -m pip install playwright==1.64.0
.venv/bin/python tests/browser_smoke.py
```

Ese script utiliza Chromium instalado en `/usr/bin/chromium` (entorno Linux de desarrollo), carga una pieza de prueba, maneja el visor y verifica la descarga. No implica validación en otros navegadores o sistemas operativos.
