"""Planos sostenidos y fundidos de la ventana de medios, sin mover los rótulos."""
from collections import Counter
from itertools import combinations
import hashlib
from PIL import Image, ImageOps, ImageFilter
from .pipeline import duration,run
from .purple_layout import SIZE

FPS=30
FADE_FRAMES=9
MIN_SHOT_FRAMES=90
MAX_PHOTO_BOUNDARY_SHIFT=27  # Hasta 0.9 s de ajuste visual; audio intacto.


def visual_identity(visual):
    # El mismo archivo de vídeo puede contener varios planos completamente distintos.
    return (visual['game'],visual.get('image_url') or visual['index'],
        visual.get('kind','image'),visual.get('start') if visual.get('kind')=='video' else None,
        tuple(visual.get('source_crop',[])))


def plan_shots(topic,audios):
    if topic.get('editorial_version',0)>=3:return plan_unique_shots(topic,audios)
    shots=[];elapsed=0;frames=0;last=None;usage=Counter()
    for i,(beat,wav) in enumerate(zip(topic['beats'],audios)):
        elapsed+=duration(wav);end=round(elapsed*FPS);total=end-frames
        # Un clip inferior a dos segundos se descarta si el bloque dispone de fotos.
        choices=[v for v in beat['visuals'] if v.get('max_seconds',60)>=2]
        if not choices:raise ValueError('No hay medios suficientemente largos para un montaje fluido')
        unique=[];seen=set()
        for visual in choices:
            key=visual_identity(visual)
            if key not in seen:unique.append(visual);seen.add(key)
        count=min(len(unique),max(1,total//MIN_SHOT_FRAMES),max(1,round(total/(4.5*FPS))))
        # Solo candidatos relacionados aprobados para ESTE bloque: sin relleno genérico.
        unique.sort(key=lambda v:(visual_identity(v)==last,usage[visual_identity(v)]))
        for j in range(count):
            choice=unique[j];n=total*(j+1)//count-total*j//count
            if choice.get('kind')=='video' and choice.get('max_seconds',3.6)*FPS<n+FADE_FRAMES:
                photos=[v for v in unique if v.get('kind','image')=='image']
                if not photos:raise ValueError('El vídeo no cubre la duración del plano y su fundido')
                choice=photos[j%len(photos)]
            key=visual_identity(choice);usage[key]+=1
            if shots and key==last:
                shots[-1]['frames']+=n
            else:shots.append({'beat':i,'visual':choice,'frames':n})
            last=key
        frames=end
    if any(s['frames']<MIN_SHOT_FRAMES for s in shots):raise ValueError('Plano demasiado breve')
    return shots


def resource_identity(visual):
    # Otro recorte de una fotografía no es otro recurso.
    return (visual['game'],visual.get('image_url') or visual['index'],visual.get('kind','image'))


def stabilize_photo_boundaries(shots):
    """Sostener fotos breves desplazando ligeramente un corte entre fotos contiguas."""
    original=[s['frames'] for s in shots]
    for i,shot in enumerate(shots):
        missing=MIN_SHOT_FRAMES-shot['frames']
        if missing<=0:continue
        if missing>MAX_PHOTO_BOUNDARY_SHIFT or shot['visual'].get('kind','image')!='image':
            raise ValueError('Bloque demasiado breve para un plano sostenido')
        for j in (i+1,i-1):
            if not 0<=j<len(shots):continue
            donor=shots[j]
            if (donor['visual'].get('kind','image')=='image' and
                    donor['visual']['game']==shot['visual']['game'] and
                    donor['frames']-missing>=MIN_SHOT_FRAMES):
                donor['frames']-=missing;shot['frames']+=missing;break
        else:raise ValueError('Faltan fotos contiguas con duración suficiente')
    # Impedir que varios ajustes acumulen una desviación grande de la narración.
    offset=0
    for shot,before in zip(shots,original):
        offset+=shot['frames']-before
        if abs(offset)>MAX_PHOTO_BOUNDARY_SHIFT:
            raise ValueError('El corte se aleja demasiado del bloque narrado')
    return shots


def plan_unique_shots(topic,audios):
    shots=[];used=[];elapsed=0.;frames=0
    def available(v):
        for old in used:
            if resource_identity(v)!=resource_identity(old):continue
            if v.get('kind','image')=='image':return False
            if max(v['start'],old['start'])<min(v['start']+v['max_seconds'],old['start']+old['max_seconds']):return False
        return True
    for i,(beat,wav) in enumerate(zip(topic['beats'],audios)):
        elapsed+=duration(wav);end=round(elapsed*FPS);total=end-frames
        candidates=[];seen=set()
        for v in beat['visuals']:
            key=visual_identity(v)
            if key not in seen and available(v):candidates.append(v);seen.add(key)
        if not candidates:
            # Continuar el mismo plano contiguo es distinto de volver a mostrarlo después.
            if shots and shots[-1]['visual'].get('kind','image')=='image' and any(
                    resource_identity(v)==resource_identity(shots[-1]['visual']) for v in beat['visuals']):
                shots[-1]['frames']+=total;frames=end;continue
            raise ValueError('Faltan medios relacionados sin repetir para este bloque')
        if total<MIN_SHOT_FRAMES:
            photos=[v for v in candidates if v.get('kind','image')=='image']
            if not photos:raise ValueError('Bloque demasiado breve para un vídeo sin ralentizar')
            choice=photos[0]
            shots.append({'beat':i,'visual':choice,'frames':total});used.append(choice)
            frames=end;continue
        max_count=min(len(candidates),total//MIN_SHOT_FRAMES)
        desired=min(max_count,max(1,round(total/(4.5*FPS))))
        selected=None
        for count in list(range(desired,max_count+1))+list(range(desired-1,0,-1)):
            if count<1:continue
            for group in combinations(candidates,count):
                caps=[int(v['max_seconds']*FPS)-FADE_FRAMES if v.get('kind')=='video' else total for v in group]
                if min(caps)<MIN_SHOT_FRAMES or sum(caps)<total:continue
                # Evitar dos rangos solapados también dentro del mismo bloque.
                if any(resource_identity(a)==resource_identity(b) and (a.get('kind','image')=='image' or
                    max(a['start'],b['start'])<min(a['start']+a['max_seconds'],b['start']+b['max_seconds']))
                    for a,b in combinations(group,2)):continue
                selected=(group,caps);break
            if selected:break
        if not selected:raise ValueError('Los medios únicos no cubren la duración sin bucles ni planos fugaces')
        group,caps=selected;counts=[MIN_SHOT_FRAMES]*len(group);remaining=total-sum(counts)
        while remaining:
            free=[j for j in range(len(group)) if counts[j]<caps[j]]
            for j in free:
                add=min(caps[j]-counts[j],max(1,remaining//len(free)),remaining)
                counts[j]+=add;remaining-=add
                if not remaining:break
        for visual,n in zip(group,counts):
            shots.append({'beat':i,'visual':visual,'frames':n});used.append(visual)
        frames=end
    if len(shots)<3:raise ValueError('Se necesitan tres planos distintos sin repetir')
    return stabilize_photo_boundaries(shots)


def prepare_photo(source,target,choice):
    with Image.open(source) as image:
        image=image.convert('RGB')
        if choice.get('source_crop'):
            x,y,w,h=choice['source_crop'];image=image.crop((x,y,x+w,y+h))
        if choice.get('fit','cover')=='contain':
            # Conservar la foto completa; el fondo desenfocado llena el mismo cuadrado.
            background=ImageOps.fit(image,(2160,2160)).filter(ImageFilter.GaussianBlur(55))
            foreground=ImageOps.contain(image,(2160,2160),Image.Resampling.LANCZOS)
            background.paste(foreground,((2160-foreground.width)//2,(2160-foreground.height)//2))
            image=background
        else:
            side=min(image.size);x=round((image.width-side)*choice.get('focus',.5))
            y=round((image.height-side)*choice.get('focus_y',.5))
            image=image.crop((x,y,x+side,y+side)).resize((2160,2160),Image.Resampling.LANCZOS)
        image.save(target)


def render_media(shots,visuals,work,preset):
    clips=[];used=[];fingerprints={};total_frames=sum(s['frames'] for s in shots)
    for i,shot in enumerate(shots):
        choice=shot['visual'];source,credit=visuals[(choice['game'],choice['index'])]
        is_video=choice.get('kind')=='video';n=shot['frames']+(FADE_FRAMES if i<len(shots)-1 else 0)
        command=['ffmpeg','-hide_banner','-loglevel','error','-y','-filter_threads','1']
        if is_video:
            if choice['start']+n/FPS>duration(source):raise ValueError('Plano más largo que su fuente')
            command+=['-ss',str(choice['start']),'-i',str(source)]
            if choice.get('fit','cover')=='contain':
                vf=(f'fps={FPS},split=2[bg][fg];[bg]scale={SIZE}:{SIZE}:force_original_aspect_ratio=increase,'
                    f'crop={SIZE}:{SIZE},boxblur=25:2[blur];[fg]scale={SIZE}:{SIZE}:force_original_aspect_ratio=decrease[sharp];'
                    '[blur][sharp]overlay=(W-w)/2:(H-h)/2,setsar=1')
            else:
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
        if source not in fingerprints:
            with source.open('rb') as stream:fingerprints[source]=hashlib.file_digest(stream,'sha256').hexdigest()
        clips.append(target);used.append({**credit,'beat':shot['beat'],'seconds':shot['frames']/FPS,
            'source_sha256':fingerprints[source],
            'rendered_seconds':n/FPS,'focus':choice.get('focus',.5),'kind':'video' if is_video else 'image',
            'source_start':choice.get('start') if is_video else None,'source_audio_used':False,
            'source_crop':choice.get('source_crop'),'focus_y':choice.get('focus_y',.5),
            'fit':choice.get('fit','cover'),'subject':choice.get('subject'),
            'relevance':choice.get('relevance'),
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
