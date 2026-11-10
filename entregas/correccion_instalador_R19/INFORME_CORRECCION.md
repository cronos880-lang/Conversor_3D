# Corrección del instalador R19

El usuario muestra dos capturas del instalador detenido visualmente tras los
mensajes `Requirement already satisfied`. No muestran error ni permiten
distinguir si pip sigue activo o si ha comenzado la verificación posterior.

Se corrige un defecto verificable del instalador: ejecutaba todos los imports
nativos sin progreso, registro ni tiempo máximo. La nueva herramienta usa sólo
la biblioteca estándar de Python para supervisar procesos aislados y registra
identidad Python, `pip check`, 17 imports, la importación conjunta en el orden
original y la construcción de un sólido CAD de control.

Cada import tiene un límite de 90 segundos y muestra actividad cada cinco. Un
error muestra el mensaje original y el código nativo, sin recomendar siempre
reinstalar. Un timeout termina el proceso y sus hijos. El modo de comprobación
no instala paquetes. El instalador reutiliza la `.venv` existente; no la borra
ni la recrea en cada intento. Al aprobar el entorno, el BAT abre R19.

Los ocho tests cubren importación fallida, espera acotada con actividad, cierre
nativo, ejecutable ausente, primera librería fallida, comprobación sin instalar,
carpeta de parche incorrecta y terminación de descendientes. El último ejercita
grupos POSIX; `taskkill` requiere validación en Windows nativo.

El motor conserva la firma
`96429bbba84ee5abb202198d0a769f0f32c5a91a31989e7859d8ae0cf7276006`.
No se cambian sus Python ni las tolerancias. El ZIP R19 original se conserva
con SHA256 `99ba000c02b42734e20cfad9c4d49f5233c95b704182b432697b5888904c77ce`.
El parche modifica dos BAT, añade el comprobador, su lanzador y estas
instrucciones, y actualiza los manifiestos de la instalación resultante.

Los resultados de geometría de R19 se mantienen como resultados del motor
anterior sin modificaciones. Los nuevos tests de instalación no se suman a
ellos para atribuir una nueva validación geométrica o una ejecución Windows.
