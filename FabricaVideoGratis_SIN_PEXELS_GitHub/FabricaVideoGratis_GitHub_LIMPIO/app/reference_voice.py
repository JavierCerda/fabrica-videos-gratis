"""VoxCPM2 con la referencia A1 del propietario; CPU local, sin API ni fallback."""
from functools import lru_cache
import hashlib
import json
import re
import subprocess
import time
from pathlib import Path
import numpy as np
from .pipeline import ROOT,duration,run

RUNTIME=ROOT/'.cache/voxcpm2'
PRECISE_ASR=('Systran/faster-whisper-medium','08e178d48790749d25932bbc082711ddcfdfbc4f')


def profile():
    return json.loads((ROOT/'config/voice_reference.json').read_text())


def digest(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def reference_file():
    config=profile();path=ROOT/config['reference']
    if not path.is_file() or digest(path)!=config['reference_sha256']:
        raise RuntimeError('La referencia de voz A1 no existe o ha cambiado; se detiene sin sustituirla')
    return path


def canonical(text):
    # Whisper puede escribir GTA 5 donde la voz dice GTA cinco.
    numbers=dict(zip('0123456789',['cero','uno','dos','tres','cuatro','cinco','seis','siete','ocho','nueve']))
    text=text.casefold().translate(str.maketrans('áéíóú','aeiou'))
    # GTA V y GTA cinco representan el mismo nombre pronunciado; V aislada no.
    roman={'ii':'dos','iii':'tres','iv':'cuatro','v':'cinco','vi':'seis'}
    text=re.sub(r'\bgta\s+(ii|iii|iv|vi|v)\b',lambda m:'gta '+roman[m[1]],text)
    tokens=re.findall(r'[^\W\d_]+|\d+',text,re.UNICODE)
    return [numbers.get(t,t) for t in tokens]


def recognized_groups(recognized):
    """Agrupar palabras sin duración propia en el intervalo real de su vecina."""
    result=[];pending=[]
    for word in recognized:
        if word['end']<word['start']:raise RuntimeError('Tiempos de voz no fiables')
        if word['end']==word['start']:
            pending.append(word);continue
        if pending:
            word={'text':' '.join(w['text'] for w in pending+[word]),
                'start':min(w['start'] for w in pending+[word]),'end':word['end']}
            pending=[]
        if result and word['start']<result[-1]['end']:
            previous=result.pop();word={'text':previous['text']+' '+word['text'],
                'start':previous['start'],'end':max(previous['end'],word['end'])}
        result.append(word)
    if pending:
        if not result:raise RuntimeError('Tiempos de voz no fiables')
        result[-1]['text']+=' '+' '.join(w['text'] for w in pending)
        result[-1]['end']=max(result[-1]['end'],pending[-1]['end'])
    return result


def checked_words(text,recognized):
    """Usar tiempos reconocidos en el audio; rechazar omisiones, sin inventar marcas."""
    labels=re.findall(r'\w+',text,re.UNICODE);expected=canonical(text)
    boundaries=[];count=0
    for label in labels:
        count+=len(canonical(label));boundaries.append(count)
    cursor=0;label_cursor=0;result=[];previous=0.;group_start=None
    for word in recognized_groups(recognized):
        tokens=canonical(word['text'])
        if not tokens:continue
        if tokens!=expected[cursor:cursor+len(tokens)]:
            wanted=' '.join(expected[cursor:cursor+len(tokens)])
            heard=' '.join(tokens)
            raise RuntimeError(f'El audio no coincide con el guion en la palabra {cursor+1}: '
                f'esperado {wanted!r}, reconocido {heard!r}')
        start=float(word['start']);end=float(word['end'])
        if end<=start or start<previous-.001:raise RuntimeError('Tiempos de voz no fiables')
        if group_start is None:group_start=start
        cursor+=len(tokens);previous=end
        if cursor in boundaries:
            final=boundaries.index(cursor)+1
            result.append({'text':' '.join(labels[label_cursor:final]),'start':group_start,'end':end})
            label_cursor=final;group_start=None
    if cursor!=len(expected):raise RuntimeError('La voz ha omitido el final del guion')
    return result


@lru_cache(maxsize=1)
def recognizer():
    from faster_whisper import WhisperModel
    p=profile()
    return WhisperModel(p['asr_repository'],revision=p['asr_revision'],device='cpu',
        compute_type='int8',cpu_threads=4,download_root=str(RUNTIME/'asr'))


@lru_cache(maxsize=1)
def precise_recognizer():
    from faster_whisper import WhisperModel
    return WhisperModel(PRECISE_ASR[0],revision=PRECISE_ASR[1],device='cpu',
        compute_type='int8',cpu_threads=4,download_root=str(RUNTIME/'asr'))


def recognize(path,text,precise=False):
    # Decodificar con FFmpeg evita incompatibilidades entre versiones de PyAV.
    raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-f','f32le','-ac','1','-ar','16000','-'])
    samples=np.frombuffer(raw,dtype=np.float32)
    model=precise_recognizer() if precise else recognizer()
    segments,_=model.transcribe(samples,language='es',beam_size=5,word_timestamps=True,
        vad_filter=False,initial_prompt=text)
    return [{'text':w.word,'start':w.start,'end':w.end} for s in segments for w in s.words]


def verified_recognition(path,text,directory):
    """Releer el mismo audio con un modelo mayor si falla; nunca dar palabras por dichas."""
    directory=Path(directory);p=profile()
    for precise,name,model in ((False,'reconocimiento_voz.json',(p['asr_repository'],p['asr_revision'])),
            (True,'reconocimiento_voz_segunda_pasada.json',PRECISE_ASR)):
        recognized=recognize(path,text,precise=precise)
        (directory/name).write_text(json.dumps(recognized,ensure_ascii=False,indent=2))
        try:words=checked_words(text,recognized)
        except RuntimeError:
            if precise:raise
            continue
        return words,{'asr_repository':model[0],'asr_revision':model[1],
            'word_alignment':model[0]+': reconocimiento con coincidencia léxica completa'}


def synthesize_reference(text,path):
    p=profile();reference=reference_file();path=Path(path)
    cli=RUNTIME/'engine/build/bin/voxcpm2-cli'
    models=[RUNTIME/'models'/w['name'] for w in p['weights']]
    if not cli.is_file() or not all(m.is_file() for m in models):
        raise RuntimeError('Falta preparar el motor VoxCPM2 gratuito; no se usa otra voz')
    prompt=path.with_name('referencia_a1.wav');raw=path.with_name('voz_generada.wav')
    run(['ffmpeg','-v','error','-y','-i',str(reference),'-ac','1','-ar','48000','-c:a','pcm_s16le',str(prompt)])
    start=time.monotonic();successful=False
    try:
        command=[str(cli),'--cpu','--seed',str(p['seed']),'--cfg',str(p['cfg']),
            '--timesteps',str(p['timesteps']),'--steps','450','-r',str(prompt),
            '-t',text,'-o',str(raw),*[str(m) for m in models]]
        with (path.parent/'voxcpm_generation.log').open('w') as stream:
            subprocess.run(command,stdout=stream,stderr=stream,check=True,timeout=900)
        seconds=duration(raw)
        if not 1<seconds<65:raise RuntimeError('La voz supera la duración admisible del Short')
        words,verification=verified_recognition(raw,text,path.parent)
        # Conservar una cola natural y retirar solo silencio tras la última palabra.
        end=min(seconds,words[-1]['end']+.25)
        run(['ffmpeg','-v','error','-y','-i',str(raw),'-t',f'{end:.6f}','-ac','1','-ar','48000','-c:a','pcm_s16le',str(path)])
        path.with_suffix('.words.json').write_text(json.dumps(words,ensure_ascii=False,indent=2))
        (path.parent/'reference_voice_info.json').write_text(json.dumps({
            'engine':'VoxCPM2 / llama.cpp-omni','voice':p['id'],'language':p['language'],
            'reference_sha256':p['reference_sha256'],'seed':p['seed'],'cfg':p['cfg'],
            'timesteps':p['timesteps'],'engine_revision':p['engine_revision'],
            'weights_revision':p['weights_revision'],'elapsed_seconds':time.monotonic()-start,
            **verification,
            'execution':'CPU local, sin API, clave, GPU de pago ni facturación','fallback_enabled':False},ensure_ascii=False,indent=2))
        successful=True
    finally:
        prompt.unlink(missing_ok=True)
        if successful:raw.unlink(missing_ok=True)
