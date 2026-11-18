# Shorts de curiosidades GTA

El formato principal crea vídeos verticales **1080×1920 a 30 fps**, de 25–59 segundos.
La imagen ocupa el montaje: se ha eliminado la plantilla de tarjetas, números,
explicaciones y rótulos permanentes. Solo aparece un gancho durante **1,7 segundos**
al principio. Los subtítulos se entregan aparte y su incrustación es opcional.

## Voz y música

La voz predeterminada es **Kokoro `em_alex`**, español, con una cadencia masculina
serena y velocidad 0,94. No clona ni imita a una persona real. Se sintetiza en CPU,
sin API ni cuota de voz. Se usa `kokoro-onnx==0.6.1`, `espeakng-loader==0.2.4` y el
modelo Kokoro-82M v1.0 con pesos Apache-2.0. Los archivos del modelo y las voces
se descargan desde una versión fijada y se comprueban sus SHA-256.

La banda de fondo **Midnight Avenue** se compone y sintetiza dentro del proyecto:
piano eléctrico, bajo y percusión suave a 88 BPM, sin samples ni canciones ajenas.
La mezcla baja la música cuando habla la voz, suaviza la dinámica y limita los picos.
Los artefactos incluyen la narración y la música por separado, además del MP4.

## Imágenes y curiosidades

Los guiones revisados de `topics/curiosities.json` cubren:

- **GTA IV:** tres historias conectadas en Liberty City.
- **San Andreas:** tres ciudades y un recorrido por todo el estado.
- **Vice City:** su identidad deliberadamente ochentera y Ray Liotta como voz de Tommy Vercetti, acreditado en el manual oficial.
- **GTA III:** la libertad de desviarse del recorrido.
- **GTA V:** el contraste de sus tres protagonistas.
- **GTA VI:** los distintos ambientes de Leonida.

Algunos episodios son curiosidades documentadas y otros son lecturas de diseño,
identificadas como opinión. No se anuncian mitos o filtraciones como hechos.

Se consulta el catálogo oficial de Rockstar en Steam y la galería oficial de GTA VI.
Cada imagen queda asociada a su juego, fuente, hash y resolución original. El montaje
rechaza recursos de juegos no permitidos para el tema. Las capturas históricas de
menor tamaño conservan el plano completo sobre un fondo ambiental desenfocado;
no se promete que sean material nativo 1080p ni se inventan detalles al ampliarlas.
Las capturas de alta resolución admiten encuadres verticales con movimiento suave.
Se presentan como imágenes oficiales animadas, no como gameplay grabado por el canal.

Antes de cada producción, `gta_sources.py` consulta también los anuncios del editor
mediante la API pública de noticias de Steam, sin clave. El informe
**ideas_investigadas.json** registra los artículos encontrados, fuentes y errores
si una fuente no responde. Los candidatos nuevos requieren comprobación editorial
y guion; no se convierten automáticamente en afirmaciones o vídeos. Las comprobaciones
de términos de las fuentes ayudan a detectar cambios, pero no son un verificador
universal de hechos. Los datos de los guiones se revisan editorialmente.

## Ejecutar y revisar

En **Actions → Fabrica gratuita de videos → Run workflow**:

- **muestra** genera dos vídeos: GTA IV y San Andreas.
- Los demás valores seleccionan un episodio concreto.
- **captions** activa subtítulos sobre la imagen; por defecto está desactivado.

El workflow ejecuta pruebas de regresión y una prueba real del montaje y la mezcla
sin servicios externos. El artefacto **shorts-gta-studio** incluye vídeos, portadas,
guiones, voces, narración, música, subtítulos, créditos e informe de investigación.
Se conserva durante siete días.

La programación semanal existente genera el siguiente guion aprobado desde el
18 de noviembre de 2026. Si se agota el catálogo, se detiene para revisar nuevas
ideas en lugar de repetir vídeos indefinidamente.

El código está en
`FabricaVideoGratis_SIN_PEXELS_GitHub/FabricaVideoGratis_GitHub_LIMPIO/`.
El nuevo punto de entrada es `python -m app.studio`. Los formatos anteriores
`app.shorts` y `app.pipeline` se conservan, pero ya no los ejecuta el workflow.

## Derechos y publicación

**Cinco segundos no garantizan evitar Content ID ni conceden derechos de uso.**
La duración de las tomas se elige por ritmo. El proyecto no incorpora recortes de
otros creadores sin una base de permisos o licencia revisada, ni modifica material
para evadir detecciones. No utiliza canciones de GTA ni el audio de sus tráilers.

Las imágenes oficiales siguen teniendo copyright de Rockstar/Take-Two; su carácter
público no las convierte en material libre. Los metadatos mantienen
`copyright_clearance=false`, `monetization_clearance=false` y
`rights.status=review_required`. La política general de Rockstar no se interpreta
como una autorización comercial. Los derechos deben revisarse antes de publicar
o monetizar. **No se publica ningún vídeo en YouTube** y este flujo rechaza
`YOUTUBE_UPLOAD=true`.

- [Política de Rockstar](https://support.rockstargames.com/articles/7bNaeoMFTV0iUDGhStTXvz/policy-on-posting-copyrighted-rockstar-games-material)
- [Copyright y fair use en YouTube](https://support.google.com/youtube/answer/9783148)
- [Kokoro-82M: modelo y licencia](https://huggingface.co/hexgrad/Kokoro-82M)
- [Voces de Kokoro](https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md)

## Coste

Todo se ejecuta con herramientas y modelos locales gratuitos dentro del runner.
No se activa facturación, no hay llamadas a Gemini ni API de voz de pago y no se
contratan servicios. Los límites gratuitos de GitHub y la disponibilidad de las
fuentes pueden detener una ejecución. La gratuidad de producción no implica
una autorización comercial del material visual.
