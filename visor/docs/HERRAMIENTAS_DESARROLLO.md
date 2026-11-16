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

## ArtCraft: conexión aún no acreditada

Se buscaron REA y ArtCraft en el catálogo de plugins disponible y no aparecieron
resultados. Ese catálogo no es exhaustivo; puede consultarse también el
[directorio de plugins](https://chatgpt.com/plugins).

Se revisaron los repositorios oficiales de [ArtCraft](https://github.com/storytold/artcraft)
y [sus servicios](https://github.com/storytold/artcraft-services). Las fuentes de
sesiones MCP existen, pero crear una sesión requiere una cuenta autenticada
mediante API key o sesión web. Eso no demuestra que exista un servidor MCP
público utilizable ni que este chat tenga acceso a la cuenta del usuario.

Referencia verificada: [creación de sesión MCP autenticada](https://github.com/storytold/artcraft-services/blob/4c72ed543753f4ef71d75691e3c106c294b77cbd/crates/service/web/storyteller_web/src/http_server/endpoints/mcp_sessions/create_mcp_session_handler.rs).

No inventar una URL MCP, una herramienta, una cuenta conectada ni claves.
Mantener pendiente la conexión hasta disponer de la instalación/servicio
concreto, su transporte documentado y la autenticación correspondiente. No
solicitar contraseñas ni claves en el chat; usar los mecanismos de conexión o
secretos del entorno cuando estén disponibles. No activar generación de pago.
