# Conexiones de desarrollo: REA y ArtCraft

Estas herramientas no son dependencias del Visor ni se incorporan a los ZIP.
Comprobar su disponibilidad real al reanudar el trabajo: las herramientas de un
chat, los programas del entorno Linux y los del Windows del usuario son distintos.

## REA verificado el 16 de noviembre de 2026

Se recuperó una instalación existente de REA 6.8.0 en el entorno Cloud. Se conectó
un cliente MCP real mediante stdio, se enumeraron sus 229 herramientas, se llamó
`binary_session` y se inspeccionó el paquete R21 con `inspect_desktop_application`.
El diagnóstico de identidad e inventario pasó. No se instaló otro REA.

En este entorno la instalación recuperada es
`/workspace/tools/rea-6.8.0/bin/rea`; el SDK MCP ya instalado permite usarla desde
un cliente local. La evidencia de esta sesión está en
`/workspace/work/r21_repair_20261116/rea_conexion.json` y
`rea_inspeccion_r21.json`. Son rutas locales, no entregas ni pruebas en Windows.
No afirmar que REA no existe sólo porque no aparece como herramienta directa
del chat: comprobar también la instalación CLI y el transporte MCP disponible.

Para el Codex CLI de Windows, la forma de registro se comprueba con
`codex mcp add --help`; una instalación que use npx puede registrarse con:

```powershell
codex mcp add rea -- npx.cmd --yes rea-agents@6.8.0 mcp
npx.cmd --yes rea-agents@6.8.0 mcp doctor --format json
```

Eso conecta el cliente local de Windows. No proporciona acceso remoto al mismo
desde el chat Cloud. No abrir puertos públicos ni atribuir acceso al escritorio
Windows sin un canal autenticado realmente disponible.

## ArtCraft: Craft Anything conectado el 16 de noviembre de 2026

El usuario aclaró que se refiere a
[storytold/craft-anything](https://github.com/storytold/craft-anything), la
herramienta de inspección, no al editor de generación de imágenes del mismo
fabricante. La investigación previa de sesiones del editor no describe la
conexión necesaria para Craft Anything.

Se descargó la [publicación oficial v0.6.1](https://github.com/storytold/craft-anything/releases/tag/v0.6.1)
para Linux x86_64 y se contrastó el archivo con `SHA256SUMS.txt` de esa publicación:
`83ec0730c9117f399122b315c63ed4c3a8d31ac55bddd74cb8b33cd2f76ef704`.
Se conserva con sus licencias MIT/Apache-2.0 y NOTICE en una carpeta aislada:
`/workspace/tools/craft-anything-0.6.1/unpacked/craft-anything-0.6.1-linux-x86_64`.
No se añadieron dependencias al Visor ni se incluyó la herramienta en su ZIP.

Se verificó `craft-anything-cli --version` y se conectó realmente el servidor
`craft-anything-cli mcp --all-tools --deep --project RUTA.cany` con el SDK MCP ya
instalado. El servidor informó la versión 0.6.1 y enumeró **323 herramientas**.
Se hicieron llamadas reales a `core_session_show` y `core_archives_compare`
comparando los ZIP R21 original y corregido. Resultado: un archivo añadido,
cinco modificados, ninguno eliminado y 32 idénticos. Las inspecciones se limitaron
al proyecto autorizado; no se activaron reconstrucciones autónomas ni servicios
externos de pago.

La evidencia y el cliente repetible están en
`/workspace/work/r21_repair_20261116/craft_conexion.mjs`,
`craft_conexion.json` y `craft_comparacion_r21.json`. El proyecto de evidencia es
`r21.cany` dentro de esa carpeta. El cliente conserva configuración y datos
auxiliares en las carpetas locales de la herramienta mediante variables XDG.

Para un Codex CLI donde esté instalado el ejecutable, el registro equivalente es:

```text
codex mcp add craft-anything -- RUTA_AL_EJECUTABLE/craft-anything-cli mcp
```

Sustituir la ruta por la instalación real de ese equipo. En Windows, el
[ZIP portable oficial](https://github.com/storytold/craft-anything/releases/tag/v0.6.1)
incluye el CLI; su ayuda confirma los comandos `setup`, `doctor` y `mcp`.
No registrar una ruta Linux en Windows. No ejecutar `setup` indiscriminadamente
sobre todos los clientes cuando basta un registro explícito.

Las conexiones verificadas son MCP locales en el entorno Cloud, usadas mediante
un cliente programático. No son plugins nativos añadidos al catálogo del chat ni
un túnel al Windows del usuario. No afirmar que existe acceso remoto a su PC sin
un canal autenticado realmente disponible.
