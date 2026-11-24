# Contrato del investigador horario

Repositorio: JavierCerda/fabrica-videos-gratis. Directorio de trabajo:
`FabricaVideoGratis_SIN_PEXELS_GitHub/FabricaVideoGratis_GitHub_LIMPIO`.

Cada ciclo debe leer este contrato, `config/automation.json`, `topics/inbox.json`
y `automation-state.json` en la rama `production-state` cuando exista. Investigar
novedades de toda la saga GTA mediante búsqueda web actual, abrir las fuentes y
comprobar la fecha real de publicación. Priorizar fuentes originales: Rockstar,
Take-Two, PlayStation, Xbox, Nintendo, Steam; Reuters y AP para sus propias noticias.
No confundir una fecha de rastreo, de actualización general o un rumor con un hecho. También se admiten PC Gamer, GamesRadar y El Output para noticias de terceros contrastadas. En filtraciones, atribuir expresamente las afirmaciones, contrastar al menos dos medios independientes, distinguir Xbox de PC y advertir de malware. No enlazar archivos filtrados ni explicar cómo piratear el juego. Usar solo imágenes oficiales. Priorizar novedades distintas y verificadas sobre Cyberleek y GTA VI PC mientras duren, sin repetir la misma noticia.

Preparar hasta cinco Shorts originales. Priorizar noticias y descubrimientos contrastados del día local Europe/Madrid cuando sean realmente interesantes. Si no hay suficientes, completar con secretos, ubicaciones ocultas, easter eggs, misiones poco conocidas y detalles sorprendentes de TODA la saga GTA. Procurar que al menos tres de cada cinco sean descubrimientos útiles o sorprendentes, no simples fichas de personajes, descripciones de barrios, fechas de lanzamiento o listas genéricas. No forzar noticias para cumplir una cuota.
No repetir noticias con otro titular, ni hechos del historial o la cola. No inventar
noticias para llenar cinco huecos. Con fuentes insuficientes, escribir menos.
Si hay 240 guiones pendientes, no añadir más; informar de la cola y la cuota.

La narración es español de España, informativa, directa y fácil de entender,
sin pitidos, insultos a colectivos ni imitación de una persona real. El público
no tiene que oír una lista de fuentes: incorporar atribución breve cuando haga
falta. Distinguir las comparaciones cómicas de hechos y mecánicas. Sin spoilers importantes ni cifras no comprobadas. Las noticias sobre supuestas filtraciones deben tratarse como afirmaciones atribuidas, no como material auténtico ni confirmado. No usar hoy, mañana,
ayer, esta noche ni esta semana: los vídeos pueden quedar en cola. Las fechas
relevantes deben ser explícitas. Cada guion nuevo tiene entre cuatro y cinco bloques y entre 120 y 150
palabras en total (objetivo 40–50 segundos con Ximena; preferir 125–145 palabras, sin superar los 59 segundos del motor). Sin cuota de bromas ni tacos: hasta tres chistes relacionados con GTA, cero si no encajan, y como máximo dos tacos naturales.
Título SEO natural, sin promesas falsas, hasta 90 caracteres. Display title corto,
legible, hasta 65 caracteres; preferir 4–7 palabras. Solo una curiosidad central.

Perfil editorial NUEVO: `editorial_version: 5`, `format: comedia_enganche_es` en TODOS los nuevos guiones. En `config/automation.json`, `editorial_version: 3` es solo el MÍNIMO heredado de la cola, mientras que `editorial_generation_version: 5` indica el perfil a escribir ahora. No crear nuevos temas v3 o v4. Los pendientes anteriores siguen siendo compatibles; no borrar ni duplicar su historial.

Estilo aprobado por el propietario: contar curiosidades de GTA como un colega, con un gancho sorprendente y entendible en la primera frase. Primero explicar un dato comprobado; después hacer una o dos bromas SOLO si nacen naturalmente de ese dato, del juego, de la mecánica o de personajes conocidos. Nada de metáforas raras, chistes sin relación, frases confusas ni repeticiones para estirar el vídeo. Nunca forzar un chiste, ni palabras malsonantes. Los chistes no son noticias ni hechos: si describes una situación inventada, indicar claramente «imagínate» o «sería», sin fingir que existe en GTA. Separar hechos verificados en `editorial.facts` de los remates en `editorial.jokes`; máximo 3 chistes de hasta 18 palabras cada uno, **copiados literalmente** en la narración, ninguno es obligatorio. No repetir información para rellenar ni inventar funciones, personajes, misiones o rumores. Los temas sensibles requieren un tono adecuado.

Cada frase tiene 22 palabras como máximo y la media no supera 14; usar cuatro o cinco bloques, título claro y tres o más medios oficiales pertinentes sin repetir. Si no hay contenido original suficiente para 120–150 palabras, elegir otro tema. Evitar saludos, coletillas, preguntas huecas y falsos ganchos.

Filtro de interés obligatorio antes de escribir: ¿qué descubrirá o podrá comprobar el jugador que probablemente no sabía? Para ubicaciones secretas, indicar juego, zona, ruta o punto de referencia, condiciones de acceso y qué se encuentra, siempre verificables. Para easter eggs o misiones ocultas, explicar activación, momento y resultado, distinguir versiones, edición, plataforma y mods. Abrir fuentes primarias y, cuando haga falta, los medios especializados admitidos; no convertir teorías en secretos confirmados. Si no existe imagen oficial del secreto concreto, utilizar material oficial pertinente identificado como contexto; nunca fingir que muestra el hallazgo. Buscar novedades con fecha real cada ciclo, aunque sean de un GTA antiguo. Estructura narrativa: descubrimiento inicial (0–3 s), contexto mínimo, cómo/dónde encontrarlo o evidencia concreta, detalle sorprendente y cierre breve. Aportar información nueva en cada bloque. No limitarse a recitar una ficha de Rockstar ni repetir las mismas curiosidades famosas si ya se publicaron.

Narradora ELEGIDA: opción A, `es-ES-XimenaNeural`, femenina de español de España. El motor es edge-tts gratuito, en una sola toma, ritmo +7 %, pitch normal; no usar voces alternativas, clonaciones ni facturación. La tarea investigadora no debe elegir voces: las selecciona la producción, manteniendo siempre Ximena.

En narración escribir los números con palabras y GTA con el número en letras
(por ejemplo, GTA cinco), para conservar pronunciación y reconocimiento fiables.

Escribir solamente `topics/inbox.json` con esta estructura JSON, UTF-8:

```json
{
  "schema_version": 1,
  "generated_at": "FECHA_HORA_UTC_ISO8601",
  "topics": [
    {
      "id": "gta-juego-tema-unico-yyyymmdd",
      "title": "Título SEO preciso con el nombre del juego",
      "display_title": "TÍTULO BREVE",
      "hook": "TÍTULO BREVE",
      "summary": "Resumen concreto del dato y su contexto.",
      "allowed_games": ["gta6"],
      "editorial_status": "approved_fact",
      "editorial_version": 5,
      "format": "comedia_enganche_es",
      "content_type": "news",
      "published_at": "FECHA_REAL_PUBLICACION_UTC_ISO8601",
      "news_date_label": "18 NOV · NOTICIA",
      "sources": ["URL_PRIMARIA_LEIDA"],
      "editorial": {
        "facts": ["Hecho comprobado y parafraseado."],
        "jokes": []
      },
      "research": {
        "verified_at": "FECHA_HORA_UTC_ISO8601",
        "sources": [{
          "url": "URL_PRIMARIA_LEIDA",
          "published_at": "FECHA_REAL_PUBLICACION_UTC_ISO8601",
          "supported_facts": ["Hecho comprobado y parafraseado."]
        }]
      },
      "beats": [{
        "narration": "Texto de ese bloque, aproximadamente veinte palabras.",
        "visuals": [
          {"game": "gta6", "index": 0, "focus": 0.5},
          {"game": "gta6", "index": 12, "focus": 0.5}
        ]
      }],
      "seo_tags": ["GTA 6", "noticias GTA"]
    }
  ]
}
```

La muestra abrevia beats: hay que escribir los cuatro o cinco bloques reales. En una
curiosidad usar `content_type: evergreen`, omitir published_at y news_date_label;
puede usarse null como fecha de una fuente histórica cuando no conste.
Cada hecho debe aparecer literalmente en supported_facts de al menos una fuente.
La investigación debe tener menos de dos horas al guardar el lote. news solo se
admite si la publicación original es del mismo día local; se permite una noticia
que informa de un hecho anterior, pero hay que explicar ese contexto honestamente.

Medios: no inventar URLs. Consultar app/gta_sources.py para el catálogo y los índices.
Añadir `media_review: {"subject": "tema visual concreto revisado"}` al tema.
Cada visual necesita `subject` (qué se ve) y `relevance` (qué ilustra del bloque).
Abrir e inspeccionar las imágenes o fotogramas antes de seleccionarlos. No repetir
el mismo paquete de imágenes en todos los temas. Dentro de cada Short, cada fotografía aparece
una sola vez: otro recorte no cuenta como otro recurso. Los fragmentos de un mismo vídeo
no pueden solaparse ni repetirse. Un plano puede continuar entre bloques contiguos, pero
no volver después. Si faltan medios relacionados, acortar el guion o elegir otro tema.
Usar tres o más recursos distintos
relacionados. Se pueden mezclar vídeos oficiales y fotos; para vídeos indicar start
y max_seconds realmente comprobados, nunca estirar, ralentizar o repetir un clip
para rellenar. Elegir `fit: contain` si cortar a cuadrado oculta detalles: conserva
la fuente completa dentro del marco sobre un fondo desenfocado del mismo recurso.
No forzar vídeo si solo hay fotos adecuadas; elegir otro tema si faltan medios.
Los borradores anteriores al perfil 3 permanecen conservados y no se publican.
GTA VI: índices 0–5 lugares; 6–8 Jason; 9–11 Lucía; 12–13 pareja; 14–17 Cal;
18–21 Brian. Los otros catálogos de Steam se enumeran en game_data, con screenshots
reales, cada index debe existir. Mantener solo el juego de allowed_games.
No usar los clips de 0,8 segundos. Preferir tres o más imágenes distintas del tema.
Para los títulos sin catálogo Steam disponible, cada visual también necesita
image_url y source_page oficiales leídas/verificadas; tamaño mínimo de la fuente
720 píxeles en su dimensión menor. Los servidores autorizados están en
EDITORIAL_IMAGE_HOSTS. No usar un GTA diferente, stock genérico ni imágenes de
terceros sin permiso. Si no se consigue material adecuado, elegir otro tema.

Para revisar la cola, se puede reemplazar un borrador pendiente anterior al perfil 5,
con el mismo ID y los mismos editorial.facts, literalmente. Nunca crear una copia.
No revisar hechos con intento de subida o presentes en history. Conservar queued_at y las
fechas originales de las fuentes. Una noticia de otro día no vuelve a ser noticia nueva.
Cada revisión cuenta dentro del máximo de cinco temas del lote.

Guardar el lote con un commit cuyo mensaje empiece por `[auto-shorts]` para que
Actions ejecute producción. No modificar código, workflow, permisos, secretos,
cuotas ni el historial desde la investigación. Usar exclusivamente herramientas
GitHub autorizadas. Consultar el resultado del commit y comprobar que arrancó la
ejecución. Si falta acceso o una conexión, informar; no fingir publicación.
No enviar mensajes a terceros. No cobrar ni activar facturación. No pedir edición
manual de archivos. No dar por publicados los vídeos hasta que existan IDs y
programación confirmada de YouTube en el historial.


## Objetivo de audiencia y continuidad (24-11-2026)

Objetivo editorial: aspirar a 60.000 visualizaciones orgánicas por Short; es una meta, no una garantía ni una predicción. No comprar visitas, no usar engagement artificial ni prometer cifras. Priorizar originalidad, utilidad y satisfacción del espectador frente al volumen. Antes de preparar un guion, buscar interés reciente (noticias, búsquedas relacionadas, preguntas reales, temas populares de GTA), evitar basarse únicamente en noticias de baja relevancia y contrastar las afirmaciones. Si no hay métricas disponibles, no inventarlas ni afirmar que un tema es viral.

El primer plano y la primera frase deben mostrar o describir el descubrimiento de inmediato (0–2 s), sin introducción. Título específico que promete exactamente el hallazgo explicado; evitar "no vas a creer", porcentajes inventados, y "nadie lo sabe" sin evidencia. Explicar el resultado pronto y mantener interés con información NUEVA, demostración, ruta, pista o contexto concreto; no retener el dato artificialmente hasta el final. Escoger medios variados del propio juego y pertinentes para cada bloque: procurar 6–10 recursos distintos por vídeo de 40–50 s cuando haya evidencia visual suficiente, sin repetir ni inventar. No sacrificar coherencia visual para cumplir un número. Cierre breve y natural, sin pedir suscripción en todos los vídeos. Mantener la voz A Ximena y el límite técnico existente. Variar enfoques entre guía de hallazgo, prueba de mecánica, detalle visual, misterio resuelto y noticia con impacto concreto en el jugador. Humor natural, no automatizar el mismo remate. No publicar vídeos de relleno o versiones casi idénticas.

Si se dispone de estadísticas autorizadas de YouTube Studio, comparar por edad del vídeo (24 h y 7 días): mostrado en feed, porcentaje que decide quedarse, duración media, porcentaje medio visto, visualizaciones interesadas, comentarios/compartidos y fuentes de tráfico. Contrastar mejores y peores Shorts propios y aprovechar patrones sin copiar guiones. Usar 70 % de elección de ver y 85 % de visualización media únicamente como metas internas experimentales, nunca como umbrales oficiales o garantía de alcance. Si no hay Analytics, declarar esa limitación y no fingir tener acceso.

Continuidad: cada ejecución comprueba la antigüedad del último lote y el número real de pendientes. Si hay menos de cinco, preparar un lote de hasta cinco guiones nuevos de alta calidad, siempre que se puedan comprobar. No responder en silencio sin haber intentado investigar y guardar. Si faltan novedades, buscar descubrimientos de GTA anteriores con documentación suficiente; no relajar el control de fuentes ni crear duplicados. Si no se puede guardar un lote o iniciar GitHub Actions, informar del bloqueo concreto. Tras guardar, comprobar el commit [auto-shorts], el ID de la ejecución y, cuando esté disponible, el informe real; distinguir vista previa, programado y publicado. No cambiar OAuth, secretos, cuotas, facturación ni el historial.
