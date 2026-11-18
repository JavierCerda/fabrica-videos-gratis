# Fábrica gratuita de vídeos (versión sin Pexels)

Este proyecto genera guion y voz con **Gemini 3.1 Flash-Lite (guion) y Piper local (voz española)** y obtiene fotografías y algunos vídeos **de Wikimedia Commons**, sin API key de imágenes. FFmpeg convierte fotos auténticas en planos con movimiento, monta subtítulos y crea un vídeo horizontal de unos 5 minutos. La miniatura y el MP4 se guardan como artefactos en GitHub Actions.

**No está comprobada la generación real completa con Gemini/Commons y depende de cuotas gratuitas.** No prometemos que cada ejecución sea satisfactoria o monetizable; el primer vídeo debe revisarse antes de publicarlo. La publicación en YouTube se deja DESACTIVADA en el workflow incluido.

## Ejecutar en GitHub

El workflow está en `.github/workflows/video_semanal.yml`. El código se encuentra en
`FabricaVideoGratis_SIN_PEXELS_GitHub/FabricaVideoGratis_GitHub_LIMPIO/`.

1. Guarda una clave propia del nivel gratuito como secreto `GEMINI_API_KEY`. No subas claves al repositorio; revoca cualquier clave que hayas compartido públicamente.
2. Abre **Actions > Fabrica gratuita de videos > Run workflow** y selecciona `main`.
3. Al terminar, descarga el artefacto **contenido-generado**. Incluye el MP4, miniatura, guion, metadatos, subtítulos, créditos y las voces que se hayan generado.

No hace falta una clave de Pexels ni configurar YouTube. `YOUTUBE_UPLOAD=false`
permanece fijado en el workflow. También se conserva la ejecución semanal existente.

Antes de generar se ejecutan las pruebas de regresión y una prueba real de montaje
sin servicios externos. El runner usa Ubuntu 24.04. Primero se comprueba el material
multimedia y después se genera la voz, para evitar consumir cuota de voz si falla Wikimedia.

### Modelos y descargas

El modelo de texto predeterminado es `gemini-3.1-flash-lite`; ante un HTTP 404 se
prueba `gemini-3-flash-preview`. La voz predeterminada es Piper `es_ES-davefx-medium`, generada en CPU sin una API de voz. Opcionalmente se conserva `gemini-2.5-flash-preview-tts`; ante 404/429 se regenera todo el episodio con Piper para no mezclar voces.
Solo se aceptan los modelos incluidos en la lista con nivel gratuito documentado
en [los precios de Gemini](https://ai.google.dev/gemini-api/docs/pricing).
Los errores de cuota no provocan un cambio a un modelo premium ni activan facturación.

Wikimedia usa sus CDN oficiales `upload.wikimedia.org` y `thumb.wikimedia.org`.
Se espacian las peticiones, se guardan búsquedas y descargas en caché durante cada ejecución y se respeta
`Retry-After`; si el límite persiste, el proceso se detiene. Los archivos válidos
pueden reutilizarse en distintas secciones con planos diferentes.

Si el conector devuelve `403 Resource not accessible by integration`, comprueba
que **ChatGPT Codex Connector esté instalado en la cuenta propietaria del repositorio**
y tenga acceso a este repositorio. Autorizar la cuenta y tener la aplicación
instalada son pasos diferentes.

### Voz local sin cuota

Se usa `piper-tts==1.8.0` y la revisión fijada
`0ca208afc2a2ee102b1e961e72e0a7e4907be3d0` de la voz española davefx.
Esa versión procede de la base rdh y datos CC0. Se verifican los SHA-256 del
modelo, la configuración y su MODEL_CARD antes de cargarlo. La primera ejecución
descarga unos 63 MB; la síntesis posterior ocurre dentro del runner, sin GPU,
sin clave de voz y sin activar facturación. Su timbre es distinto de Gemini Charon.

La cuota gratuita diaria de Gemini TTS puede impedir completar doce secciones;
por ese motivo no es el motor predeterminado. El proveedor real queda registrado
en `guion.json` y `metadata.json`.

### Voz VoxCPM2

Está conservado el notebook Colab `colab/VoxCPM2_FabricaVideo_Colab.ipynb`, con estilo de locución anciano ronco. El proceso programado usa Piper en CPU, ya que las GPU de Colab gratuito no son un servicio automático siempre disponible. No se afirma que sean voces idénticas.

### Licencias y calidad

El programa permite solo material etiquetado CC0, dominio público o CC BY, intenta conservar autor, fuente y licencia en `creditos_stock.json` y en la descripción. Verifica las licencias y atribuciones antes de publicar; metadatos pueden ser incorrectos, y fotografías ilustrativas no necesariamente son del dispositivo concreto mencionado.

### Coste

0 € si se respetan los niveles gratuitos de GitHub y Gemini y no se activa facturación. Las cuotas pueden cambiar o impedir generar un episodio. No promete ingreso alguno.
