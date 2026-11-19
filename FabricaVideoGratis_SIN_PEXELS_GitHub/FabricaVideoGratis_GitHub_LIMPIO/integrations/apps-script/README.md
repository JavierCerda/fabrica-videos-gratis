# Conexión opcional de Google, pendiente de autorización

Preparada para la cuenta del propietario y el canal JMDopamine
(`UCuMX_olnpHMCr06FQBdCzjQ`). No sustituye una sesión de YouTube Studio
por OAuth: exige una autorización de Google independiente.

`Code.gs` y `appsscript.json` son el código revisable que se instala en un
proyecto de Apps Script propiedad del usuario. El proyecto predeterminado
gestiona OAuth y activa YouTube Data API al añadir el servicio. No requiere
facturación ni servicios de pago. Fuentes oficiales:

- https://developers.google.com/apps-script/guides/services/advanced
- https://developers.google.com/apps-script/guides/cloud-platform-projects
- https://developers.google.com/apps-script/advanced/youtube
- https://developers.google.com/apps-script/guides/web

La función `comprobarCanal` solo consulta la identidad del canal. Los únicos
ámbitos del manifiesto son `youtube.upload` y `youtube.readonly`. No obtiene
permisos de correo, Drive o facturación. Los tokens de Google nunca se
devuelven ni salen del servicio.

El puente HTTP todavía no está desplegado ni conectado al workflow. Su
activación requiere aprobación del propietario: acceso desde GitHub Actions
a través de una clave HMAC aleatoria, guardada únicamente en Propiedades
del script y Actions Secrets. El código no lleva ninguna clave incorporada.
Sin clave de al menos 43 caracteres, rechaza todas las peticiones.

Cada petición firma el JSON exacto, canal, marca de tiempo y nonce. Rechaza
firmas falsas, marcas de tiempo de más de cinco minutos, repeticiones y
canales distintos. El diario previo a cada subida evita repetir un insert
si Google aceptó el vídeo pero se perdió la respuesta. Comprueba también las
huellas de las cincuenta subidas recientes. Conserva un máximo de cien
intentos por día de Los Ángeles y archivos MP4 de hasta 32 MiB.

Esta versión admite exclusivamente pruebas privadas sin programación y sin
notificaciones. Rechaza toda solicitud pública o con `publishAt`. No cambia
`publication_enabled`, la cuota o los permisos del repositorio. La publicación
automática pública sigue pendiente de conexión y prueba efectiva; no se
debe anunciar como completada. El diario de Apps Script tiene almacenamiento
limitado y fallará de forma cerrada si se llena.

Prueba local sin acceso a cuentas:
`node tests/test_apps_script_bridge.cjs integrations/apps-script/Code.gs`.
