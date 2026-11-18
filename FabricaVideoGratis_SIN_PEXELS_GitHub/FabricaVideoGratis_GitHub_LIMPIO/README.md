# Fábrica gratuita de vídeos (versión sin Pexels)

Este proyecto genera guion y voz con **Gemini 2.5 Flash-Lite / Gemini 2.5 Flash Preview TTS** y obtiene fotografías y algunos vídeos **de Wikimedia Commons**, sin API key de imágenes. FFmpeg convierte fotos auténticas en planos con movimiento, monta subtítulos y crea un vídeo horizontal de unos 5 minutos. La miniatura y el MP4 se guardan como artefactos en GitHub Actions.

**No está comprobada la generación real completa con Gemini/Commons y depende de cuotas gratuitas.** No prometemos que cada ejecución sea satisfactoria o monetizable; el primer vídeo debe revisarse antes de publicarlo. La publicación en YouTube se deja DESACTIVADA en el workflow incluido.

## Para tu repositorio JavierCerda/fabrica-videos-gratis

1. La raíz de GitHub debe contener `.github/workflows/video_semanal.yml` y la carpeta `FabricaVideoGratis_GitHub_LIMPIO`.
2. Reemplaza el archivo ya existente `FabricaVideoGratis_GitHub_LIMPIO/app/pipeline.py` por la versión actualizada (se sube desde Code > Add file > Upload files o pegando el contenido en Edit this file).
3. Crea `.github/workflows/video_semanal.yml` en la raíz. La ejecución usa la carpeta donde ya has subido tus archivos.
4. **Revoke** la clave de Gemini compartida en el chat; crea OTRA sin facturación y guarda solo la nueva en GitHub Actions Secret `GEMINI_API_KEY`.
5. No necesitas clave `PEXELS_API_KEY`.
6. Abre Actions > Fabrica gratuita de videos > Run workflow. El vídeo se recupera en `contenido-generado` si todo sale bien.

### Voz VoxCPM2

Está conservado el notebook Colab `colab/VoxCPM2_FabricaVideo_Colab.ipynb`, con estilo de locución anciano ronco. El proceso programado usa Gemini TTS, ya que las GPU de Colab gratuito no son un servicio automático siempre disponible. No se afirma que sean voces idénticas.

### Licencias y calidad

El programa permite solo material etiquetado CC0, dominio público o CC BY, intenta conservar autor, fuente y licencia en `creditos_stock.json` y en la descripción. Verifica las licencias y atribuciones antes de publicar; metadatos pueden ser incorrectos, y fotografías ilustrativas no necesariamente son del dispositivo concreto mencionado.

### Coste

0 € si se respetan los niveles gratuitos de GitHub y Gemini y no se activa facturación. Las cuotas pueden cambiar o impedir generar un episodio. No promete ingreso alguno.
