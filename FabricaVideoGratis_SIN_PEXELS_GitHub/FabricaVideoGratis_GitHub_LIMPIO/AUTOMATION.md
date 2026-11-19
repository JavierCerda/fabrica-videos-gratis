# Contrato del investigador horario

Repositorio: JavierCerda/fabrica-videos-gratis. Directorio de trabajo:
`FabricaVideoGratis_SIN_PEXELS_GitHub/FabricaVideoGratis_GitHub_LIMPIO`.

Cada ciclo debe leer este contrato, `config/automation.json`, `topics/inbox.json`
y `automation-state.json` en la rama `production-state` cuando exista. Investigar
novedades de toda la saga GTA mediante búsqueda web actual, abrir las fuentes y
comprobar la fecha real de publicación. Priorizar fuentes originales: Rockstar,
Take-Two, PlayStation, Xbox, Nintendo, Steam; Reuters y AP para sus propias noticias.
No confundir una fecha de rastreo, de actualización general o un rumor con un hecho.

Preparar cinco Shorts originales. Intentar que al menos tres traten noticias
publicadas en el día local de Europe/Madrid cuando existan tres noticias distintas
sin publicar. Si faltan, completar con curiosidades interesantes de toda la saga.
No repetir noticias con otro titular, ni hechos del historial o la cola. No inventar
noticias para llenar cinco huecos. Con fuentes insuficientes, escribir menos.
Si hay 240 guiones pendientes, no añadir más; informar de la cola y la cuota.

La narración es español de España, con humor adulto original y muchos tacos,
sin pitidos, insultos a colectivos ni imitación de una persona real. El público
no tiene que oír una lista de fuentes: incorporar atribución breve cuando haga
falta. Distinguir las comparaciones cómicas de hechos y mecánicas. Sin spoilers
importantes, cifras no comprobadas ni supuestas filtraciones. No usar hoy, mañana,
ayer, esta noche ni esta semana: los vídeos pueden quedar en cola. Las fechas
relevantes deben ser explícitas. Cada guion tiene cinco bloques y entre 95 y 125
palabras en total, al menos ocho tacos del conjunto que revisa app/quality.py.
Título SEO natural, sin promesas falsas, hasta 90 caracteres. Display title corto,
legible, hasta 65 caracteres; preferir 4–7 palabras. Solo una curiosidad central.

Perfil editorial actual: `editorial_version: 2` en cada tema. Explicar el dato
como a alguien que no conoce el juego: vocabulario corriente, una idea por frase,
frases de hasta 22 palabras y media de hasta 14. Cinco bloques: gancho claro,
explicación, ejemplo sencillo, consecuencia y remate. No recitar verificaciones,
reservas, fuentes ni aclaraciones sobre las bromas. Separar hechos y chistes en
editorial; los tacos no deben ocultar el dato ni reemplazar una explicación.
La voz elegida es `es-ES-AlvaroNeural`: narrador masculino español, elegante,
limpio y de ritmo pausado, con rate -6% y pitch -4Hz. Mantener esa misma voz
en todas las tomas; no cambiarla desde la investigación ni usar las voces rechazadas.
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
      "format": "comedia_es",
      "content_type": "news",
      "published_at": "FECHA_REAL_PUBLICACION_UTC_ISO8601",
      "news_date_label": "18 NOV · NOTICIA",
      "sources": ["URL_PRIMARIA_LEIDA"],
      "editorial": {
        "facts": ["Hecho comprobado y parafraseado."],
        "jokes": ["Comparaciones inventadas del narrador, no hechos del juego."]
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

La muestra abrevia beats: hay que escribir los cinco bloques reales. En una
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
el mismo paquete de imágenes en todos los temas. Usar tres o más recursos distintos
relacionados. Se pueden mezclar vídeos oficiales y fotos; para vídeos indicar start
y max_seconds realmente comprobados, nunca estirar, ralentizar o repetir un clip
para rellenar. Elegir `fit: contain` si cortar a cuadrado oculta detalles: conserva
la fuente completa dentro del marco sobre un fondo desenfocado del mismo recurso.
No forzar vídeo si solo hay fotos adecuadas; elegir otro tema si faltan medios.
Los borradores anteriores al perfil 2 permanecen conservados y no se publican.
GTA VI: índices 0–5 lugares; 6–8 Jason; 9–11 Lucía; 12–13 pareja; 14–17 Cal;
18–21 Brian. Los otros catálogos de Steam se enumeran en game_data, con screenshots
reales, cada index debe existir. Mantener solo el juego de allowed_games.
No usar los clips de 0,8 segundos. Preferir tres o más imágenes distintas del tema.
Para los títulos sin catálogo Steam disponible, cada visual también necesita
image_url y source_page oficiales leídas/verificadas; tamaño mínimo de la fuente
720 píxeles en su dimensión menor. Los servidores autorizados están en
EDITORIAL_IMAGE_HOSTS. No usar un GTA diferente, stock genérico ni imágenes de
terceros sin permiso. Si no se consigue material adecuado, elegir otro tema.

Guardar el lote con un commit cuyo mensaje empiece por `[auto-shorts]` para que
Actions ejecute producción. No modificar código, workflow, permisos, secretos,
cuotas ni el historial desde la investigación. Usar exclusivamente herramientas
GitHub autorizadas. Consultar el resultado del commit y comprobar que arrancó la
ejecución. Si falta acceso o una conexión, informar; no fingir publicación.
No enviar mensajes a terceros. No cobrar ni activar facturación. No pedir edición
manual de archivos. No dar por publicados los vídeos hasta que existan IDs y
programación confirmada de YouTube en el historial.
