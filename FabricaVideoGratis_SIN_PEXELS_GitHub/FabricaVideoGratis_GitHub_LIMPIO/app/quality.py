"""Control de los MP4 finales: decodificación, voz, subtítulos y consistencia del formato."""
import json
import re
import subprocess
from pathlib import Path

from .pipeline import OUT, duration, log
from .neural_voice import spoken_tokens

SWEARS={'joder','coño','cojones','hostia','mierda','puto','puta','putos','putas','cabrón','cabrones','cago'}


def inspect(video):
    folder=video.parent;meta=json.loads((folder/'metadata.json').read_text())
    topic=json.loads((folder/'guion.json').read_text());errors=[]
    streams=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(video)]))['streams']
    v=next(s for s in streams if s['codec_type']=='video');a=next(s for s in streams if s['codec_type']=='audio')
    if (v['width'],v['height'],v['r_frame_rate'])!=(1080,1920,'30/1'):errors.append('Formato de vídeo inesperado')
    if (a['channels'],a['sample_rate'])!=(2,'48000'):errors.append('Formato de audio inesperado')
    if not 25<=duration(video)<=59:errors.append('Duración fuera del objetivo')
    subprocess.run(['ffmpeg','-hide_banner','-v','error','-i',str(video),'-f','null','-'],check=True)
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
        if text.count(r'\N')>1:errors.append('Subtítulo con más de dos líneas')
        previous_end=end;events+=1
    if not events:errors.append('Faltan subtítulos')
    if not meta['layout']['persistent_title'] or meta['layout']['media_box']!=[48,414,984,984]:errors.append('Plantilla inconsistente')
    if meta.get('publication_enabled'):errors.append('Publicación activada')
    profanity=sum(w in SWEARS for b in topic['beats'] for w in spoken_tokens(b['narration']))
    if topic.get('format')=='comedia_es' and profanity<8:errors.append('El guion no cumple el tono adulto solicitado')
    audio=subprocess.run(['ffmpeg','-hide_banner','-i',str(video),'-vn','-af',
        'loudnorm=I=-16:TP=-1:LRA=7:print_format=json','-f','null','-'],capture_output=True,text=True,check=True)
    levels,_=json.JSONDecoder().raw_decode(audio.stderr[audio.stderr.rfind('{'):])
    if float(levels['input_tp'])>-.8:errors.append('Pico de audio demasiado alto')
    result={'passed':not errors,'errors':errors,'duration_seconds':duration(video),'decoded_entire_video':True,
        'word_timestamps_verified':True,'subtitle_groups':events,'strong_language_count':profanity,
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
