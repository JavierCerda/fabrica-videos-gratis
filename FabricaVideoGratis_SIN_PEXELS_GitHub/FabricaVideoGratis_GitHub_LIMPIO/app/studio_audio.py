"""Narración serena y música instrumental original, todo en CPU local."""
import hashlib
import os
from pathlib import Path

import numpy as np
import requests
import soundfile as sf

from .pipeline import ROOT, duration, log

MODEL_FILES = {
    'kokoro-v1.0.onnx': ('beb0d1848dee9a49da392cc3df26958d46cfa35d321edf434f52949153f0df3a', 325505369),
    'voices-v1.0.bin': ('bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d', 28214398),
}
MODEL_BASE = 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/'
VOICE = 'em_alex'
VOICE_OPTIONS = ('em_alex','em_santa','im_nicola')


def ensure_kokoro():
    folder = ROOT/'.cache'/'kokoro'; folder.mkdir(parents=True, exist_ok=True)
    for name, (sha, size) in MODEL_FILES.items():
        p = folder/name
        if p.exists():
            with p.open('rb') as f: actual = hashlib.file_digest(f,'sha256').hexdigest()
            if actual == sha and p.stat().st_size == size: continue
        part = p.with_suffix(p.suffix+'.part'); count = 0; digest = hashlib.sha256()
        log('Descargando voz Kokoro: '+name)
        try:
            with requests.get(MODEL_BASE+name,stream=True,timeout=(15,90)) as r:
                r.raise_for_status()
                with part.open('wb') as f:
                    for data in r.iter_content(1024*1024):
                        count += len(data)
                        if count > size: raise ValueError('Modelo de voz superior al tamaño fijado')
                        f.write(data); digest.update(data)
            if count != size or digest.hexdigest() != sha: raise ValueError('Integridad de Kokoro incorrecta')
            part.replace(p)
        finally: part.unlink(missing_ok=True)
    return folder


def narrate(topic, directory, voice_name=None):
    from kokoro_onnx import Kokoro
    from kokoro_onnx.config import EspeakConfig
    import espeakng_loader
    import onnxruntime as ort
    voice_name=voice_name or os.getenv('SHORT_VOICE') or VOICE
    if voice_name not in VOICE_OPTIONS:raise ValueError('Voz fuera de las opciones revisadas')
    folder = ensure_kokoro()
    opts = ort.SessionOptions(); opts.intra_op_num_threads = 2; opts.inter_op_num_threads = 1
    session = ort.InferenceSession(str(folder/'kokoro-v1.0.onnx'),opts,providers=['CPUExecutionProvider'])
    voice = Kokoro.from_session(session, str(folder/'voices-v1.0.bin'),
        EspeakConfig(lib_path=espeakng_loader.get_library_path(),data_path=espeakng_loader.get_data_path()))
    paths = []
    for i, beat in enumerate(topic['beats']):
        # Registro masculino reposado; sin clonar ni imitar una persona real.
        samples, rate = voice.create(beat['narration'],voice=voice_name,speed=0.94,lang='es',sentence_pause=0.20,clause_pause=0.10)
        if not np.isfinite(samples).all() or len(samples)<rate: raise ValueError('Narración vacía o inválida')
        p=directory/f'voz_{i:02d}.wav'; sf.write(p,samples,rate,subtype='PCM_16'); paths.append(p)
        log(f'Kokoro {voice_name} {i+1}/{len(topic["beats"])}: {duration(p):.1f}s')
    return paths, {'engine':'kokoro-onnx','version':'0.6.1','model':'Kokoro-82M v1.0','voice':voice_name,
                   'language':'es','speed':0.94,'direction':'masculina, serena, cálida y con pausas discretas',
                   'model_license':'Apache-2.0','model_source':'https://huggingface.co/hexgrad/Kokoro-82M','execution':'local CPU'}


def compose_music(path, seconds, seed=2026, rate=48000):
    """Piano eléctrico, bajo y percusión suave. Notas y síntesis propias, sin samples."""
    rng=np.random.default_rng(seed); n=int(np.ceil(seconds*rate)); mono=np.zeros(n,dtype=np.float64)
    beat=60/88
    chords=[(45,[57,60,64,67,71]),(41,[57,60,64,65,69]),(48,[55,59,62,64,67]),(43,[55,59,62,64,69])]
    def add(start, midi, length, gain, kind='keys'):
        a=int(start*rate); count=min(int(length*rate),n-a)
        if a<0 or count<=0:return
        t=np.arange(count)/rate; f=440*2**((midi-69)/12)
        if kind=='bass':
            tone=np.sin(2*np.pi*f*t)+0.18*np.sin(4*np.pi*f*t)
            env=np.minimum(1,t/0.025)*np.exp(-t/0.55)
        else:
            tone=np.sin(2*np.pi*f*t)+0.28*np.sin(2*np.pi*2*f*t)*np.exp(-t*3)+0.07*np.sin(2*np.pi*3*f*t)
            env=np.minimum(1,t/0.012)*np.exp(-t/1.3)
        env*=np.minimum(1,(length-t)/0.12)
        mono[a:a+count]+=tone*env*gain
    bars=int(np.ceil(seconds/(beat*4)))
    for bar in range(bars):
        root,notes=chords[bar%len(chords)]; offset=bar*beat*4
        for j,note in enumerate(notes):add(offset+j*0.025,note,beat*3.5,0.035)
        add(offset,root,beat*1.2,0.065,'bass');add(offset+beat*2.5,root+12,beat*0.65,0.045,'bass')
        # Frases cortas originales, sin melodías o ritmos extraídos de GTA.
        if bar%2:
            for j,note in enumerate([notes[2]+12,notes[1]+12,notes[0]+12]):add(offset+(1.5+j*.5)*beat,note,beat*.6,.019)
        for j in range(8):
            a=int((offset+j*beat/2)*rate); size=min(int(rate*.06),n-a)
            if size<=0:continue
            noise=rng.normal(0,1,size); noise=np.concatenate(([0.],np.diff(noise)))
            mono[a:a+size]+=noise*np.exp(-np.arange(size)/(rate*.014))*.003
        for j in [0,2]:
            a=int((offset+j*beat)*rate); size=min(int(rate*.18),n-a)
            if size<=0:continue
            t=np.arange(size)/rate
            mono[a:a+size]+=np.sin(2*np.pi*(48*t+2.2*(1-np.exp(-t*30))))*np.exp(-t*30)*.028
    # Espacio estéreo discreto: eco propio, sin reverberaciones muestreadas.
    delay=int(rate*.16); right=mono*.94; right[delay:]+=mono[:-delay]*.12
    stereo=np.column_stack((mono,right));fade=min(int(rate*1.2),n//2)
    stereo[:fade]*=np.linspace(0,1,fade)[:,None];stereo[-fade:]*=np.linspace(1,0,fade)[:,None]
    peak=np.max(np.abs(stereo))
    if peak>0.9:stereo*=.9/peak
    sf.write(path,stereo,rate,subtype='PCM_16')
    return {'title':'Midnight Avenue','bpm':88,'origin':'composición y síntesis procedural originales del proyecto',
            'third_party_samples':False,'music_file':Path(path).name,'ducking':True,'mix_gain':1.8,'seed':seed}
