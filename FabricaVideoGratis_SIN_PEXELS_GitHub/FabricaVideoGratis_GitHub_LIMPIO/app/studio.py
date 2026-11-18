"""Shorts visuales sobre curiosidades de GTA: narración, imágenes y música propias en la mezcla."""
import argparse
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path

from PIL import Image
from .pipeline import ROOT, OUT, duration, log, run
from .shorts import download_trailer, POLICY, YOUTUBE_POLICY
from .purple_layout import SIZE, X, Y, frame_background, yellow_captions
from .studio_audio import compose_music
from .neural_voice import narrate
from .gta_sources import image_for, verify_topic, discover_ideas

WIDTH,HEIGHT,FPS=1080,1920,30


def write_json(path, obj):
    Path(path).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')


def image_cover(clip,path):
    frame=Path(path).parent/'render'/'cover_base.jpg'
    run(['ffmpeg','-hide_banner','-loglevel','error','-y','-ss','0.2','-i',str(clip),'-frames:v','1',str(frame)])
    with Image.open(frame) as im:
        im.convert('RGB').save(path,quality=94)


def validate_visual(topic, visual):
    if visual['game'] not in topic['allowed_games']:raise ValueError('Se rechaza material de un GTA distinto al tema')
    if not 0<=visual.get('focus',.5)<=1:raise ValueError('Encuadre fuera de la imagen')
    if not 0<=visual.get('focus_y',.5)<=1:raise ValueError('Encuadre vertical fuera de la imagen')
    crop=visual.get('source_crop')
    if crop is not None and (len(crop)!=4 or not all(isinstance(n,int) for n in crop) or min(crop)<0 or min(crop[2:])<2):
        raise ValueError('Recorte de origen inválido')
    if visual.get('kind','image') not in ('image','video'):raise ValueError('Tipo de recurso no admitido')
    if visual.get('kind')=='video':
        if visual['game']!='gta6' or visual.get('index')!=-1:raise ValueError('Vídeo fuera del catálogo revisado')
        if not 0<=visual.get('start',-1)<=70:raise ValueError('Inicio del plano fuera del catálogo revisado')


def render(topic,audios,visuals,directory,preset='veryfast',burn_captions=True):
    work=directory/'render';work.mkdir(exist_ok=True);clips=[];used=[];elapsed=0;output_frames=0
    base=frame_background(work/'base_lila.png',topic.get('display_title',topic['hook']))
    for i,(beat,wav) in enumerate(zip(topic['beats'],audios)):
        seconds=duration(wav);count=max(len(beat['visuals']),math.ceil(seconds/3.6))
        end_frame=round((elapsed+seconds)*FPS);beat_frames=end_frame-output_frames
        for j in range(count):
            choice=beat['visuals'][j%len(beat['visuals'])];validate_visual(topic,choice)
            key=(choice['game'],choice['index']);source,credit=visuals[key];focus=choice.get('focus',.5)
            is_video=choice.get('kind')=='video'
            frames=beat_frames*(j+1)//count-beat_frames*j//count
            if frames<1:raise ValueError('Duración insuficiente para las imágenes elegidas')
            shot_seconds=frames/FPS;target=work/f'shot_{i}_{j}.mp4'
            command=['ffmpeg','-hide_banner','-loglevel','error','-y','-filter_complex_threads','1']
            if is_video:
                if choice['start']+shot_seconds>duration(source):raise ValueError('Plano más largo que su fuente')
                command+=['-ss',str(choice['start']),'-i',str(source)]
            else:
                command+=['-loop','1','-framerate',str(FPS),'-i',str(source)]
            # Un único ajuste para TODAS las fuentes: mismo cuadrado, sin estirar ni fondos borrosos.
            crop=choice.get('source_crop');pre=''
            if crop:
                cx,cy,cw,ch=crop
                pre=f'crop={cw}:{ch}:{cx}:{cy},'
            fy=choice.get('focus_y',.5)
            media=(f'[0:v]{pre}fps={FPS},scale={SIZE}:{SIZE}:force_original_aspect_ratio=increase,'
                   f'crop={SIZE}:{SIZE}:(iw-ow)*{focus:.4f}:(ih-oh)*{fy:.4f},setsar=1,format=yuv420p[media];')
            command+=['-loop','1','-framerate',str(FPS),'-i',str(base),'-filter_complex',
                      media+f'[1:v][media]overlay={X}:{Y}:shortest=1,format=yuv420p[v]','-map','[v]']
            run(command+['-frames:v',str(frames),'-an','-c:v','libx264','-preset',preset,'-crf','19','-threads','2',str(target)],timeout=180)
            clips.append(target);used.append({**credit,'beat':i,'seconds':shot_seconds,'focus':focus,'kind':'video' if is_video else 'image',
                'source_start':choice.get('start') if is_video else None,'source_audio_used':False,
                'source_crop':crop,'focus_y':fy,'layout':'flat_lilac_uniform_square'})
        elapsed+=seconds;output_frames=end_frame
        log(f'Montaje lila {i+1}/{len(audios)}; vídeos/fotos en cuadrado')
    listing=work/'clips.txt';listing.write_text(''.join(f"file '{p.resolve()}'\n" for p in clips))
    wavlist=work/'voices.txt';wavlist.write_text(''.join(f"file '{p.resolve()}'\n" for p in audios))
    full=directory/'narracion.wav'
    run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(wavlist),'-ar','48000','-ac','1',str(full)])
    seconds=duration(full);music=directory/'musica_original.wav'
    seed=int(hashlib.sha256(topic['id'].encode()).hexdigest()[:8],16)
    music_info=compose_music(music,seconds,seed)
    image_cover(clips[0],directory/'portada_short.jpg')
    ass=yellow_captions(topic,audios,directory)
    caption_path=str(ass.resolve()).replace('\\','\\\\').replace(':','\\:').replace("'","\\'")
    video_filter='[0:v]null'
    if burn_captions:video_filter+=f",ass='{caption_path}'"
    video_filter+='[video];'
    audio_filter=(
        '[1:a]highpass=f=70,lowpass=f=10500,equalizer=f=150:t=q:w=0.7:g=1.3,'
        'acompressor=threshold=0.18:ratio=2:attack=15:release=140,loudnorm=I=-16:TP=-2:LRA=7,aresample=48000,asplit=2[voice][side];'
        '[2:a]volume=1.8[rawmusic];[rawmusic][side]sidechaincompress=threshold=0.06:ratio=4:attack=30:release=500[bed];'
        '[voice][bed]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.84:level=0[audio]')
    output=directory/'short_vertical.mp4'
    run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(listing),'-i',str(full),'-i',str(music),
         '-filter_complex',video_filter+audio_filter,'-map','[video]','-map','[audio]',
         '-t',f'{seconds:.6f}','-c:v','libx264','-preset',preset,'-crf','19','-threads','2','-c:a','aac','-b:a','160k','-ar','48000',
         '-movflags','+faststart',str(output)],timeout=600)
    write_json(directory/'creditos_visuales.json',used)
    return output, music_info, used


def produce(topic,root,burn_captions=True):
    verified=verify_topic(topic)
    directory=root/topic['id'];directory.mkdir(parents=True,exist_ok=True);write_json(directory/'guion.json',topic)
    visuals={}
    for beat in topic['beats']:
        for visual in beat['visuals']:
            validate_visual(topic,visual);key=(visual['game'],visual['index'])
            if key not in visuals:
                if visual.get('kind')=='video':
                    source,credit=download_trailer(directory)
                    visuals[key]=(source,{**credit,'game':'gta6','type':'official_trailer'})
                else:visuals[key]=image_for(*key)
    audios,voice=narrate(topic,directory)
    seconds=sum(duration(p) for p in audios)
    if not 25<=seconds<=59:raise ValueError(f'Duración fuera del objetivo Short: {seconds:.1f}s')
    output,music,used=render(topic,audios,visuals,directory,burn_captions=burn_captions)
    meta={'title':topic['title'],'description':topic['summary']+'\n\nComentario original con voz sintética. Imágenes oficiales de Rockstar, con movimiento añadido. Música instrumental original del proyecto, sin samples ajenos.\nFuentes:\n'+'\n'.join(topic['sources']),
          'duration_seconds':duration(output),'width':WIDTH,'height':HEIGHT,'fps':FPS,'voice':voice,'music':music,
          'layout':{'template':'flat_lilac_uniform_square','media_box':[X,Y,SIZE,SIZE],'background':'#8B65B5','persistent_title':True},
          'text_overlay':{'title':topic.get('display_title',topic['hook']),'burned_captions':burn_captions,'caption_color':'#FFE600',
                          'caption_alignment':'voice_word_boundaries','persistent_labels':False},'sources':verified,
          'publication_enabled':False,'rights':{'status':'review_required','copyright_clearance':False,'monetization_clearance':False,
             'visuals':'capturas oficiales con copyright, no material libre','creator_footage_used':False,
             'music':'composición y síntesis originales, sin samples de terceros','rockstar_policy':POLICY,'youtube_policy':YOUTUBE_POLICY,
             'shot_duration_note':'La duración se elige por ritmo; cinco segundos no constituyen una exención de copyright.'}}
    write_json(directory/'metadata.json',meta)
    log(f'SHORT STUDIO TERMINADO: {output} · {duration(output):.2f}s · voz neural + música · NO PUBLICADO')
    return output


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--topic-id',default=os.getenv('SHORT_TOPIC') or 'auto');args=parser.parse_args()
    if os.getenv('YOUTUBE_UPLOAD','false').lower()!='false':raise RuntimeError('Publicación desactivada en este flujo')
    topics=json.loads((ROOT/'topics'/'curiosities.json').read_text())
    approved=[t for t in topics if t.get('editorial_status')=='approved_fact']
    stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d_%H%M%S');root=OUT/(stamp+'_gta_studio');root.mkdir(parents=True,exist_ok=True)
    discover_ideas(topics,root/'ideas_investigadas.json')
    if args.topic_id=='muestra':chosen=approved[:2]
    elif args.topic_id=='auto':
        index=max(0,(dt.date.today()-dt.date(2026,11,18)).days//7)
        if index>=len(approved):raise RuntimeError('Catálogo aprobado agotado; revisar las ideas encontradas antes de generar más')
        chosen=[approved[index]]
    else:chosen=[t for t in approved if t['id']==args.topic_id]
    if not chosen:raise ValueError('Tema no aprobado')
    for topic in chosen:produce(topic,root,burn_captions=(os.getenv('SHORT_CAPTIONS') or 'true').lower()=='true')


if __name__=='__main__':main()
