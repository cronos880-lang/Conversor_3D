# Hoja de ruta del Visor

Trabajo autorizado el 11 de noviembre de 2026. Rama de desarrollo independiente
sin reescribir historial, cambiar visibilidad, licencias ni sistema de ZIP.
R19, R18 y sus validadores permanecen congelados. El desarrollo vive en `visor/`.
No se anuncia una nueva versión ni se integra una propuesta sin aprobación fría.

## 1. Superficies y contornos compartidos

Proponente general de soportes residuales planares con curvas completas de
borde, pesos racionales positivos y ajuste minimax condicionado por los bordes.
Contrasta intersecciones OCP con vecinos analíticos. Conserva las caras analíticas
por identidad y hash B-Rep y sólo permite fusionar nuevos dominios residuales.
Tolerancia B-Rep 1e-7 mm, cota de construcción 5e-8 mm. Sin relleno ni healing.

Control conocido: caja con seis superficies B-Spline coplanares residuales,
11→6 caras, conserva las cinco caras analíticas originales. Se ejecuta el
validador R19 original completo, material y puntos comunes, con certificado.
No atribuir esta reducción a Bancada. Las pruebas sintéticas se generan sin
incorporar piezas privadas. La conexión al flujo de desarrollo se consolida
con las interfaces del punto 4; la entrega R19 no cambia.

Estado de las fases posteriores: 2–3 en preparación inmediata como soporte del
punto 1; 4–12 pendientes. Los resultados exactos de pruebas se anotan al cerrar
cada fase. Windows sólo se considera validado cuando termina su ejecución nativa.

Verificación del hito 1: 3 pruebas nuevas aprobadas; batería histórica 427
aprobadas y 15 omitidas por fixtures opcionales. La ejecución inicial detectó
rutas de importación incompletas y dos fixtures R5 sin configurar; el ejecutor
ahora lee esos fixtures de entradas concretas del ZIP histórico ya existente,
sin alterar código congelado ni publicar nuevas copias de modelos.
