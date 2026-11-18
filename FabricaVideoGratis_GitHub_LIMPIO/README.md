# FÁBRICA DE VÍDEOS — 0 € en software · Web · 5 minutos · 2026

Este proyecto intenta producir **un vídeo horizontal por semana** sobre compras inteligentes de tecnología: guion original documentado, **voz española sintética**, 40–80 cambios de plano de stock real, subtítulos y MP4 de aprox. cinco minutos. Opcionalmente sube el resultado a YouTube con OAuth.

> No se ha probado de extremo a extremo con las API reales porque faltan claves. Sí se ha probado la concatenación y exportación MP4 (ver `tests/smoke.py`). **No garantiza beneficios, audiencia ni funcionamiento gratuito ilimitado.**

## 1. Dos opciones de voz

| | GitHub Actions automático | Google Colab / VoxCPM2 |
|---|---|---|
| Funciona en navegador | ✅ | ✅ |
| Instalar algo en tu PC | ❌ | ❌ |
| Coste software | Gratis **dentro de cuotas** | Gratis **si Colab ofrece GPU gratuita** |
| Voz | **Gemini 2.5 Flash Preview TTS**, estilo anciano graciosillo | **VoxCPM2**, tu modelo y semilla descriptiva |
| Se ejecuta sin que pulses nada semanalmente | ✅, con límites de servicio | ❌, Colab necesita abrir sesión y ejecutar |
| Da dinero garantizado | ❌ | ❌ |

**No existe una garantía creíble de ejecución semanal indefinida de VoxCPM2 con GPU gratis sin que nadie intervenga.** Por eso el modo realmente programado usa Gemini TTS de nivel gratuito. **No se usa Edge TTS:** sus derechos de uso comercial en ese contexto no están confirmados.

## 2. Dejar funcionando GitHub Actions SIN instalar nada

1. Accede a [github.com/new](https://github.com/new), crea un repositorio **público**, por ejemplo `fabrica-videos-gratis`. En público, las ejecuciones estándar de Actions son gratuitas según la documentación actual de GitHub. No subas archivos personales.
2. Descarga y extrae el ZIP en tu equipo **únicamente para subir los archivos** (no hay software que instalar). En GitHub, **Add file → Upload files** y arrastra todo el contenido de la carpeta `FabricaVideoGratis`, incluida `.github`. Si el navegador omite la carpeta oculta, crea el archivo `.github/workflows/video_semanal.yml` mediante **Add file → Create new file** copiando su contenido.
3. Abre [Google AI Studio — API Keys](https://aistudio.google.com/api-keys), genera una clave en un proyecto **sin facturación habilitada**. Si la cuota de nivel gratuito no está disponible para tu cuenta o región, **detente; no actives pago**.
4. Solicita la [clave de Pexels API](https://www.pexels.com/api/), gratuita con límites. Pexels es quien suministra los **vídeos de personas reales**.
5. GitHub → tu repo → **Settings → Secrets and variables → Actions → New repository secret**: crea los secretos `GEMINI_API_KEY` y `PEXELS_API_KEY`. **Jamás los pongas en los archivos del repositorio ni en un mensaje de ChatGPT.**
6. Ve a **Actions** y activa los workflows cuando GitHub lo pida. Abre **Fabrica gratuita de vídeos → Run workflow** (prueba inicial manual desde navegador). Si finaliza correctamente, abajo aparecerá un artefacto **contenido-generado** con el MP4, guion, subtítulos y créditos.
7. Una vez comprobada la calidad, el workflow programado se ejecuta **los miércoles a las 17:17 UTC**, aproximadamente a las 18:17/19:17 en España según la época del año. Por defecto **NO publica**: es deliberado hasta comprobar calidad y licencias.

## 3. Publicación automática en YouTube (solo cuando estés conforme)

Si decides autorizarla, el programa tiene el código de subida oficial. Requiere **una configuración OAuth inicial en Google Cloud** (no basta un API key). Los tres secretos que acepta son:

- `YT_CLIENT_ID`
- `YT_CLIENT_SECRET`
- `YT_REFRESH_TOKEN`

Activa una variable de repositorio **Settings → Secrets and variables → Actions → Variables**:

- `YOUTUBE_UPLOAD` = `true`
- `YOUTUBE_PRIVACY` = `private` (recomendado para la primera prueba); cambia a `public` solo cuando quieras publicar automáticamente bajo tu responsabilidad.

El token necesita permisos `youtube.upload` autorizados en el navegador. Puedes obtener el refresh token tras configurar un cliente OAuth en Google Cloud y una autorización propia (por ejemplo con OAuth 2.0 Playground y *Use your own OAuth credentials*). **No proporciones ninguna contraseña ni token en el chat.** La autorización de proyectos externos que sigan en modo *Testing* puede tener caducidad breve; tendrás que publicar correctamente la aplicación OAuth para una programación estable. No hay método de publicar automáticamente sin autorización inicial del canal.

API YouTube: https://developers.google.com/youtube/data/reference/rest/v3/videos/insert

## 4. Cómo funciona la generación

1. Selecciona el siguiente de **12 temas verificados**, uno por semana. Una vez agotado el catálogo, **se detiene** y pide nuevas ideas, en vez de duplicar contenido.
2. Lee **fuentes oficiales** (Apple, Microsoft, Google o PlayStation) para no inventar fechas, precios o especificaciones.
3. Gemini Flash-Lite genera **12 secciones de 58–66 palabras**, con 650–820 palabras de narración total y 12 consultas visuales descriptivas.
4. Gemini Flash TTS genera 12 segmentos con voz grave, de personaje original y tono algo sarcástico. (En Colab VoxCPM2 hace esta etapa.)
5. Descarga **clips reales** de Pexels API, 2–4 por sección y los intercala cada ~4,4 segundos; no utiliza ilustraciones de relleno de la IA.
6. FFmpeg monta a **1920×1080, 25 FPS, H.264/AAC**, incrusta subtítulos y normaliza la voz. El audio fija la duración real; si excede el rango previsto, no publica. Genera además una miniatura automática sin inventar cifras de ingresos ni fotografías de producto.
7. Genera miniatura horizontal a partir de un fotograma de stock, descripción con fuentes y créditos del material audiovisual. Exporta MP4 y, solo si activaste OAuth, sube a YouTube junto a la miniatura cuando el canal lo permite.

**Importante:** no se comprueba automáticamente si cada clip de stock representa el dispositivo exacto del guion. Se trata de *B-roll ilustrativo*. Evita vídeos afirmando que estás mostrando una prueba real si no la hay. YouTube puede rechazar la monetización del contenido repetitivo o demasiado automatizado. Revisa al menos los primeros vídeos antes de hacer pública la automatización.

## 5. Voz con tu VoxCPM2 en un navegador

Abre [Google Colab](https://colab.research.google.com/), selecciona **Archivo → Subir cuaderno**, y sube `colab/VoxCPM2_FabricaVideo_Colab.ipynb`. Si Google te ofrece GPU gratuita T4, ejecútalo.

El cuaderno descarga **VoxCPM2**, pide tu ZIP y dos claves en entradas privadas de Colab, genera la narración con tu voz descrita, monta los vídeos y ofrece el MP4 terminado. **La ejecución es manual**, porque la GPU gratuita de Colab es temporal y no sirve como servidor de producción garantizado.

Tu voz original de prueba, conservada en `VOICE_PROVIDER=voxcpm`:

```python
model = VoxCPM.from_pretrained('openbmb/VoxCPM2', load_denoiser=False)
wav = model.generate(
    text='(An elderly man, rough scratchy voice, worn out and hoarse, grumpy but funny, unhurried) '
         + narracion,
    cfg_value=2.0,
    inference_timesteps=16,
)
```

## 6. Costes, límites y seguridad

- **0 €** solo si no activas facturación y te mantienes en los niveles gratuitos. Gemini y Pexels aplican cuotas. Los workflows pueden fallar, retrasarse o dejar de ejecutarse. 
- GitHub **desactiva workflows programados en repos públicos sin actividad durante 60 días**. El proyecto registra un commit de actividad **solo al terminar correctamente** cada vídeo; si falla durante 60 días, necesitarás reactivarlo desde GitHub. No es hosting garantizado 24/7.
- Pexels aporta clips auténticos, pero no implica que haya material adecuado para todos los dispositivos; la generación se cancela si no encuentra suficientes.
- El vídeo no genera ingresos por sí solo: un canal nuevo necesita crecer y cumplir las reglas de YouTube. Ni los vídeos ni la IA garantizan 300 €/mes.
- **Nunca incluyas claves en un repositorio público.** No envíes tu guion completo a Gemini si contiene información privada. El nivel gratuito de Gemini puede utilizar datos para mejorar servicios, según sus condiciones.

## 7. Prueba rápida del motor sin API

Dentro de un entorno con `ffmpeg` y Python:

```bash
python tests/smoke.py
```

Prueba realizada en la preparación de este paquete: generó un MP4 de 6,17 segundos con vídeo real de prueba, dos audios simulados y subtítulos; sin red ni claves.

## 8. Archivos clave

- `app/pipeline.py` — sistema completo
- `topics/topics.json` — 12 ideas con fuentes oficiales
- `.github/workflows/video_semanal.yml` — automatización en servidor de GitHub
- `colab/VoxCPM2_FabricaVideo_Colab.ipynb` — opción VoxCPM2 desde navegador
- `tests/smoke.py` — prueba de render sin claves

### Fuentes de políticas y documentación

- https://docs.github.com/en/actions/reference/runners/github-hosted-runners
- https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- https://ai.google.dev/gemini-api/docs/pricing
- https://www.pexels.com/api/documentation/
- https://github.com/OpenBMB/VoxCPM
- https://support.google.com/youtube/answer/1311392
