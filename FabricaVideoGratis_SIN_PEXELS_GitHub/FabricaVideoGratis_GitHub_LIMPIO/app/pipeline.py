"""Fábrica de vídeos en la nube: Gemini (guion + TTS), Wikimedia Commons (material real), FFmpeg.
Ni el render ni la publicación se ejecutan si no hay credenciales propias.
"""
from __future__ import annotations
import argparse, base64, datetime as dt, hashlib, json, math, os, random, re, shutil, subprocess, sys, time, wave
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output'
OUT.mkdir(exist_ok=True)
TIMEOUT = 90
UA = 'FabricaVideoGratis/2.0 (public educational video creator; contact: https://github.com/JavierCerda/fabrica-videos-gratis)'


def log(message):
    print(f'[FABRICA] {message}', flush=True)


def run(args, timeout=300):
    p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if p.returncode:
        raise RuntimeError(f'Falló comando {args[0]}: {p.stderr[-1600:]}')
    return p.stdout


def duration(path):
    info = json.loads(run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'json', str(path)]))
    return float(info['format']['duration'])


def fail_if_no_key(name):
    key = os.environ.get(name)
    if not key:
        raise RuntimeError(f'Falta {name}. Configura el secreto en GitHub > Settings > Secrets and variables > Actions.')
    return key


def gemini(prompt, model, audio=False):
    key = fail_if_no_key('GEMINI_API_KEY')
    body = {'contents': [{'parts': [{'text': prompt}]}]}
    if audio:
        body['generationConfig'] = {'responseModalities': ['AUDIO'], 'speechConfig': {'voiceConfig': {'prebuiltVoiceConfig': {'voiceName': os.getenv('GEMINI_VOICE', 'Charon')}}}}
    else:
        body['generationConfig'] = {'responseMimeType': 'application/json', 'temperature': 0.65}
    url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
    for attempt in range(3):
        try:
            r = requests.post(url, headers={'x-goog-api-key': key, 'Content-Type': 'application/json'}, json=body, timeout=TIMEOUT + (60 if audio else 0))
            if r.status_code in (429, 500, 502, 503) and attempt < 2:
                time.sleep(8 * (attempt + 1)); continue
            r.raise_for_status()
            obj = r.json()
            parts = obj['candidates'][0]['content']['parts']
            if audio:
                part = next((p['inlineData'] for p in parts if 'inlineData' in p), None)
                if not part:
                    raise ValueError('Respuesta TTS sin audio.')
                return base64.b64decode(part['data']), part.get('mimeType', 'audio/L16;rate=24000')
            return ''.join(p.get('text', '') for p in parts)
        except (requests.RequestException, KeyError, ValueError) as ex:
            if attempt == 2:
                raise RuntimeError(f'Gemini no respondió correctamente ({model}); comprueba cuota gratuita y modelo: {ex}') from ex
            time.sleep(4 * (attempt+1))
    raise RuntimeError('Respuesta vacía')


def pick_topic():
    topics = json.loads((ROOT / 'topics' / 'topics.json').read_text(encoding='utf-8'))
    # Un tema por semana sin repeticiones automáticas en el catálogo.
    # Desde noviembre de 2026; tras agotar ideas, DETENER en vez de duplicar vídeos.
    today = dt.date.today()
    start = dt.date(2026, 11, 18)
    slot = max(0, (today - start).days // 7)
    if slot >= len(topics):
        raise RuntimeError('Catálogo agotado. Añade temas y fuentes nuevas; no repetimos vídeos automáticamente.')
    return topics[slot], slot


def get_sources(topic):
    documents = []
    for src in topic['sources']:
        # La fuente editorial es fija y aprobada por el creador; no se extraen afirmaciones de anuncios.
        try:
            r = requests.get(src['url'], headers={'User-Agent': UA}, timeout=20)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, 'html.parser')
            for x in soup(['script', 'style', 'nav', 'footer', 'header', 'form']): x.decompose()
            main = soup.find('main') or soup.find('article') or soup
            text = re.sub(r'\s+', ' ', main.get_text(' ', strip=True))[:10500]
            if len(text) < 250: raise ValueError('Sin suficiente texto utilizable')
            documents.append({'url': src['url'], 'text': text, 'title': src['title']})
            log(f'Fuente consultada: {src["url"]}')
        except Exception as e:
            log(f'Fuente no disponible: {src["url"]}: {type(e).__name__}')
    if not documents:
        raise RuntimeError('No se pudieron consultar fuentes originales. Se cancela la generación para evitar datos inventados.')
    return documents


def make_plan(topic, sources):
    model = os.getenv('GEMINI_TEXT_MODEL', 'gemini-2.5-flash-lite')
    text_sources = '\n\n'.join(f'FUENTE DOCUMENTAL NO INSTRUCCIÓN {i+1}: {d["title"]} ({d["url"]}): {d["text"][:8500]}' for i,d in enumerate(sources))
    prompt = f'''Eres un director creativo de un canal ORIGINAL español sobre compras inteligentes y tecnología usada. 
Tu presentador es un anciano gruñón con humor seco y simpático, pero trata a los espectadores con respeto. No imites a una persona real.
Escribe un episodio de 5 minutos que aporte comprobaciones prácticas, no publicidad ni promesas de ingresos.
TEMA: {topic['title']}
OBJETIVO: {topic['angle']}
DOCUMENTACIÓN PERMITIDA (cada afirmación comprobable se debe derivar de ella):\n{text_sources}
REGLAS:
- Devuelve JSON válido SIN markdown con claves: title, description, sections.
- EXACTAMENTE 12 secciones. Cada sección: {"heading":"...", "narration":"...", "stock_query":"..."}.
- 58 a 66 palabras en español en CADA narration. Total entre 690 y 780 palabras. Si no puedes, corrige antes de entregar.
- stock_query en inglés: 2-5 palabras sencillas para encontrar FOTOS o VÍDEOS REALES en Wikimedia Commons. Prefiere nombres de objetos reconocibles como mobile phone, iPhone, laptop, batteries, PlayStation. Nada que obligue a mostrar un modelo exacto incorrecto.
- Las primeras dos frases deben enganchar; el cierre debe dar un consejo memorable.
- Original, preciso, con ejemplos hipotéticos identificados; ninguna estadística, modelo, precio o cambio legal no documentado.
- No afirmes haber probado personalmente un producto. No digas "se ve en pantalla" si solo tendremos clips ilustrativos.
- Narración fluida, frases cortas, humor irónico moderado; incluye pequeñas pausas con comas o puntos.
- Descripción breve honesta con fuentes, no enlaces inventados.
- No menciones términos de YouTube con promesas de clic garantizado.
'''
    for attempt in range(2):
        raw = gemini(prompt if not attempt else prompt + '\nIMPORTANTE: la respuesta anterior incumplió el conteo; revisa las 12 secciones y el número de palabras.', model)
        try:
            plan = json.loads(re.sub(r'^```(?:json)?|```$', '', raw.strip()).strip())
            sections = plan['sections']
            counts = [len(re.findall(r'\b[\wÁÉÍÓÚÜÑáéíóúüñ]+\b',s['narration'])) for s in sections]
            if len(sections) != 12 or not 650 <= sum(counts) <= 820 or any(n < 42 or n > 84 for n in counts):
                raise ValueError(f'Longitud o estructura incorrecta: {counts}')
            if any(not s['stock_query'].strip() or not s['heading'].strip() for s in sections): raise ValueError('Faltan campos')
            plan['source_urls'] = [d['url'] for d in sources]
            plan['topic_id'] = topic['id']
            log(f'Guion: {sum(counts)} palabras en {len(sections)} secciones')
            return plan
        except (ValueError, TypeError, KeyError) as ex:
            log(f'Revisando guion: {ex}')
    raise RuntimeError('El guion generado no cumple el formato mínimo; no se publicará contenido defectuoso.')


def write_wav(raw, mime, path):
    if mime.startswith('audio/wav') or raw[:4] == b'RIFF':
        path.write_bytes(raw); return
    # Gemini TTS 2.5 devuelve generalmente PCM s16 mono a 24 kHz.
    match = re.search(r'rate\s*=\s*(\d+)', mime, re.I)
    sample_rate = int(match.group(1)) if match else 24000
    if not any(x in mime.lower() for x in ('l16', 'pcm', 'audio/raw', 'audio/wave')):
        raise ValueError(f'Formato de audio inesperado: {mime}')
    with wave.open(str(path), 'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(sample_rate); wav.writeframes(raw)


def narration_audio(plan, directory):
    provider = os.getenv('VOICE_PROVIDER', 'gemini')
    if provider not in ('gemini', 'voxcpm'):
        raise RuntimeError('VOICE_PROVIDER debe ser gemini o voxcpm (Colab con GPU temporal).')
    audio_paths=[]
    if provider == 'voxcpm':
        import torch, soundfile as sf
        from voxcpm import VoxCPM
        log('Cargando VoxCPM2: opción para Colab, NO para el runner gratuito de GitHub.')
        model = VoxCPM.from_pretrained('openbmb/VoxCPM2', load_denoiser=False)
        sr = model.tts_model.sample_rate
        voice_desc = os.getenv('VOX_VOICE_DESCRIPTION', '(An elderly man, rough scratchy voice, worn out and hoarse, grumpy but funny, unhurried)')
    for i, s in enumerate(plan['sections']):
        p = directory / f'voz_{i:02d}.wav'
        # La personalidad se controla con la dirección de actuación, sin clonar una identidad ajena.
        prompt = ('Lee en ESPAÑOL DE ESPAÑA de forma expresiva, clara y con pausas naturales. '
                  'Actúa como un narrador mayor, cascarrabias y simpático, con voz grave y un punto áspero. '
                  'No exageres la ronquera ni hagas ruidos o introducciones. Lee únicamente el siguiente texto, palabra por palabra:\n\n'
                  + s['narration'])
        if provider == 'voxcpm':
            torch.manual_seed(1)
            generated = model.generate(text=voice_desc + ' ' + s['narration'], cfg_value=2.0, inference_timesteps=16)
            sf.write(str(p), generated, sr)
        else:
            raw, mime = gemini(prompt, os.getenv('GEMINI_TTS_MODEL', 'gemini-2.5-flash-preview-tts'), audio=True)
            write_wav(raw, mime, p)
        if duration(p) < 4: raise ValueError(f'Audio demasiado corto en sección {i}: {p}')
        audio_paths.append(p)
        log(f'Voz {i+1}/12: {duration(p):.1f} s')
    return audio_paths


def clean_metadata(text):
    return re.sub(r'\s+', ' ', BeautifulSoup(str(text or ''), 'html.parser').get_text(' ', strip=True))[:240]


def commons_search(query):
    """Wikimedia Commons: imágenes auténticas y algunos vídeos, sin API key.

    Solo usamos obras con licencia explícita CC0, dominio público o CC BY.
    La atribución por archivo se incluye en metadata.json y creditos_stock.json.
    """
    endpoint = 'https://commons.wikimedia.org/w/api.php'
    params = {'action':'query', 'format':'json', 'formatversion':'2',
              'generator':'search', 'gsrsearch':query, 'gsrnamespace':'6',
              'gsrlimit':'40', 'prop':'imageinfo',
              'iiprop':'url|extmetadata|size|mime', 'iiurlwidth':'1600'}
    resp = requests.get(endpoint, params=params,
                        headers={'User-Agent':UA, 'Accept':'application/json'}, timeout=35)
    resp.raise_for_status()
    results=[]
    for item in resp.json().get('query',{}).get('pages',[]):
        ii=(item.get('imageinfo') or [{}])[0]
        mime=ii.get('mime','')
        kind=('image' if mime in ('image/jpeg','image/png','image/webp') else
              'video' if mime in ('video/webm','video/ogg','video/mp4') else '')
        if not kind: continue
        meta=ii.get('extmetadata') or {}
        def m(k): return meta.get(k,{}).get('value','')
        lic=clean_metadata(m('LicenseShortName')).strip()
        lc=lic.lower().replace('-',' ').strip()
        # Evitar por defecto el uso de CC BY-SA para no imponer condiciones
        # de copyleft al material derivado por accidente.
        if not (lc.startswith('cc0') or lc.startswith('public domain') or
                lc.startswith('pd ') or lc=='pd' or lc.startswith('cc by ')):
            continue
        width=int(ii.get('width',0) or 0); height=int(ii.get('height',0) or 0)
        if width<800 or height<450: continue
        # Selección de ficheros pequeños para mantener Actions en nivel gratuito.
        if kind=='video' and int(ii.get('size',0))>55_000_000: continue
        origin=ii.get('thumburl') if kind=='image' else ii.get('url')
        if not origin or not origin.startswith('https://'): continue
        page=ii.get('descriptionurl') or ('https://commons.wikimedia.org/wiki/'+item['title'].replace(' ','_'))
        artist=clean_metadata(m('Artist') or m('Credit') or 'Autor no indicado')
        results.append({'id':str(item.get('pageid')), 'url':origin,
                        'page_url':page, 'artist':artist,
                        'license':lic, 'license_url':clean_metadata(m('LicenseUrl')),
                        'title':item['title'], 'kind':kind,
                        'width':width,'height':height, 'size':int(ii.get('size',0))})
    # Preferir escenas apaisadas con buena resolución; no excluir verticales.
    return sorted(results,key=lambda v:(v['kind']!='video',v['width']/max(1,v['height'])<1.2, -v['width']))


def download_commons(clip, folder):
    kind=clip['kind']
    suffix=('.jpg' if kind=='image' else '.webm')
    p=folder/f'{clip["id"]}{suffix}'
    if p.exists(): return p
    url=clip['url']
    host=urlparse(url).hostname or ''
    if not (host=='upload.wikimedia.org' or host.endswith('.upload.wikimedia.org')):
        raise ValueError('Origen no permitido: únicamente upload.wikimedia.org')
    maxbytes=65_000_000 if kind=='video' else 12_000_000
    with requests.get(url,headers={'User-Agent':UA},stream=True,timeout=(15,75)) as resp:
        resp.raise_for_status(); n=0
        with p.open('wb') as dest:
            for chunk in resp.iter_content(1024*256):
                n+=len(chunk)
                if n>maxbytes:
                    dest.close();p.unlink(missing_ok=True)
                    raise ValueError('Archivo multimedia demasiado grande')
                dest.write(chunk)
    return p


def get_stock(plan, directory):
    cache=directory/'stock'; cache.mkdir(exist_ok=True)
    result=[]; credits={};used=set()
    for i,section in enumerate(plan['sections']):
        specific=' '.join(section['stock_query'].split()[:5])
        title=plan.get('title','').lower()
        general=('iPhone' if 'iphone' in title else
                 'PlayStation' if 'ps5' in title else
                 'laptop computer' if 'portátil' in title or 'ordenador' in title else
                 'smartphone')
        search_terms=[specific,general,'mobile phone','electronics','computer hardware']
        selected=[]
        for term in dict.fromkeys(search_terms):
            if len(selected)>=3: break
            try:
                candidates=commons_search(term)
            except Exception as e:
                log(f'Commons no responde a {term}: {str(e)[:120]}')
                continue
            random.Random(i*271+len(term)).shuffle(candidates)
            # Buscar algunos vídeos antes que fotografías cuando hay resultados.
            candidates.sort(key=lambda x: x['kind']!='video')
            for clip in candidates:
                if clip['id'] in used: continue
                try:
                    path=download_commons(clip,cache)
                    if clip['kind']=='video' and duration(path)<5: continue
                    used.add(clip['id']); selected.append(path)
                    credits[clip['id']]={'creator':clip['artist'], 'link':clip['page_url'],
                                         'license':clip['license'], 'license_url':clip['license_url'],
                                         'query':term, 'type':clip['kind']}
                    if len(selected)>=3: break
                except Exception as e:
                    log(f'Recurso Commons omitido: {str(e)[:130]}')
        if len(selected)<2:
            raise RuntimeError(f'Wikimedia Commons: no hay dos medios válidos para la sección {i+1}. No se fabrica un vídeo con relleno falso.')
        result.append(selected)
        log(f'Material real {i+1}/12: {sum(p.suffix==".webm" for p in selected)} vídeos, {sum(p.suffix!=".webm" for p in selected)} fotos')
    (directory/'creditos_stock.json').write_text(json.dumps(credits,ensure_ascii=False,indent=2),encoding='utf-8')
    return result


def format_srt(seconds):
    ms=round(seconds*1000)
    h=ms//3600000;ms%=3600000;m=ms//60000;ms%=60000;s=ms//1000;ms%=1000
    return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'


def create_subtitles(plan, audios, directory):
    start=0;lines=[];idx=1
    for section,audio in zip(plan['sections'],audios):
        words=section['narration'].split()
        chunks=[words[k:k+9] for k in range(0,len(words),9)]
        d=duration(audio)
        ratio=d/len(words)
        offset=0
        for chunk in chunks:
            d2=len(chunk)*ratio
            lines += [str(idx), f'{format_srt(start+offset)} --> {format_srt(start+offset+d2)}', ' '.join(chunk), '']
            offset += d2;idx += 1
        start+=d
    path=directory/'subtitulos.srt'; path.write_text('\n'.join(lines),encoding='utf-8')
    return path


def ff_text(s):
    return re.sub(r'[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9 .,:¡!¿?()\-]', '', s)[:72]


def render_video(plan, audios, stocks, directory, test_mode=False):
    clips_dir=directory/'render';clips_dir.mkdir(exist_ok=True)
    w,h=(640,360) if test_mode else (1920,1080)
    fps=24 if test_mode else 25
    output=directory/'video_final.mp4'
    section_files=[]
    for index,(s, audio, videos) in enumerate(zip(plan['sections'],audios,stocks)):
        section_duration=duration(audio)
        shot_count=max(1,math.ceil(section_duration/(3 if test_mode else 4.4)))
        tempfiles=[]
        for j in range(shot_count):
            sd=min(3 if test_mode else 4.4, section_duration-j*(3 if test_mode else 4.4))
            vid=videos[j%len(videos)]
            p=clips_dir/f's{index:02d}_{j:02d}.mp4'
            vf=f'scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={fps},setsar=1,format=yuv420p'
            if vid.suffix.lower() in ('.jpg','.jpeg','.png','.webp'):
                # Una FOTO AUTÉNTICA con movimiento de cámara suave, no una imagen IA.
                vf=(f'scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},'
                    f'zoompan=z=\'min(zoom+0.0007,1.08)\':d=1:s={w}x{h}:fps={fps},'
                    'setsar=1,format=yuv420p')
                cmd=['ffmpeg','-hide_banner','-loglevel','error','-y','-loop','1',
                     '-framerate',str(fps),'-i',str(vid),'-t',f'{sd:.3f}', '-an','-vf',vf]
            else:
                d=duration(vid)
                offset=min(max(0,d-sd-.25),(j*3.2+index*.5)%max(1,d-sd-.25))
                cmd=['ffmpeg','-hide_banner','-loglevel','error','-y','-ss',f'{offset:.3f}',
                     '-i',str(vid),'-t',f'{sd:.3f}', '-an','-vf',vf]
            run(cmd+['-c:v','libx264','-preset','ultrafast' if test_mode else 'veryfast',
                     '-crf','25' if test_mode else '22','-pix_fmt','yuv420p','-r',str(fps),str(p)],timeout=180)
            tempfiles.append(p)
        shotlist=clips_dir/f'section_{index:02d}.txt'
        shotlist.write_text(''.join("file '"+str(p.resolve()).replace("'","'\\''")+"'\n" for p in tempfiles),encoding='utf-8')
        section_video=clips_dir/f'section_{index:02d}.mp4'
        run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(shotlist),'-c','copy',str(section_video)],timeout=180)
        section_files.append(section_video)
        log(f'Montaje {index+1}/{len(plan["sections"])}: {shot_count} planos reales')
    listfile=clips_dir/'all.txt'
    listfile.write_text(''.join("file '"+str(p.resolve())+"'\n" for p in section_files),encoding='utf-8')
    silent=clips_dir/'silent.mp4'
    run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(listfile),'-c','copy',str(silent)],timeout=240)
    wavlist=clips_dir/'audios.txt'
    wavlist.write_text(''.join("file '"+str(p.resolve())+"'\n" for p in audios),encoding='utf-8')
    long_wav=clips_dir/'full.wav'
    run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(wavlist),'-ac','2','-ar','48000',str(long_wav)], timeout=90)
    srt=create_subtitles(plan,audios,directory)
    # Escapar rutas que usan ffmpeg subtitles filter; en servidor Linux paths sin espacios raros.
    srt_path=str(srt.resolve()).replace('\\','\\\\').replace(':','\\:').replace("'","\\'")
    fontsize=15 if test_mode else 33
    filter_sub=f"subtitles='{srt_path}':force_style='FontName=DejaVu Sans,FontSize={fontsize},Outline=2,Shadow=0,Alignment=2,MarginV={14 if test_mode else 64},PrimaryColour=&H00FFFFFF&,OutlineColour=&H00111111&'"
    run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(silent),'-i',str(long_wav),'-vf',filter_sub,'-af','loudnorm=I=-16:TP=-1.5:LRA=9','-map','0:v:0','-map','1:a:0','-shortest','-c:v','libx264','-preset','ultrafast' if test_mode else 'veryfast','-crf','23' if test_mode else '20','-c:a','aac','-b:a','192k','-movflags','+faststart',str(output)],timeout=900)
    return output



def create_thumbnail(plan, video, directory):
    """Miniatura horizontal original, creada a partir del metraje seleccionado."""
    from PIL import Image, ImageDraw, ImageFont, ImageEnhance
    import textwrap
    frame=directory/'miniatura_base.jpg'
    run(['ffmpeg','-hide_banner','-loglevel','error','-y','-ss','00:00:02',
         '-i',str(video),'-frames:v','1','-vf','scale=1280:720',str(frame)],timeout=80)
    img=Image.open(frame).convert('RGB')
    img=ImageEnhance.Contrast(img).enhance(1.12)
    # Degradado lateral legible sin introducir datos no verificados.
    overlay=Image.new('RGBA',(1280,720),(0,0,0,0)); od=ImageDraw.Draw(overlay)
    for x in range(0,1080,4):
        alpha=int(230*max(0,1-x/1080)**1.6)
        od.rectangle((x,0,x+4,720),fill=(6,13,25,alpha))
    img=Image.alpha_composite(img.convert('RGBA'),overlay)
    dr=ImageDraw.Draw(img)
    font_path='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
    small=ImageFont.truetype(font_path,33); big=ImageFont.truetype(font_path,78)
    dr.rounded_rectangle((65,55,470,108),radius=12,fill=(239,174,47,255))
    dr.text((85,61),'ANTES DE COMPRAR',font=small,fill=(14,20,30,255))
    # Max tres líneas y palabras cortadas de forma segura.
    title=re.sub(r'[:¿?!]+',' ',str(plan.get('title',''))).strip()
    words=title.split(); lines=[]; line=''
    for word in words:
        candidate=(line+' '+word).strip()
        if dr.textbbox((0,0),candidate,font=big)[2] <= 890:
            line=candidate
        else:
            if line: lines.append(line)
            line=word
        if len(lines)>=3: break
    if line and len(lines)<3: lines.append(line)
    if not lines: lines=['COMPRA INTELIGENTE']
    for i,line in enumerate(lines[:3]):
        y=180+i*110
        dr.text((61,y+5),line,font=big,fill=(0,0,0,210),stroke_width=5,stroke_fill=(0,0,0,210))
        dr.text((61,y),line,font=big,fill=(255,255,255,255),stroke_width=2,stroke_fill=(15,25,35,255))
    dr.rectangle((65,650,520,657),fill=(239,174,47,255))
    out=directory/'miniatura_youtube.jpg'
    img.convert('RGB').save(out,quality=91,optimize=True)
    return out

def description(plan, credits):
    unique=list({x['link']: x for x in credits.values() if x.get('link')}.values())
    srcs='\n'.join('- '+url for url in plan['source_urls'])
    stock='\n'.join('- '+x['creator']+' — '+x['license']+' — '+x['link'] for x in unique)
    return (plan.get('description','')+'\n\nFuentes consultadas:\n'+srcs+'\n\n'
            'Imágenes y vídeo ilustrativos: Wikimedia Commons. No representan necesariamente el modelo exacto mencionado.\n'
            'Créditos (autor, licencia, fuente):\n'+stock+'\n\nVídeo narrado con voz sintética. La información puede cambiar.').strip()[:4800]


def save_metadata(plan, directory):
    credits=json.loads((directory/'creditos_stock.json').read_text(encoding='utf-8'))
    meta={'title':plan['title'][:95], 'description':description(plan,credits),'tags':['tecnología','segunda mano','compras inteligentes','consejos'], 'sources':plan['source_urls']}
    (directory/'metadata.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    (directory/'guion.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
    return meta


def maybe_upload(video, meta, thumbnail=None):
    if os.getenv('YOUTUBE_UPLOAD','false').lower() != 'true':
        log('Subida desactivada: MP4 guardado como artefacto de GitHub.')
        return
    needed=('YT_CLIENT_ID','YT_CLIENT_SECRET','YT_REFRESH_TOKEN')
    if not all(os.getenv(k) for k in needed):
        raise RuntimeError('YOUTUBE_UPLOAD=true pero faltan credenciales OAuth. No se publica.')
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    privacy=os.getenv('YOUTUBE_PRIVACY','private').lower()
    if privacy not in ('private','unlisted','public'): raise ValueError('Privacidad inválida')
    creds=Credentials(None,refresh_token=os.environ['YT_REFRESH_TOKEN'],token_uri='https://oauth2.googleapis.com/token', client_id=os.environ['YT_CLIENT_ID'],client_secret=os.environ['YT_CLIENT_SECRET'],scopes=['https://www.googleapis.com/auth/youtube.upload'])
    client=build('youtube','v3',credentials=creds,cache_discovery=False)
    body={'snippet':{'title':meta['title'],'description':meta['description'],'tags':meta['tags'],'categoryId':'28','defaultLanguage':'es'},'status':{'privacyStatus':privacy,'selfDeclaredMadeForKids':False,'containsSyntheticMedia':False}}
    # Vídeos con metraje real y narración sintética: comprobar las obligaciones de divulgación según el caso.
    media=MediaFileUpload(str(video),mimetype='video/mp4',resumable=True,chunksize=8*1024*1024)
    request=client.videos().insert(part='snippet,status',body=body,media_body=media)
    result=None
    while result is None:
        _,result=request.next_chunk()
    log('SUBIDO: https://www.youtube.com/watch?v='+result['id']+' (privacidad '+privacy+')')
    if thumbnail and Path(thumbnail).exists():
        try:
            client.thumbnails().set(videoId=result['id'],media_body=str(thumbnail)).execute()
            log('Miniatura subida a YouTube')
        except Exception as ex:
            log('Miniatura no subida; sigue disponible en el artefacto: '+str(ex)[:160])


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--topic-id',default=None)
    args=parser.parse_args()
    topic, index=pick_topic()
    if args.topic_id:
        all_topics=json.loads((ROOT/'topics'/'topics.json').read_text(encoding='utf-8'))
        matches=[t for t in all_topics if t['id']==args.topic_id]
        if not matches: raise ValueError('No se encuentra el tema solicitado')
        topic=matches[0]
    stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d_%H%M')
    directory=OUT/f'{stamp}_{topic["id"]}'
    directory.mkdir(parents=True,exist_ok=True)
    docs=get_sources(topic)
    plan=make_plan(topic, docs)
    (directory/'guion.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
    audio=narration_audio(plan,directory)
    stock=get_stock(plan,directory)
    video=render_video(plan,audio,stock,directory)
    seconds=duration(video)
    log(f'VÍDEO TERMINADO: {video} · {seconds:.1f}s')
    if not (250 <= seconds <= 390):
        log('AVISO: duración fuera del objetivo de cinco minutos; se deja para revisión.')
        # No se publica de forma automática algo que incumple la duración.
        return
    metadata=save_metadata(plan,directory)
    thumbnail=create_thumbnail(plan,video,directory)
    log(f'Miniatura terminada: {thumbnail}')
    maybe_upload(video,metadata,thumbnail)


if __name__=='__main__':
    try: main()
    except Exception as exc:
        log(f'ERROR: {exc}')
        raise
