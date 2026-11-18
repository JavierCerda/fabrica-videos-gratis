# Shorts GTA: plantilla fija y curiosidades concretas

El formato principal crea borradores verticales **1080×1920 a 30 fps**, de 25–59 segundos.
La plantilla es simple y permanece igual durante todo el vídeo:

- Fondo lila plano **#8B65B5**.
- Título del episodio fijo arriba, centrado y con un máximo de tres líneas.
- Vídeos y fotos en el mismo cuadrado de **984×984**, situado en **(48, 414)**.
- Subtítulos amarillos con borde negro debajo del medio, en grupos de hasta tres palabras.

Todos los medios usan el mismo ajuste proporcional para llenar el cuadrado, sin
estirarlos, sin paneles borrosos y sin cambios de tamaño. El encuadre horizontal o
vertical se revisa por plano para conservar al protagonista. Se retiran las bandas
negras incrustadas en el tráiler mediante un recorte editorial explícito, registrado
en los créditos. Las fotos conservan su nitidez: no se añade un zoom artificial.
La resolución de salida no implica que todas las fuentes sean nativas 1080p.

## Voz y subtítulos

El motor principal es **Microsoft Edge neural**, mediante `edge-tts==7.3.1`,
sin API key, cuenta de facturación ni suscripción. La voz predeterminada es
**es-ES-AlvaroNeural**. La alternativa es **es-MX-JorgeNeural**. Se entregan dos
muestras con la misma frase y sin música para comparar. Velocidad -3 %, tono -2 Hz.
No se clona una voz ni se imita a una persona real.

El servicio es online y depende de su disponibilidad; no es una API con garantía
de servicio. Si falla, el workflow se detiene: **no vuelve automáticamente a las
voces Kokoro o Piper rechazadas**. La validación TLS se mantiene activada y se
cargan las CA del sistema cuando el entorno lo necesita.

Cada narración guarda `voz_XX.words.json` con los tiempos de palabra entregados
por el servicio. Los subtítulos ASS y SRT usan esas marcas, con el desplazamiento
real de cada audio; no se calculan repartiendo la frase por su número de letras.
No se solapan dos grupos de subtítulos. Si faltan las marcas, la producción falla.

La música **Midnight Avenue** sigue siendo una composición y síntesis original
local, sin samples ni canciones ajenas. Su volumen baja durante la voz.

## Contenido

Los episodios aprobados para la selección automática aportan hechos concretos:

- **GTA VI: pasado de Jason y Lucía.** Ejército, prisión, Liberty City y la
  propiedad de Brian Heder. Cada dato procede de las biografías oficiales.
- **Vice City: la voz de Tommy Vercetti.** Ray Liotta, acreditado en el manual oficial.

Los antiguos comentarios generales del catálogo se conservan archivados y ya no
entran en `auto` ni `muestra`. Un guion nuevo necesita un dato verificable, una
fuente y una selección visual relacionada; los anuncios encontrados no se
convierten automáticamente en afirmaciones. `ideas_investigadas.json` registra
las fuentes consultadas y los errores de consulta. Las comprobaciones de términos
ayudan a detectar cambios de páginas, pero no son un verificador universal.

## Workflow

En Actions, **Fabrica gratuita de videos** genera por defecto `gta6-pasado-protagonistas`.
`muestra` produce los dos episodios aprobados. `voice` permite elegir España o
México; `captions` está activado por defecto. La programación semanal existente
usa solo el catálogo de hechos aprobados y se detiene si se agota.

El workflow ejecuta las pruebas y un montaje real con medios sintéticos antes de
producir el episodio. El artefacto `shorts-gta-studio` contiene MP4, portada,
guion, narraciones, marcas de palabra, música, ASS/SRT, créditos y muestras de voz.
Retención: siete días. Punto de entrada: `python -m app.studio`.

## Coste, fuentes y publicación

No se activa facturación, no se llama a Gemini ni a una API de pago y no se
contratan servicios. Los límites gratuitos de GitHub y la disponibilidad del
servicio de voz o de las fuentes pueden detener una ejecución.

El material visual oficial sigue teniendo copyright de Rockstar/Take-Two.
Los metadatos mantienen `rights.status=review_required`, `copyright_clearance=false`
y `monetization_clearance=false`. No se usan vídeos ajenos de creadores ni audio
de tráilers. La duración de las tomas responde al montaje, no evita Content ID.
**No se publica en YouTube**: el flujo rechaza `YOUTUBE_UPLOAD=true`.

- [Jason y Lucía: biografías oficiales](https://www.rockstargames.com/VI/only-in-leonida/jason)
- [Galería oficial GTA VI](https://www.rockstargames.com/VI/media/screenshots)
- [edge-tts: documentación](https://github.com/rany2/edge-tts)
- [Política de Rockstar](https://support.rockstargames.com/articles/7bNaeoMFTV0iUDGhStTXvz/policy-on-posting-copyrighted-rockstar-games-material)
- [Copyright en YouTube](https://support.google.com/youtube/answer/9783148)
