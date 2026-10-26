# Avance del motor después de R7 · 26/10/2026

**No hay una nueva versión para instalar.** Se guardan código y resultados reales; la actualización queda bloqueada por la pérdida de superficies CAD en Bancada_Motor y por comprobaciones externas inconclusas.

[Leer el informe completo](./INFORME_AVANCE_MOTOR.md) · [Revisar el código modificado](./codigo_modificado/) · [Parche frente a R7](./CAMBIOS_DESARROLLO.patch) · [Puertas de entrega](./PUERTAS_DE_ENTREGA.json).

Las mejoras generales del preprocesador ya resuelven tres STL antes rechazados, sin cambiar las tolerancias: cavidades cerradas del Lego, costuras en T del soporte móvil y redundancias verificadas de PEGS. Los STEP pasan relectura, geometría, topología, OCC en frío y CGAL; la interfaz completa también se ha probado. PEGS usa recuperación facetada.

STEP para comprobar por separado, sin actualizar el programa:

- [Lego 4×2](./STEP_verificados/V_legoBrick4x2.step?raw=true).
- [Soporte móvil](./STEP_verificados/Soporte_movil_2.step?raw=true).
- [Technic PEGS](./STEP_verificados/Technic_PEGS_Cross_x6_A.step?raw=true).
- [Control del estante que ya funcionaba](./STEP_verificados/Soportes_estante_bobinas_v0.step?raw=true).

Código, datos y pruebas reproducibles, divididos por tamaño:

1. [Descargar código y evidencias principales — 65 MB](./Avance_motor_CODIGO_Y_EVIDENCIAS_NO_ACTUALIZACION.zip?raw=true).
2. [Descargar banco externo de auditoría — 54 MB](./Banco_externo_AUDITORIA_NO_ACTUALIZACION.zip?raw=true).

Para consultar toda la auditoría, extraer ambos ZIP en la misma carpeta. Comparten la raíz avance_desarrollo_post_R7; el archivo principal incluye las instrucciones para desarrolladores. No contienen un instalador nuevo. Los dos ZIP pasaron CRC, extracción y contraste de todos los SHA256; los valores exactos están en [VALIDACION_PAQUETE.json](./VALIDACION_PAQUETE.json).

Resultados: 144 pruebas automáticas distintas aprobadas; 25 pruebas afectadas repetidas tras aplicar el parche a una copia limpia. Cubo 4/4; 21 conversiones de regresión completadas y 20 DATA STEP idénticos a R7. Bancada convierte, pero pasa de 89 caras CAD y 25 cilindros a 6.277 planos: no se da esa pérdida por resuelta. Banco externo: 19 conversiones completadas; 16 contrastes completos aprobados, dos con salida aprobada y STL fuera de calibración, uno inconcluso y una conversión interrumpida por tiempo. Los intentos descartados están identificados.

6558 conserva DATA idéntico a R7. Las líneas que observa el usuario en Onshape siguen pendientes. Windows nativo, Onshape y WebAssembly no se han validado en esta sesión. La web de main y las entregas R7 anteriores permanecen intactas.

El repositorio es privado: para descargar, iniciar sesión con la cuenta que tenga acceso. Conservar la instalación actual.
