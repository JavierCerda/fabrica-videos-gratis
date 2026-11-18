# Referencia A1

`voz_a_1.flac` conserva sin pérdida las muestras PCM del primer WAV adjuntado
por el propietario (`descarga.wav`, 10,24 segundos, 48 kHz mono).
Es la referencia sintética elegida de VoxCPM2, descripción a, semilla 1.
No se vuelve a diseñar una voz aleatoria a partir de la descripción en cada vídeo.
El segundo WAV se conserva en los archivos originales del propietario y no se
selecciona automáticamente como alternativa.

El SHA256 de la referencia, el del WAV original y los parámetros del motor
están en `config/voice_reference.json`. Los pesos proceden de VoxCPM2
(OpenBMB, Apache-2.0), convertidos a GGUF por el proyecto enlazado desde su
documentación oficial. Los modelos se descargan al preparar el motor y nunca
se incluyen en los commits.
