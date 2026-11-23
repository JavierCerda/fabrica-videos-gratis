"""Previsualización aislada: NO usa la cola ni ninguna API de subida."""
import datetime as dt
import json
import os
from pathlib import Path

from app.pipeline import ROOT, OUT, duration
from app.editorial_queue import validate_topic, timestamp
from app.quality import inspect
from app.studio import produce

TOPIC_PATH = ROOT / 'experiments/comedy_preview/topic.json'
TARGET_VOICE = 'es-ES-XimenaNeural'


def main():
    if os.getenv('RUN_MODE', 'preview') != 'preview':
        raise RuntimeError('Esta prueba solo permite RUN_MODE=preview')
    if os.getenv('SHORT_VOICE') != TARGET_VOICE:
        raise RuntimeError('La prueba requiere SHORT_VOICE=' + TARGET_VOICE)
    topic = json.loads(TOPIC_PATH.read_text(encoding='utf-8'))
    config = json.loads((ROOT / 'config/automation.json').read_text(encoding='utf-8'))
    config['editorial_version'] = 4
    # Es un dato evergreen aprobado previamente, no una noticia de última hora.
    validate_topic(topic, timestamp(topic['research']['verified_at']), config)
    output = OUT / 'muestra-comedia-voz'
    video = produce(topic, output)
    result = inspect(video)
    if not result['passed']:
        raise RuntimeError('La muestra no pasa el control de calidad; no se publica')
    metadata = json.loads((video.parent / 'metadata.json').read_text(encoding='utf-8'))
    if metadata['voice']['voice'] != TARGET_VOICE:
        raise RuntimeError('La muestra no utilizó la nueva voz')
    report = {
        'status': 'preview_only', 'youtube_uploaded': False,
        'voice': TARGET_VOICE, 'seconds': round(duration(video), 2),
        'title': topic['title'], 'quality_passed': True,
        'video_path': str(video),
        'fact_source': topic['sources'],
    }
    (output / 'preview_report.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))
    print('Vista previa creada. SIN credenciales de YouTube, sin publicación y sin modificar production-state.')


if __name__ == '__main__':
    main()
