# Conexión de Google y publicación programada

Canal autorizado: JMDopamine (`UCuMX_olnpHMCr06FQBdCzjQ`), fijado en cliente y
servidor. La identidad se verifica mediante la API; una sesión de Studio no
sustituye OAuth. La prueba privada de Actions del 19 de noviembre de 2026
confirmó el vídeo `CaYx-v8uEAQ` como privado mediante `videos.list`.

El proyecto predeterminado de Apps Script gestiona OAuth y YouTube Data API.
Solo necesita los ámbitos existentes `youtube.upload` y `youtube.readonly`;
no requiere facturación, Gmail, Drive, permisos nuevos ni servicios de pago.
Los tokens permanecen en Google. `YT_BRIDGE_URL` y `YT_BRIDGE_KEY` están en
Actions Secrets; la misma clave aleatoria está en Propiedades del script.
No hay claves en este código. Una variable opcional `YT_CHANNEL_ID` distinta
del canal autorizado provoca un rechazo antes de conectar.

La versión dos mantiene las pruebas privadas y permite publicación programada
cuando el servidor anuncia `publication_enabled: true` y el contrato del
repositorio también está habilitado. Cada inserción comienza privada.
`publishAt` debe estar entre dos minutos y siete días en el futuro. Se rechazan
subidas públicas inmediatas, avisos a suscriptores y otros canales.
El servidor y el cliente comprueban la fecha y privacidad devueltas por
`videos.list`. Solo se registra `scheduled` tras confirmar la fecha exacta.
Los ciclos posteriores consultan las programaciones vencidas y registran
`published` exclusivamente si YouTube devuelve privacidad pública.
Las pruebas privadas existentes no se convierten ni se vuelven a subir.

Cada petición firma el JSON exacto en ASCII, con escapes JSON que conservan
las tildes y eñes al decodificar. Incluye canal, marca de tiempo y nonce.
HMAC-SHA256, la ventana de cinco minutos, los nonces persistentes y el canal
fijado rechazan peticiones falsas, caducadas o repetidas. No se reintentan los
POST. Las redirecciones de ContentService solo se siguen mediante GET al host
oficial, sin reenviar cuerpo ni firma. Los errores solo muestran códigos
cerrados del protocolo, nunca credenciales o cuerpos de petición.

El diario del servidor se guarda antes de `videos.insert`, y el ID se guarda
antes de comprobar el resultado. La operación firmada `inspect` solo consulta;
no inserta, modifica, programa ni publica vídeos. Un fallo incierto detiene
nuevas inserciones hasta conciliarlo. También se comprueban las huellas de las
cincuenta subidas recientes. El historial permanente de `production-state`
impide reutilizar hechos o vídeos, incluidas pruebas privadas anteriores.

Se conservan cien intentos diarios según el día de Los Ángeles, un máximo de
cinco vídeos por hora y doce minutos entre publicaciones. La generación exige
QA positivo antes de reservar un intento o contactar con la inserción.
Archivos MP4: máximo 32 MiB. La caché del servidor retira confirmaciones de más
de catorce días para no llenar sus propiedades; nunca caduca intentos inciertos.
El historial permanente de GitHub no se purga y prevalece para la deduplicación.

La activación requiere desplegar este código revisado en la implementación
existente y habilitar `config/automation.json`. El éxito de una prueba privada
no equivale a publicación pública. No debe afirmarse una programación sin ID
y fecha confirmados ni una publicación sin privacidad pública confirmada.

Validación sin cuentas:
`python -m unittest discover -s tests -p 'test_*.py' -q`.
La comprobación `integrations/bridge_check.py` usa datos sintéticos que el
servidor debe rechazar antes de cualquier inserción.

Referencias oficiales:
- https://developers.google.com/apps-script/guides/services/advanced
- https://developers.google.com/apps-script/guides/web
- https://developers.google.com/youtube/data/reference/rest/v3/videos/insert
- https://developers.google.com/youtube/data/reference/rest/v3/videos#status.publishAt
