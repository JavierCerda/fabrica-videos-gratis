# Shorts GTA: comedia española y producción automática

El formato principal es **comedia adulta en español de España**, con tacos sin
censura, datos verificables y comparaciones humorísticas originales. No se clona
una voz ni se presenta una broma como una mecánica confirmada del juego.

## Producción

Al actualizar el catálogo de guiones aprobados en `main`, el workflow arranca
automáticamente y genera **dos Shorts**. También permite ejecución manual.
Los episodios actuales son: Cal Hampton y el alquiler de Jason.
La voz es **es-ES-AlvaroNeural**. El guion completo se sintetiza en una única
toma para conservar el timbre y el ritmo. Solo se acortan los silencios largos,
sin acelerar palabras ni recortar fonemas; las marcas de palabra se recalculan.
Los bloques se separan por muestras y se vuelven a unir sin perder audio.
No se ocultan los tacos en audio ni subtítulos.

La plantilla se conserva durante todo el vídeo: lila plano **#8B65B5**, título
fijo arriba, medios en un cuadrado de **984×984** en **(48,414)** y subtítulos
amarillos debajo. Fotos y vídeos usan el mismo encuadre proporcional sin estirarse.
Las imágenes se revisan antes de fijar su centro de encuadre.

Se emplean fotos de los personajes y vídeos oficiales suficientemente largos.
Los clips inferiores a dos segundos se descartan cuando hay fotos disponibles:
no se intercalan destellos de 0,8 segundos. Los planos duran al menos tres segundos,
con zoom muy suave y fundidos de 0,3 segundos solo dentro del cuadrado. Título,
fondo y subtítulos quedan estables. No se repiten ni ralentizan vídeos para rellenar.

La música original del proyecto sigue baja bajo la voz y baja aún más al hablar.
Se mantienen los tiempos de palabra que entrega el motor: los subtítulos no se
sincronizan contando letras. La voz se comprueba contra el texto completo;
si omite o cambia palabras, se detiene. No se vuelve a voces anteriores como fallback.

## Guiones y fuentes

El catálogo `topics/curiosities.json` diferencia los hechos y los chistes en
`editorial.facts` y `editorial.jokes`. El nuevo formato `comedia_es` es el único
que participa por defecto en `auto` y `muestra`. Los formatos anteriores se
conservan, pero no se mezclan automáticamente con el tono nuevo.

Las fichas de Rockstar respaldan las curiosidades de Cal y Brian. Las palomas,
el antivirus, las nóminas o la comunidad de vecinos son bromas del narrador.
Los nuevos artículos encontrados se guardan como candidatos para revisión;
no se publican ni se convierten en hechos sin comprobarlos.

La programación semanal existente elige el siguiente guion aprobado. Al agotarse
el catálogo se detiene en vez de inventar noticias o repetir episodios.

## Control automático de calidad

Antes de terminar, `python -m app.quality` revisa todos los MP4 producidos:

- Decodificación completa, FPS constantes y tiempos de todos los fotogramas.
- Continuidad de todas las muestras de voz y ausencia de silencios superiores a 700 ms.
- Planos de al menos tres segundos y detección de imágenes congeladas.
- Audio estéreo de 48 kHz y picos por debajo del límite fijado.
- Todas las palabras de la narración, incluidos los tacos, en las marcas de voz.
- Subtítulos sin solapamientos ni parpadeos, con un máximo de dos líneas.
- Título permanente, dimensiones del marco y publicación desactivada.

El informe `control_calidad.json`, MP4, portada, guion, fuentes, voces, música,
marcas de palabra y subtítulos se guardan en `shorts-gta-studio` durante siete días.
Estas comprobaciones técnicas no garantizan que el humor o la voz gusten a todos.

## Coste y publicación

Se mantienen herramientas gratuitas y voz Edge sin API key ni cuenta de
facturación. La disponibilidad del servicio de voz y las cuotas gratuitas de
GitHub pueden detener el proceso. No se activa facturación ni se contratan servicios.

**No se publica en YouTube.** El flujo rechaza `YOUTUBE_UPLOAD=true`. Los clips y
capturas de Rockstar mantienen su copyright: los metadatos conservan
`rights.status=review_required`, `copyright_clearance=false` y
`monetization_clearance=false`. La duración de los planos se elige por montaje;
no se usa para evitar Content ID ni se incluyen vídeos de otros creadores.

- [Biografías oficiales](https://www.rockstargames.com/VI/only-in-leonida)
- [Vídeos y clips oficiales](https://www.rockstargames.com/VI/media/videos)
- [Voz Edge](https://github.com/rany2/edge-tts)
