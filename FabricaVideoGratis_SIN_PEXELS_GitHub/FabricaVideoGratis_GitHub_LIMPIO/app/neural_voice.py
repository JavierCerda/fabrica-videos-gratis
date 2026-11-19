"""Narrador español elegante y tomas continuas con tiempos de palabra verificados."""
import asyncio
import json
import os
import re
from pathlib import Path
import soundfile as sf

from .pipeline import duration, log, run
from .continuity import tighten_pauses

VOICES=('es-ES-AlvaroNeural','voxcpm2-a1','es-ES-XimenaNeural','es-ES-ElviraNeural')
DEFAULT_VOICE=VOICES[0]
DELIVERIES={
    'standard':{'rate':'-2%','pitch':'+0Hz','tail':.25},
    'story':{'rate':'-2%','pitch':'+0Hz','tail':.25},
    'deadpan':{'rate':'-2%','pitch':'+0Hz','tail':.25},
    'punchline':{'rate':'-2%','pitch':'+0Hz','tail':.25},
}


def spoken_tokens(text):
    return re.findall(r'\w+',text.casefold())


async def synthesize(text, path, voice, delivery='standard'):
    if delivery not in DELIVERIES:raise ValueError('Dirección de voz no admitida')
    if voice=='voxcpm2-a1':
        from .reference_voice import synthesize_reference
        synthesize_reference(text,path)
        return
    settings=DELIVERIES[delivery]
    if voice=='es-ES-AlvaroNeural':settings={**settings,'rate':'-6%','pitch':'-4Hz'}
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
    directory=Path(directory)
    for beat in topic['beats']:
        if beat.get('delivery','standard') not in DELIVERIES:raise ValueError('Dirección de voz no admitida')
    # Una única toma: no reiniciar timbre, tono ni ritmo en cada bloque del guion.
    full=directory/'toma_continua.wav'
    text=' '.join(b['narration'] for b in topic['beats'])
    verification={}
    try:
        asyncio.run(synthesize(text,full,selected,delivery='punchline' if topic.get('format')=='comedia_es' else 'standard'))
        if selected=='es-ES-AlvaroNeural':
            from .reference_voice import verified_recognition
            _,verification=verified_recognition(full,text,directory)
    except Exception as exc:
        raise RuntimeError('La voz neural no está disponible; se detiene sin usar las voces rechazadas') from exc
    samples,rate=sf.read(full,dtype='float64')
    words=json.loads(full.with_suffix('.words.json').read_text())
    samples,words,edits=tighten_pauses(samples,rate,words)
    sf.write(full,samples,rate,subtype='PCM_16')
    full.with_suffix('.words.json').write_text(json.dumps(words,ensure_ascii=False,indent=2))
    paths=[];directions=[];word_index=0;sample_start=0
    for i,beat in enumerate(topic['beats']):
        path=Path(directory)/f'voz_{i:02d}.wav'
        count=len(spoken_tokens(beat['narration']));end=word_index
        tokens=0
        while tokens<count and end<len(words):
            tokens+=len(spoken_tokens(words[end]['text']));end+=1
        group=words[word_index:end]
        if spoken_tokens(beat['narration'])!=spoken_tokens(' '.join(w['text'] for w in group)):
            raise ValueError('Las palabras del bloque no coinciden con la toma continua')
        sample_end=round((group[-1]['end']+words[end]['start'])/2*rate) if end<len(words) else len(samples)
        sf.write(path,samples[sample_start:sample_end],rate,subtype='PCM_16')
        # Restar índices enteros evita tiempos negativos por redondeo en límites contiguos.
        local=[{**w,'start':(round(w['start']*rate)-sample_start)/rate,
                'end':(round(w['end']*rate)-sample_start)/rate} for w in group]
        path.with_suffix('.words.json').write_text(json.dumps(local,ensure_ascii=False,indent=2))
        paths.append(path);log(f'Voz neural {selected} {i+1}/{len(topic["beats"])}: {duration(path):.1f}s')
        directions.append({'beat':i,'delivery':'continuous','same_take':True})
        word_index=end;sample_start=sample_end
    if word_index!=len(words):raise ValueError('Sobran palabras al dividir la toma continua')
    metadata={'engine':'Microsoft Edge neural / edge-tts','version':'7.3.1','voice':selected,
        'language':selected[:5],'directions':directions,'word_timestamps':True,
        'continuous_take':True,'pause_editing':edits,
        'execution':'servicio online sin clave ni cuenta de facturación','fallback_enabled':False}
    metadata.update(verification)
    if selected=='es-ES-AlvaroNeural':
        metadata.update(style='Narrador masculino elegante, dicción española clara',rate='-6%',pitch='-4Hz')
    if selected=='voxcpm2-a1':
        metadata.update(json.loads((directory/'reference_voice_info.json').read_text()))
        metadata['version']=metadata['engine_revision'][:12]
    return paths,metadata


def auditions(directory):
    """Muestra del narrador español seleccionado, sin cambiar de voz."""
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    text='Jason pasó por el ejército antes de llegar a los Keys. Lucía aprendió a pelear desde niña. Estos detalles aparecen en las fichas oficiales de Rockstar.'
    for label,voice in [('A',DEFAULT_VOICE)]:
        wav=directory/f'muestra_{label}.wav';asyncio.run(synthesize(text,wav,voice))
        run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(wav),
             '-af','loudnorm=I=-18:TP=-2:LRA=7','-ar','48000','-c:a','libmp3lame','-b:a','192k',
             str(directory/f'Voz_neural_{label}.mp3')])
    (directory/'voces.json').write_text(json.dumps({'A':DEFAULT_VOICE},indent=2))


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--auditions',required=True)
    auditions(parser.parse_args().auditions)
