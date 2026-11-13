# R21 experimental — ACTUALIZACIÓN ligera para R20

## Entrega e instalación

Necesita R20 instalada con su entorno Python 3.12 x64 preparado. El paquete
contiene el código propio R21, recursos, lanzadores, instrucciones y manifiestos;
reutiliza las dependencias R20 y las 357 fuentes congeladas R19 sin modificarlas.
No contiene runtimes, modelos del usuario ni otra copia del motor histórico.

[Descarga directa](https://github.com/cronos880-lang/Conversor_3D/blob/perfeccion_Visualizador_R21/entregas/perfeccion_Visualizador_R21/Conversor_3D_R21_ACTUALIZACION_LIGERA.zip?raw=true)

1. Descomprimir todo en una carpeta nueva junto a `Conversor_3D_R20_experimental`.
2. Abrir `Iniciar_R21.bat`. Si se solicita, seleccionar la carpeta R20 existente.
3. Para verificar el entorno sin abrir el Visor, usar `Diagnostico_R21.bat`.

No extraer dentro de R20. Los datos propios van en `datos` dentro de R21. Para
volver a R20, cerrar R21 y abrir su lanzador original. Si R20 no tiene un entorno
válido, utilizar su `Reparar_Entorno_R20.bat`; R21 no instala dependencias.

- Archivo: `Conversor_3D_R21_ACTUALIZACION_LIGERA.zip`.
- Tamaño: **83.795 bytes**, 37 archivos.
- SHA-256: `0e1778d70e371ae697447e42989f201264ba31f08fe939b88b1b9f1ddb573900`.
- Versión: `21.0.0`, puerto propio `8785`.
- [Commit de fuentes probado](https://github.com/cronos880-lang/Conversor_3D/commit/583f73e7376cf1acd08518cc06f160cb6e3a9505).
- El manifiesto del ZIP registra ese commit, árbol limpio y hash de cada archivo.

## Mejora demostrada y límites

Se evita repetir propuestas que no pueden cambiar una referencia ya analítica y
se aprovecha un certificado completo generado dentro de la misma conversión,
tras verificarlo con el verificador congelado. Para una reconversión idéntica se
recupera sólo la geometría de referencia: **siempre se ejecuta otro control frío
completo**, con un nonce nuevo, antes de usarla. No se almacenan certificados en
la caché ni se trasladan aprobaciones entre conversiones.

Se mantienen los perfiles, los cuatro botones y los controles de geometría,
material, tres mallados y STEP final. Se incluyen las mejoras de presentación y
progreso del desarrollo posterior a R20. Los fallos del motor tienen etapa,
código nativo y registros; el problema concreto del PC Windows del usuario no se
declara resuelto sin reproducirlo en ese equipo.

### Bancada Motor real

Mediciones locales Linux, con otras pruebas en curso; no son una promesa de
tiempo en el PC Windows del usuario.

| Conversión | Tiempo total | Caras | Sólidos | Tolerancia B-Rep máxima |
|---|---:|---:|---:|---:|
| R20, primera | 892,2 s | 101 | 1 | 1e-7 mm |
| Desarrollo R21, primera | 891,3 s | 101 | 1 | 1e-7 mm |
| R21, repetida con control frío nuevo | 77,7 s | 101 | 1 | 1e-7 mm |

La repetida tardó unas 11,5 veces menos que la primera del desarrollo R21. Su
control frío nuevo consumió 68,2 s; no es simplemente entregar un archivo guardado.
Los STEP de esas dos conversiones son idénticos byte por byte:
`61d025a44bac16e9258876941452df01ee3649e29f9c574eac7368f0c9ec4217`.
Sus nonces son distintos. En las tres salidas: material sin discrepancias, tres
mallados comprobados, B-Rep válido, desviación máxima medida de 0,003438 mm y
53 planos, 18 cilindros, 18 B-Spline y 12 superficies de extrusión.

**La primera conversión sigue siendo lenta. No se han reducido las 101 caras ni
mejorado su precisión en esta entrega.** No confundir tolerancia topológica B-Rep
de `1e-7 mm` con la distancia geométrica entre el STL y el STEP.

### Ocho piezas distintas

Se completaron 24 conversiones reales (R20 primera, desarrollo primera y repetida)
con cajas, cilindros, cilindro rotado, perfil L, escalón, taladro pequeño, dos
taladros y pared fina. Todas conservaron caras, desviación medida y material, con
tres mallados y tolerancia máxima `1e-7 mm`. La tabla está también en
[`visor/docs/R21_INFORME.md`](../../visor/docs/R21_INFORME.md).

| Pieza | R20 primera | Mejora primera | Mejora repetida | Caras |
|---|---:|---:|---:|---:|
| Caja | 30,14 s | 29,31 s | 6,04 s | 6 |
| Cilindro | 33,95 s | 29,15 s | 6,38 s | 3 |
| Perfil L | 20,70 s | 15,63 s | 3,38 s | 8 |
| Cilindro rotado | 43,61 s | 20,30 s | 4,50 s | 3 |
| Taladro pequeño | 47,91 s | 40,76 s | 10,99 s | 7 |
| Escalón | 32,71 s | 27,82 s | 5,99 s | 8 |
| Pared fina | 38,19 s | 29,29 s | 5,64 s | 10 |
| Dos taladros | 22,41 s | 16,94 s | 4,43 s | 8 |

Las mediciones se tomaron con carga variable. Comparan estas ejecuciones concretas;
no garantizan el mismo porcentaje de mejora en toda pieza o equipo.

Se hicieron además **ocho reconversiones R20 con su caché de análisis ya preparada**,
para no comparar solamente contra R20 en frío. Sumaron 176,99 s frente a 47,36 s
de las ocho reconversiones del desarrollo mejorado (unas 3,7 veces menos en esta
medición). Todas las ocho salidas adicionales R20 pasaron los controles completos,
con las mismas caras, cero discrepancias de material y tres mallados. El conjunto
de esta comparación comprende 32 conversiones reales; la carga del equipo varió
entre tandas, por lo que no se promete un factor universal.

## Pruebas y conservación

- Pruebas actuales locales: **57 aprobadas**.
- Batería histórica local: **427 aprobadas y 15 omitidas** según sus condiciones.
- Los 357 hashes R19 y la reglamentación general V2.3.1 permanecen intactos.
- Se probó que una geometría de caché alterada, incluso con hashes recalculados,
  se rechaza mediante control frío y vuelve al cálculo R19.
- El ZIP final se extrae en una ruta con espacios y arranca usando el entorno
  real R20: dos conversiones HTTP, STEP reimportado válido, certificados nuevos
  y bytes de versión R20 conservados.
- Prueba real de navegador Chromium sobre ese ZIP final: importar STL, convertir,
  progreso completo al 100 %, exportar el STEP y conservar los cuatro botones,
  sin errores JavaScript. El STEP descargado se reimportó: sólido válido de seis
  caras y 120 mm³.
- [Pruebas nativas de las fuentes R21 en GitHub Actions](https://github.com/cronos880-lang/Conversor_3D/actions/runs/43460470807).

**Resultado nativo final: aprobado en Windows y Linux**, para el commit de fuentes
indicado. Linux: 57 pruebas actuales, 427 históricas aprobadas y 15 omitidas.
Windows: 57 actuales, 426 históricas aprobadas y 16 omitidas. Las omisiones son
las condiciones existentes de la batería; no se alteraron sus pruebas.

Windows completó también la carpeta portable, las conversiones nativas, la
instalación y reparación reales de R20 y el arranque de R21 mediante su `.bat`
con espacios en las rutas. La actualización hizo dos conversiones con certificados
nuevos, STEP válidos y R20 intacta. El log termina con:
`R21 LIGERA: ARRANQUE, DOS CONVERSIONES Y STEP VALIDOS; R20 INTACTA`.

Windows CI y Linux no sustituyen la prueba en el PC del usuario ni una importación en
SolidWorks, Inventor u Onshape. No hay dependencias nuevas; el conversor web,
sus automatizaciones y los ZIP históricos no se modifican.

Los resultados numéricos sin modelos privados se incluyen en
[`RESULTADOS.json`](RESULTADOS.json).

## Investigación geométrica no incorporada

Un prototipo aislado obtuvo cinco caras analíticas en una pieza de revolución
que la referencia dejaba muy facetada. El evaluador congelado lo rechazó porque
la referencia carece de cilindros comparables para el contraste de recortes.
No se incorpora esa ruta, no se cambia el evaluador y no se presenta como una
mejora geométrica aceptada. Reducir caras y mejorar la primera reconstrucción
siguen siendo los siguientes objetivos técnicos.

Se utilizaron Python, OCP/CadQuery, las bibliotecas ya bloqueadas, Git y GitHub
Actions; también se revisó la estrategia de SolidCraft. REA y ArtCraft no están
conectados en este entorno; Godot no aporta al cálculo B-Rep y Rust no se integra
ni se instala como dependencia nueva. La entrega sigue siendo experimental y
no implica aprobación oficial del usuario.
