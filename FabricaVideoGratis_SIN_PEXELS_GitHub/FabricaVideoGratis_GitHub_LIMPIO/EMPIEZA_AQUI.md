# EMPIEZA AQUÍ — 0 € · Solo navegador

**Qué recibirás**: un MP4 de ~5 minutos cada miércoles, con voz sintética en español de España, clips REALES de Pexels y subtítulos. **Ninguna facturación habilitada**. Lo subirás automáticamente a YouTube solo si configuras OAuth y habilitas la variable de publicación.

1. Crea un repositorio **público** en https://github.com/new.
2. Extrae este ZIP y sube sus carpetas a GitHub (incluida `.github`). Nada se instala en tu ordenador.
3. En https://aistudio.google.com/api-keys crea una API Key en un proyecto **gratuito sin facturación**.
4. En https://www.pexels.com/api/ pide la API Key gratuita.
5. En GitHub > **Settings > Secrets and variables > Actions**, crea dos secretos: `GEMINI_API_KEY` y `PEXELS_API_KEY`. Nunca los pegues en chats ni archivos públicos.
6. En GitHub > **Actions > Fábrica gratuita de vídeos > Run workflow** ejecuta la primera prueba. Cuando termine, descarga el artefacto **contenido-generado**.
7. Mira el vídeo y comprueba voz, imágenes y hechos. **No active la publicación pública hasta que estés satisfecho.**
8. Si quieres subida automática, configura OAuth de YouTube según `README.md`, con `YOUTUBE_PRIVACY=private` en la primera prueba.

### Sobre tu voz VoxCPM2

El archivo `colab/VoxCPM2_FabricaVideo_Colab.ipynb` está preparado con tu método `VoxCPM.from_pretrained('openbmb/VoxCPM2', load_denoiser=False)`, voz de anciano, `cfg_value=2.0`, `inference_timesteps=16`.

- Para ejecutarla GRATIS en Colab debes abrir el navegador, obtener GPU gratuita si está disponible y pulsar Ejecutar todo.
- **No hay GPU garantizada ni ejecución desatendida gratis**, por lo que **la ejecución automática de GitHub utiliza Gemini TTS**.

### Qué está verificado

Se probó el montaje offline (FFmpeg + audio + subtítulos) y se creó un MP4 de prueba de 6 segundos. Todavía NO se han probado llamadas reales a Gemini, Pexels ni YouTube con tus claves. Los vídeos públicos NO están activados.

**No es una máquina de dinero garantizado.** Es un sistema de producción que necesita visualizaciones y cumplir las reglas de monetización.
