"""Planos sostenidos y fundidos de la ventana de medios, sin mover los rótulos."""
from PIL import Image
from .pipeline import duration,run
from .purple_layout import SIZE

FPS=30
FADE_FRAMES=9
MIN_SHOT_FRAMES=90


def plan_shots(topic,audios):
    shots=[];elapsed=0;frames=0;last=None
    for i,(beat,wav) in enumerate(zip(topic['beats'],audios)):
        elapsed+=duration(wav);end=round(elapsed*FPS);total=end-frames
        # Un clip inferior a dos segundos se descarta si el bloque dispone de fotos.
        choices=[v for v in beat['visuals'] if v.get('max_seconds',60)>=2]
        if not choices:raise ValueError('No hay medios suficientemente largos para un montaje fluido')
        unique=[];seen=set()
        for visual in choices:
            key=(visual['game'],visual['index'])
            if key not in seen:unique.append(visual);seen.add(key)
        count=min(len(unique),max(1,total//MIN_SHOT_FRAMES),max(1,round(total/(4.5*FPS))))
        if last and len(unique)>1 and (unique[0]['game'],unique[0]['index'])==last:
            unique=unique[1:]+unique[:1]
        for j in range(count):
            choice=unique[j];n=total*(j+1)//count-total*j//count
            if choice.get('kind')=='video' and choice.get('max_seconds',3.6)*FPS<n+FADE_FRAMES:
                photos=[v for v in unique if v.get('kind','image')=='image']
                if not photos:raise ValueError('El vídeo no cubre la duración del plano y su fundido')
                choice=photos[j%len(photos)]
            key=(choice['game'],choice['index'])
            if shots and key==last:
                shots[-1]['frames']+=n
            else:shots.append({'beat':i,'visual':choice,'frames':n})
            last=key
        frames=end
    if any(s['frames']<MIN_SHOT_FRAMES for s in shots):raise ValueError('Plano demasiado breve')
    return shots


def prepare_photo(source,target,choice):
    with Image.open(source) as image:
        image=image.convert('RGB')
        if choice.get('source_crop'):
            x,y,w,h=choice['source_crop'];image=image.crop((x,y,x+w,y+h))
        side=min(image.size);x=round((image.width-side)*choice.get('focus',.5))
        y=round((image.height-side)*choice.get('focus_y',.5))
        image=image.crop((x,y,x+side,y+side)).resize((2160,2160),Image.Resampling.LANCZOS)
        image.save(target)


def render_media(shots,visuals,work,preset):
    clips=[];used=[];total_frames=sum(s['frames'] for s in shots)
    for i,shot in enumerate(shots):
        choice=shot['visual'];source,credit=visuals[(choice['game'],choice['index'])]
        is_video=choice.get('kind')=='video';n=shot['frames']+(FADE_FRAMES if i<len(shots)-1 else 0)
        command=['ffmpeg','-hide_banner','-loglevel','error','-y','-filter_threads','1']
        if is_video:
            if choice['start']+n/FPS>duration(source):raise ValueError('Plano más largo que su fuente')
            command+=['-ss',str(choice['start']),'-i',str(source)]
            vf=(f'fps={FPS},scale={SIZE}:{SIZE}:force_original_aspect_ratio=increase,'
                f'crop={SIZE}:{SIZE}:(iw-ow)*{choice.get("focus",.5)}:(ih-oh)*{choice.get("focus_y",.5)},setsar=1')
        else:
            photo=work/f'photo_{i:02d}.png';prepare_photo(source,photo,choice)
            command+=['-i',str(photo)]
            # Doble resolución y movimiento calculado por frame para evitar redondeos bruscos.
            vf=(f"zoompan=z='1.01+0.035*on/{max(1,n-1)}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':"
                f'd={n}:s=1968x1968:fps={FPS},scale={SIZE}:{SIZE}:flags=lanczos,setsar=1')
        target=work/f'media_{i:02d}.mp4'
        run(command+['-vf',vf,'-frames:v',str(n),'-an','-c:v','libx264','-preset',preset,
            '-crf','18','-pix_fmt','yuv420p','-threads','2','-video_track_timescale','15360',str(target)],timeout=240)
        clips.append(target);used.append({**credit,'beat':shot['beat'],'seconds':shot['frames']/FPS,
            'rendered_seconds':n/FPS,'focus':choice.get('focus',.5),'kind':'video' if is_video else 'image',
            'source_start':choice.get('start') if is_video else None,'source_audio_used':False,
            'source_crop':choice.get('source_crop'),'focus_y':choice.get('focus_y',.5),
            'motion':'source_video' if is_video else 'gentle_zoom','transition_seconds':FADE_FRAMES/FPS if i else 0,
            'layout':'flat_lilac_uniform_square'})
    command=['ffmpeg','-hide_banner','-loglevel','error','-y','-filter_complex_threads','1']
    for clip in clips:command+=['-i',str(clip)]
    graph=''.join(f'[{i}:v]settb=AVTB,setpts=PTS-STARTPTS,fps={FPS}[v{i}];' for i in range(len(clips)))
    previous='v0';offset=0
    for i in range(1,len(clips)):
        offset+=shots[i-1]['frames'];name=f'blend{i}'
        graph+=f'[{previous}][v{i}]xfade=transition=fade:duration={FADE_FRAMES/FPS}:offset={offset/FPS:.9f}[{name}];'
        previous=name
    target=work/'media_continua.mp4'
    run(command+['-filter_complex',graph.rstrip(';'),'-map',f'[{previous}]','-frames:v',str(total_frames),
        '-an','-c:v','libx264','-preset',preset,'-crf','18','-pix_fmt','yuv420p','-threads','2',str(target)],timeout=600)
    return target,used
