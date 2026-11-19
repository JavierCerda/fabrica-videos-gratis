"""Shorts visuales sobre curiosidades de GTA: narración, imágenes y música propias en la mezcla."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path

from PIL import Image
from .pipeline import ROOT, OUT, duration, log, run
from .shorts import download_trailer, POLICY, YOUTUBE_POLICY
from .purple_layout import SIZE, X, Y, frame_background, yellow_captions
from .studio_audio import compose_music
from .neural_voice import narrate
from .gta_sources import image_for, verify_topic, discover_ideas, clip_for, OFFICIAL_CLIPS

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
    if visual.get('fit','cover') not in ('cover','contain'):raise ValueError('Encuadre no admitido')
    if not 0<=visual.get('focus',.5)<=1:raise ValueError('Encuadre fuera de la imagen')
    if not 0<=visual.get('focus_y',.5)<=1:raise ValueError('Encuadre vertical fuera de la imagen')
    if 'max_seconds' in visual and not 0<visual['max_seconds']<=12:raise ValueError('Límite de plano inválido')
    crop=visual.get('source_crop')
    if crop is not None and (len(crop)!=4 or not all(isinstance(n,int) for n in crop) or min(crop)<0 or min(crop[2:])<2):
        raise ValueError('Recorte de origen inválido')
    if visual.get('kind','image') not in ('image','video'):raise ValueError('Tipo de recurso no admitido')
    if visual.get('kind')=='video':
        if visual['game']!='gta6' or visual.get('index') not in (-1,*OFFICIAL_CLIPS):raise ValueError('Vídeo fuera del catálogo revisado')
        if not 0<=visual.get('start',-1)<=70:raise ValueError('Inicio del plano fuera del catálogo revisado')


def allocate_frames(total,choices):
    """Respetar los clips cortos sin repetirlos; las fotos completan el bloque de voz."""
    capped={i:round(v['max_seconds']*FPS) for i,v in enumerate(choices) if 'max_seconds' in v}
    free=[i for i in range(len(choices)) if i not in capped]
    remaining=total-sum(capped.values())
    if remaining<0 or not free:raise ValueError('El plan debe reservar una foto para completar la duración')
    result=[capped.get(i,0) for i in range(len(choices))]
    for j,i in enumerate(free):result[i]=remaining*(j+1)//len(free)-remaining*j//len(free)
    if min(result)<1:raise ValueError('Duración insuficiente para este plan de planos')
    return result


def render(topic,audios,visuals,directory,preset='veryfast',burn_captions=True):
    from .smooth_media import plan_shots,render_media
    work=directory/'render';work.mkdir(exist_ok=True)
    from .gta_sources import game_label
    base=frame_background(work/'base_lila.png',topic.get('display_title',topic['hook']),
        game_label(topic['allowed_games'][0]),topic.get('news_date_label'))
    shots=plan_shots(topic,audios)
    media,used=render_media(shots,visuals,work,preset)
    log(f'Montaje continuo: {len(shots)} planos sostenidos, zoom suave y fundidos de 0.3 s')
    wavlist=work/'voices.txt';wavlist.write_text(''.join(f"file '{p.resolve()}'\n" for p in audios))
    full=directory/'narracion.wav'
    run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(wavlist),'-ar','48000','-ac','1',str(full)])
    seconds=duration(full);music=directory/'musica_original.wav'
    seed=int(hashlib.sha256(topic['id'].encode()).hexdigest()[:8],16)
    music_info=compose_music(music,seconds,seed)
    music_info['mix_gain']=1.1
    ass=yellow_captions(topic,audios,directory)
    caption_path=str(ass.resolve()).replace('\\','\\\\').replace(':','\\:').replace("'","\\'")
    video_filter=f'[0:v]fps={FPS},setpts=PTS-STARTPTS[media];[3:v][media]overlay={X}:{Y}:shortest=1'
    if burn_captions:video_filter+=f",ass='{caption_path}'"
    video_filter+='[video];'
    audio_filter=(
        '[1:a]highpass=f=70,lowpass=f=10500,equalizer=f=150:t=q:w=0.7:g=1.3,'
        'acompressor=threshold=0.18:ratio=2:attack=15:release=140,loudnorm=I=-16:TP=-2:LRA=7,aresample=48000,asplit=2[voice][side];'
        '[2:a]volume=1.1[rawmusic];[rawmusic][side]sidechaincompress=threshold=0.06:ratio=4:attack=30:release=500[bed];'
        '[voice][bed]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.84:level=0[audio]')
    output=directory/'short_vertical.mp4'
    run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(media),'-i',str(full),'-i',str(music),'-loop','1','-framerate',str(FPS),'-i',str(base),
         '-filter_complex',video_filter+audio_filter,'-map','[video]','-map','[audio]',
         '-t',f'{seconds:.6f}','-c:v','libx264','-preset',preset,'-crf','19','-threads','2','-c:a','aac','-b:a','160k','-ar','48000',
         '-r',str(FPS),'-fps_mode','cfr','-pix_fmt','yuv420p','-movflags','+faststart',str(output)],timeout=600)
    image_cover(output,directory/'portada_short.jpg')
    write_json(directory/'creditos_visuales.json',used)
    return output, music_info, used


def produce(topic,root,burn_captions=True):
    if topic.get('editorial_version',0)>=2:
        from .editorial_queue import validate_editorial_style
        validate_editorial_style(topic)
    verified=verify_topic(topic)
    directory=root/topic['id'];directory.mkdir(parents=True,exist_ok=True);write_json(directory/'guion.json',topic)
    from .smooth_media import plan_shots
    audios,voice=narrate(topic,directory)
    visuals={}
    for shot in plan_shots(topic,audios):
        visual=shot['visual'];validate_visual(topic,visual);key=(visual['game'],visual['index'])
        if key not in visuals:
            if visual.get('kind')=='video':
                source,credit=download_trailer(directory) if key[1]==-1 else clip_for(key[1])
                visuals[key]=(source,{**credit,'game':'gta6','type':'official_trailer' if key[1]==-1 else 'official_character_clip'})
            else:
                if visual.get('image_url'):
                    from .gta_sources import editorial_image
                    visuals[key]=editorial_image(visual)
                else:visuals[key]=image_for(*key)
    seconds=sum(duration(p) for p in audios)
    minimum=12 if topic.get('editorial_version',0)>=3 else 25
    if not minimum<=seconds<=59:raise ValueError(f'Duración fuera del objetivo Short: {seconds:.1f}s')
    output,music,used=render(topic,audios,visuals,directory,burn_captions=burn_captions)
    meta={'title':topic['title'],'description':topic['summary']+'\n\nComentario original con voz sintética. Vídeos y capturas oficiales de Rockstar. Música instrumental original del proyecto, sin samples ajenos.\nFuentes:\n'+'\n'.join(topic['sources']),
          'duration_seconds':duration(output),'width':WIDTH,'height':HEIGHT,'fps':FPS,'voice':voice,'music':music,
          'format':topic.get('format','documental'),'editorial':topic.get('editorial',{}),
          'continuity':{'constant_frame_rate':True,'media_only_dissolves':True,'transition_seconds':.3,'minimum_shot_seconds':3,'continuous_voice_take':True},
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
    approved=[t for t in topics if t.get('editorial_status')=='approved_fact' and
              t.get('format','documental')==os.getenv('SHORT_FORMAT','comedia_es')]
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
