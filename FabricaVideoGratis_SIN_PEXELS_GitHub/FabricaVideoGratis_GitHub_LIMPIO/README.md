# Shorts GTA: investigación, producción y publicación

El canal usa una cabecera moderna con **Manrope ExtraBold** (SIL Open Font License),
tarjeta oscura sobre lila, medios uniformes de 984×984 y subtítulos amarillos.
Usa la voz española `es-ES-XimenaNeural`, la opción A elegida tras escuchar las muestras,
con tono cercano y ritmo +7 % para los próximos Shorts. La voz Álvaro queda para pruebas heredadas. Habla en una sola toma, con pausas ajustadas,
movimiento suave y fundidos solo en el marco de medios.

La voz se obtiene mediante edge-tts, sin clave ni cuenta de facturación. Los
subtítulos usan las marcas de palabra del motor, que se contrastan con el texto
sin omisiones. Whisper sigue verificando además el flujo antiguo de Álvaro;
no se ejecuta esa segunda verificación en Ximena. Los controles de sonido,
subtítulos y duración se conservan. Un fallo no sustituye la voz silenciosamente.
La referencia ronca anterior se conserva intacta en `assets/voices/voz_a_1.flac`,
con su SHA256 y configuración original en `config/voice_reference.json`.
El flujo actual no necesita descargar ni compilar VoxCPM2.

Los guiones nuevos del perfil 4 incluyen un gancho fácil de entender, hechos
comprobados y humor natural relacionado con GTA, en 90–125 palabras. No se obligan
chistes ni tacos ni se inventan noticias. Los borradores del perfil 3 se conservan.
Cada foto o fragmento tiene revisión visual y una relación explícita con su bloque.
Cada fotografía se utiliza una sola vez por Short; cambiar su recorte no crea un recurso
nuevo. Los fragmentos de un mismo vídeo no se solapan ni se repiten. Si no hay medios
relacionados suficientes, se rechaza el montaje en lugar de volver a insertar una imagen. El modo `contain` conserva el encuadre completo dentro del
cuadrado sobre una ampliación desenfocada del mismo recurso.

La producción conserva `publication_enabled: true` y solo publica en ejecuciones
de producción autorizadas. Los cambios ordinarios se verifican primero en vista
previa, sin publicar. `editorial_generation_version: 4` gobierna guiones nuevos;
el mínimo compatible 3 protege los borradores anteriores y evita perder cola.

## Flujo horario

1. La tarea de investigación de ChatGPT consulta fuentes actuales y el historial.
   Prepara cinco guiones distintos en `topics/inbox.json`. Lee `AUTOMATION.md`.
2. Un commit `[auto-shorts] ...` inicia producción en GitHub Actions. La ejecución
   horaria a los 47 minutos también procesa lo que haya quedado pendiente.
3. La cola conserva guiones, huellas de hechos, intentos e IDs de YouTube en
   `automation-state.json`, rama `production-state`, independiente de `main`.
4. Se priorizan noticias publicadas ese día en Europe/Madrid. Si no hay suficientes,
   se usan curiosidades verificadas. Los hechos y las bromas quedan separados.
5. Cada vídeo pasa la revisión de voz, fotogramas, silencios, imágenes congeladas
   y subtítulos. Solo después puede subirlo el publicador.
6. Se programan publicaciones públicas separadas doce minutos. Título, descripción,
   fuentes, etiquetas, idioma español y categoría Gaming se generan por vídeo.
   Las notificaciones a suscriptores están desactivadas para este volumen.

No se exige que existan tres noticias nuevas cada hora: si no las hay, no se
inventan ni se vuelven a etiquetar noticias antiguas como noticias de ese día.
La investigación horaria depende de la disponibilidad y límites del plan de ChatGPT.
GitHub puede retrasar ejecuciones programadas; doce minutos es la separación prevista,
no una garantía de publicación exacta por parte de las plataformas.

## Cinco por hora y cuotas

Cinco por hora durante todo el día son **120 subidas diarias**. La documentación
vigente de YouTube indica una cuota inicial de **100 videos.insert/día**, con
reinicio a medianoche del Pacífico. `config/automation.json` conserva ese límite;
los pendientes se guardan como guiones y no como MP4 para evitar almacenamiento
continuo. Un límite real menor del canal o del proyecto pausa las subidas hasta
el reinicio, sin intentar eludirlo. Para sostener 120/día hace falta una ampliación
de cuota aprobada por YouTube; no se activa facturación ni se aumenta el límite
configurado automáticamente. Una cola llena deja de aceptar guiones nuevos.

- https://developers.google.com/youtube/data/determine_quota_cost
- https://developers.google.com/youtube/data/Getting_Started#quota

## Conexión del canal

La publicación requiere una autorización OAuth del propietario. Los secretos de
Actions son `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`; la variable
`YT_CHANNEL_ID` identifica el canal exacto. Ámbitos mínimos del publicador:
`youtube.upload` y `youtube.readonly`. No se guardan secretos ni sesiones de subida
en commits, informes, archivos multimedia ni en la rama de estado.

Si la publicación está pausada, devuelve `publication_paused` conservando la cola.
Cuando esté habilitada y falte la conexión, devuelve `connection_required`:
**no significa que esté publicando**. Si OAuth corresponde a otro canal, se detiene
antes de generar o subir nada. También se comprueba que YouTube haya aceptado la
fecha de publicación. Las credenciales no se piden por chat ni se incluyen en el
repositorio. La autorización y la configuración de esos secretos se completan en
la conexión segura con el propietario; no requiere editar archivos manualmente.

La prueba inicial usa `--mode upload-test`: genera y revisa un único Short y lo sube
como privado, sin publishAt y sin notificar a suscriptores. No cambia publication_enabled.
Un commit de operación `[upload-test] ...` inicia esa prueba; la investigación horaria
sigue usando exclusivamente `[auto-shorts]`. Sin OAuth devuelve connection_required
y conserva el vídeo validado como muestra. Solo private_test_complete confirma la
subida privada, con ID y privacidad comprobados en YouTube. El historial registra
la prueba para no volver a subir el mismo hecho.

Antes de cada subida se reserva el intento en el historial. Si una respuesta se
pierde, el siguiente ciclo busca la huella en las últimas subidas del propio canal
antes de continuar. Un resultado incierto no se vuelve a subir a ciegas. Si YouTube
no confirma la programación, se informa como `schedule_needs_review`.

## Coste, medios y controles

Se usan runners estándar de un repositorio público, edge-tts sin API key y una
fuente con licencia abierta incluida en el código. No se necesita Gemini para
este flujo: los guiones proceden de la tarea de investigación. No hay proveedores
de pago ni activación de facturación. Las ejecuciones horarias guardan informes
pequeños durante un día; solo las vistas previas guardan MP4 durante un día.

Los medios deben corresponder al juego concreto. Se incluyen catálogos de GTA III,
Vice City, San Andreas, GTA IV y episodios, GTA V/Online y GTA VI. Para GTA original,
GTA 2, London, Advance, Liberty City Stories, Vice City Stories y Chinatown Wars,
el investigador tiene que seleccionar imágenes oficiales verificadas: no se usan
capturas de otro juego para rellenar. Si no se dispone de medios suficientes,
se elige otra curiosidad de la saga. Nunca se extrae audio ajeno ni se toma la
brevedad del plano como permiso de copyright. La publicación es comentario original;
las capturas conservan los derechos de su titular.

Pruebas: `python -m unittest discover -s tests -p 'test_*.py'` y
`python tests/smoke_studio.py`. La vista previa completa se ejecuta con
`python -m app.autopilot --mode preview`; producción, con `--mode production`.

Los reportes de Actions y el historial son la fuente de verdad sobre qué se ha
subido realmente. El SEO no garantiza visitas y las pruebas técnicas no garantizan
que la voz o el humor gusten a todas las personas.
