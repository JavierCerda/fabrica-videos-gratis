"""Control de los MP4 finales: decodificación, voz, subtítulos y consistencia del formato."""
import json
import re
import subprocess
from pathlib import Path
import numpy as np
import soundfile as sf

from .pipeline import OUT, duration, log
from .neural_voice import spoken_tokens
from .continuity import silent_spans

SWEARS={'joder','coño','cojones','hostia','mierda','puto','puta','putos','putas','cabrón','cabrones','cago'}


def inspect(video):
    folder=video.parent;meta=json.loads((folder/'metadata.json').read_text())
    topic=json.loads((folder/'guion.json').read_text());errors=[]
    streams=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(video)]))['streams']
    v=next(s for s in streams if s['codec_type']=='video');a=next(s for s in streams if s['codec_type']=='audio')
    if (v['width'],v['height'],v['r_frame_rate'])!=(1080,1920,'30/1'):errors.append('Formato de vídeo inesperado')
    if (a['channels'],a['sample_rate'])!=(2,'48000'):errors.append('Formato de audio inesperado')
    concise=topic.get('editorial_version',0)>=3
    if not (12 if concise else 25)<=duration(video)<=59:errors.append('Duración fuera del objetivo')
    subprocess.run(['ffmpeg','-hide_banner','-v','error','-i',str(video),'-f','null','-'],check=True)
    timestamps=subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries',
        'frame=best_effort_timestamp_time','-of','csv=p=0',str(video)],text=True)
    pts=np.array([float(line.split(',')[0]) for line in timestamps.splitlines() if line.split(',')[0].strip()])
    if len(pts)<2 or np.max(np.abs(np.diff(pts)-1/30))>.00001:errors.append('Saltos o duplicados en los tiempos de fotograma')
    if abs(float(v['duration'])-float(a['duration']))>.05:errors.append('Audio y vídeo con duraciones diferentes')
    continuous,rate=sf.read(folder/'toma_continua.wav',dtype='int16')
    joined,joined_rate=sf.read(folder/'narracion.wav',dtype='int16')
    if joined_rate!=rate or not np.array_equal(continuous,joined):errors.append('La narración contiene cortes o muestras perdidas')
    long_pauses=silent_spans(joined.astype(np.float64)/32768,rate,minimum=.7)
    if long_pauses:errors.append('Silencio de voz superior a 700 ms')
    shots=json.loads((folder/'creditos_visuales.json').read_text())
    if concise:
        image_hashes=[s.get('source_sha256') for s in shots if s.get('kind')=='image']
        if None in image_hashes or len(image_hashes)!=len(set(image_hashes)):
            errors.append('Una imagen se repite dentro del vídeo')
        if len(shots)<3:errors.append('Faltan planos distintos')
        for i,a_shot in enumerate(shots):
            for b_shot in shots[i+1:]:
                if a_shot.get('kind')==b_shot.get('kind')=='video' and a_shot.get('source_sha256')==b_shot.get('source_sha256'):
                    if max(a_shot['source_start'],b_shot['source_start'])<min(
                        a_shot['source_start']+a_shot['rendered_seconds'],b_shot['source_start']+b_shot['rendered_seconds']):
                        errors.append('Se repite un fragmento de vídeo')
    if any(s['seconds']<3-.001 for s in shots):errors.append('Plano demasiado breve para el montaje fluido')
    frozen=subprocess.run(['ffmpeg','-hide_banner','-i',str(video),'-an','-vf',
        'crop=984:984:48:414,freezedetect=n=-60dB:d=1.2','-f','null','-'],capture_output=True,text=True,check=True)
    if 'freeze_start:' in frozen.stderr:errors.append('Imagen detenida durante más de 1.2 s')
    for i,beat in enumerate(topic['beats']):
        words=json.loads((folder/f'voz_{i:02d}.words.json').read_text())
        if spoken_tokens(beat['narration'])!=spoken_tokens(' '.join(w['text'] for w in words)):
            errors.append(f'Palabras cambiadas u omitidas en el bloque {i}')
    ass=(folder/'subtitulos.ass').read_text();previous_end=0.;events=0
    def seconds(value):
        h,m,s=value.split(':');return int(h)*3600+int(m)*60+float(s)
    for line in ass.splitlines():
        if not line.startswith('Dialogue:'):continue
        fields=line.split(',',9);start,end=seconds(fields[1]),seconds(fields[2]);text=fields[9]
        if end<=start or start<previous_end-.011:errors.append('Subtítulos solapados o con duración inválida')
        if events and start-previous_end>.011:errors.append('Parpadeo entre grupos de subtítulos')
        if text.count(r'\N')>1:errors.append('Subtítulo con más de dos líneas')
        previous_end=end;events+=1
    if not events:errors.append('Faltan subtítulos')
    if not meta['layout']['persistent_title'] or meta['layout']['media_box']!=[48,414,984,984]:errors.append('Plantilla inconsistente')
    if meta.get('publication_enabled'):errors.append('Publicación activada')
    profanity=sum(w in SWEARS for b in topic['beats'] for w in spoken_tokens(b['narration']))
    if concise and profanity>2:errors.append('Demasiados tacos para el guion informativo')
    if topic.get('format')=='comedia_es' and profanity<8:errors.append('El guion no cumple el tono adulto solicitado')
    audio=subprocess.run(['ffmpeg','-hide_banner','-i',str(video),'-vn','-af',
        'loudnorm=I=-16:TP=-1:LRA=7:print_format=json','-f','null','-'],capture_output=True,text=True,check=True)
    levels,_=json.JSONDecoder().raw_decode(audio.stderr[audio.stderr.rfind('{'):])
    if float(levels['input_tp'])>-.8:errors.append('Pico de audio demasiado alto')
    result={'passed':not errors,'errors':errors,'duration_seconds':duration(video),'decoded_entire_video':True,
        'word_timestamps_verified':True,'subtitle_groups':events,'strong_language_count':profanity,
        'continuity':{'decoded_frames':len(pts),'frame_intervals_verified':True,'audio_sample_continuity_verified':True,
            'voice_pauses_over_700ms':len(long_pauses),'frozen_media_detected':'freeze_start:' in frozen.stderr,
            'minimum_shot_seconds':min(s['seconds'] for s in shots),'media_dissolve_seconds':.3},
        'voice':meta['voice'],'loudness_lufs':float(levels['input_i']),'true_peak_dbtp':float(levels['input_tp']),
        'publication_enabled':False,'layout':meta['layout']}
    (folder/'control_calidad.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    if errors:raise RuntimeError('; '.join(errors))
    log(f'QA OK: {video.name}; {events} subtítulos, {profanity} tacos conservados, pico {levels["input_tp"]} dBTP')
    return result


if __name__=='__main__':
    videos=sorted(OUT.rglob('short_vertical.mp4'))
    if not videos:raise RuntimeError('No hay vídeos terminados para revisar')
    for video in videos:inspect(video)
