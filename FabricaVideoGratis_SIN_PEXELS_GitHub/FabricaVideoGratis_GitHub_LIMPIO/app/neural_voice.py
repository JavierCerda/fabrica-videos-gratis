"""Voz neural de Edge y tiempos de palabra; sin claves, facturación ni fallback de voz."""
import asyncio
import json
import os
import re
from pathlib import Path

from .pipeline import duration, log, run

VOICES=('es-ES-AlvaroNeural','es-MX-JorgeNeural')
DEFAULT_VOICE=VOICES[0]
DELIVERIES={
    'standard':{'rate':'-3%','pitch':'-2Hz','tail':.25},
    'story':{'rate':'+6%','pitch':'+0Hz','tail':.18},
    'deadpan':{'rate':'+0%','pitch':'-3Hz','tail':.28},
    'punchline':{'rate':'+3%','pitch':'+2Hz','tail':.32},
}


def spoken_tokens(text):
    return re.findall(r'\w+',text.casefold())


async def synthesize(text, path, voice, delivery='standard'):
    if delivery not in DELIVERIES:raise ValueError('Dirección de voz no admitida')
    settings=DELIVERIES[delivery]
    import edge_tts
    import edge_tts.communicate
    # Añadir las CA del sistema conserva la validación TLS en entornos con CA propia.
    edge_tts.communicate._SSL_CTX.load_default_certs()
    partial=path.with_suffix('.part.mp3');words=[]
    try:
        request=edge_tts.Communicate(text,voice,rate=settings['rate'],pitch=settings['pitch'],
            boundary='WordBoundary',connect_timeout=15,receive_timeout=45)
        with partial.open('wb') as stream:
            async for chunk in request.stream():
                if chunk['type']=='audio':stream.write(chunk['data'])
                elif chunk['type']=='WordBoundary':
                    words.append({'text':chunk['text'],'start':chunk['offset']/10_000_000,
                                  'end':(chunk['offset']+chunk['duration'])/10_000_000})
        if partial.stat().st_size<1000 or not words:raise RuntimeError('Voz o marcas de palabra vacías')
        if spoken_tokens(text)!=spoken_tokens(' '.join(w['text'] for w in words)):
            raise RuntimeError('La voz ha omitido o cambiado palabras del guion, incluidos los tacos')
        end=max(w['end'] for w in words)+settings['tail']
        run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(partial),'-t',f'{end:.6f}',
             '-ar','48000','-ac','1','-c:a','pcm_s16le',str(path)])
        if not 1<duration(path)<60:raise RuntimeError('Duración de voz inesperada')
        path.with_suffix('.words.json').write_text(json.dumps(words,ensure_ascii=False,indent=2),encoding='utf-8')
    finally:partial.unlink(missing_ok=True)


def narrate(topic,directory,voice_name=None):
    selected=voice_name or os.getenv('SHORT_VOICE') or DEFAULT_VOICE
    if selected not in VOICES:raise ValueError('La voz solicitada no pertenece al catálogo neural aprobado')
    paths=[];directions=[]
    for i,beat in enumerate(topic['beats']):
        path=Path(directory)/f'voz_{i:02d}.wav'
        delivery=beat.get('delivery','story' if topic.get('format')=='comedia_es' else 'standard')
        if delivery not in DELIVERIES:raise ValueError('Dirección de voz no admitida')
        try:asyncio.run(synthesize(beat['narration'],path,selected,delivery=delivery))
        except Exception as exc:
            raise RuntimeError('La voz neural no está disponible; se detiene sin usar las voces rechazadas') from exc
        paths.append(path);log(f'Voz neural {selected} {i+1}/{len(topic["beats"])}: {duration(path):.1f}s')
        directions.append({'beat':i,'delivery':delivery,**DELIVERIES[delivery]})
    return paths,{'engine':'Microsoft Edge neural / edge-tts','version':'7.3.1','voice':selected,
        'language':selected[:5],'directions':directions,'word_timestamps':True,
        'execution':'servicio online sin clave ni cuenta de facturación','fallback_enabled':False}


def auditions(directory):
    """Misma frase y mismo nivel para comparar timbres de dos regiones."""
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    text='Jason pasó por el ejército antes de llegar a los Keys. Lucía aprendió a pelear desde niña. Estos detalles aparecen en las fichas oficiales de Rockstar.'
    for label,voice in zip(('A','B'),VOICES):
        wav=directory/f'muestra_{label}.wav';asyncio.run(synthesize(text,wav,voice))
        run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(wav),
             '-af','loudnorm=I=-18:TP=-2:LRA=7','-ar','48000','-c:a','libmp3lame','-b:a','192k',
             str(directory/f'Voz_neural_{label}.mp3')])
    (directory/'voces.json').write_text(json.dumps(dict(zip(('A','B'),VOICES)),indent=2))


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--auditions',required=True)
    auditions(parser.parse_args().auditions)
