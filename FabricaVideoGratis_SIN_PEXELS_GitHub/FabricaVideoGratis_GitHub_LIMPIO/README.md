# Shorts editoriales de GTA VI

El workflow crea **Shorts de 25–59 segundos, 1080×1920 a 30 fps**, con narración
española, títulos completos, carteles propios y subtítulos de hasta cuatro palabras.
El montaje alterna comentario original y fragmentos seleccionados del tráiler de
lanzamiento que Rockstar ofrece en su página oficial de descargas. No utiliza stock
genérico, filtraciones ni vídeos de otros creadores.

## Temas preparados

- **GTA VI no es solo Vice City**: qué aporta el contraste de escenarios de Leonida.
- **El riesgo es confiar**: lectura del planteamiento de Jason y Lucía, sin inventar el final.
- **Un tráiler no demuestra 60 FPS**: diferencia entre un montaje promocional y una prueba de rendimiento.

Los guiones están escritos y revisados en `topics/shorts.json`. Cada uno identifica
fuentes oficiales, hechos comprobables e interpretaciones. No se generan noticias
inventadas ni se prometen visitas. Antes de producir se comprueban las fuentes;
si faltan las referencias previstas, la ejecución se detiene para revisión editorial.

## Generar y revisar

En **Actions → Fabrica gratuita de videos → Run workflow**, se puede elegir uno
de los tres temas. El artefacto **short-gta6** incluye `short_vertical.mp4`, portada,
guion, subtítulos ASS y SRT, voces y metadatos. Se conserva durante siete días.

Antes de producir se ejecutan las regresiones y una prueba real con metraje de
prueba, sin Internet. Esta comprueba 1080×1920, pista de audio, subtítulos y que
todos los títulos y carteles quepan completos. Los subtítulos se temporizan de
forma aproximada por frases dentro de cada toma de voz; no se presentan como
alineación exacta por palabra.

Se conserva la programación semanal existente. En ella se elige el siguiente tema
del catálogo desde el 18 de noviembre de 2026. Al agotarlo, se detiene en vez de
repetir vídeos indefinidamente. Los temas manuales se seleccionan expresamente.

El código se encuentra en
`FabricaVideoGratis_SIN_PEXELS_GitHub/FabricaVideoGratis_GitHub_LIMPIO/`.
La versión horizontal anterior se conserva como `python -m app.pipeline`; ya no es
el formato que ejecuta el workflow.

## Fuentes y derechos

- [Descargas oficiales de Rockstar](https://www.rockstargames.com/VI/media/videos).
- [Personajes y lugares de Leonida](https://www.rockstargames.com/VI/only-in-leonida).
- [Política de Rockstar](https://support.rockstargames.com/articles/7bNaeoMFTV0iUDGhStTXvz/policy-on-posting-copyrighted-rockstar-games-material).
- [Copyright y fair use en YouTube](https://support.google.com/youtube/answer/9783148).
- [Políticas de monetización de YouTube](https://support.google.com/youtube/answer/1311392).

**No existe una regla de «menos de cinco segundos sin copyright».** Las duraciones
se eligen por necesidad editorial y ritmo. No se modifica el material para evitar
Content ID, ni se conserva la música o el audio del tráiler. La atribución, quitar
la música y añadir comentario no garantizan permiso, ausencia de reclamaciones ni
monetización. La política de Rockstar se refiere a usos ocasionales y no
comerciales; no se interpreta como una licencia comercial general.

Los metadatos registran la fuente, los intervalos usados y su motivo, con
`copyright_clearance=false`, `monetization_clearance=false` y
`rights.status=review_required`. La publicación permanece desactivada; este módulo
no utiliza credenciales de YouTube y rechaza `YOUTUBE_UPLOAD=true`.

El archivo completo del tráiler se descarga solo como fuente temporal (unos 782 MB).
Se verifica su SHA-256 para mantener los intervalos revisados; si Rockstar sustituye
el archivo, hay que revisar los planos. No se sube el tráiler completo al repositorio
ni al artefacto. Que la descarga sea pública no la convierte en una obra libre.

## Coste

La voz se sintetiza en CPU con `piper-tts==1.8.0` y la voz española
`es_ES-davefx-medium`, revisión
`0ca208afc2a2ee102b1e961e72e0a7e4907be3d0` con datos CC0. Se verifican los hashes
del modelo y su configuración. No hay API de voz ni llamadas a Gemini en el nuevo
flujo de Shorts. FFmpeg/FFprobe se obtienen de FFmpeg-Builds verificando el SHA-256
publicado por GitHub. No se activa facturación ni se contratan servicios.

Se usan los recursos gratuitos disponibles de GitHub; sus límites pueden detener
una ejecución. La gratuidad de la producción no implica derechos comerciales
sobre el tráiler.
