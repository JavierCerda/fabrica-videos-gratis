"""Shorts editoriales de GTA VI. Borradores; sin publicar ni eludir Content ID."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import wave
from urllib.parse import urlparse

import requests
from PIL import Image, ImageDraw, ImageFont

from .pipeline import ROOT, OUT, UA, duration, ensure_piper_model, format_srt, log, run

WIDTH, HEIGHT, FPS = 1080, 1920, 30
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
REGULAR = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
MEDIA_PAGE = 'https://www.rockstargames.com/VI/media/videos'
POLICY = 'https://support.rockstargames.com/articles/7bNaeoMFTV0iUDGhStTXvz/policy-on-posting-copyrighted-rockstar-games-material'
YOUTUBE_POLICY = 'https://support.google.com/youtube/answer/9783148'
TRAILER = 'https://media-rockstargames-com.akamaized.net/VI/downloads/videos/GTAVI_Launch_Trailer/GTAVI_Launch_Trailer.mp4'
TRAILER_SHA256 = 'c231835a84ccf72e2fc991f349087744e8487734aef2e206ae018eff69580b49'
PINK = '#fb73b8'
CYAN = '#77eee0'


def font(size, bold=True):
    return ImageFont.truetype(FONT if bold else REGULAR, size)


def wrap(text, size, max_width=880):
    f = font(size)
    lines, line = [], ''
    for word in text.split():
        if f.getlength(word) > max_width:
            raise ValueError('Palabra demasiado larga para el área visible')
        candidate = (line + ' ' + word).strip()
        if f.getlength(candidate) > max_width and line:
            lines.append(line); line = word
        else:
            line = candidate
    if line: lines.append(line)
    return lines


def fit(text, max_size=102, max_lines=3, width=880):
    for size in range(max_size, min(35, max_size-12), -2):
        try: lines = wrap(text, size, width)
        except ValueError: continue
        if len(lines) <= max_lines:
            return size, lines
    raise ValueError('Texto demasiado largo: se rechaza en vez de cortarlo')


def text_block(draw, text, y, max_size=102, max_lines=3, fill='white', width=880):
    size, lines = fit(text, max_size, max_lines, width)
    for i, line in enumerate(lines):
        draw.text((74, y + i * (size + 12)), line, font=font(size), fill=fill,
                  stroke_width=1, stroke_fill=fill)
    return y + len(lines) * (size + 12)


def background():
    # Gráfica original; nunca se sustituye GTA VI por imágenes de móviles o stock genérico.
    img = Image.new('RGB', (WIDTH, HEIGHT))
    d = ImageDraw.Draw(img)
    for y in range(HEIGHT):
        t = y / HEIGHT
        d.line((0, y, WIDTH, y), fill=(int(22 + 19*t), int(16 + 5*t), int(46 + 12*t)))
    for x in range(-500, 1400, 120):
        d.line((x, 0, x+1000, HEIGHT), fill=(45, 29, 68), width=1)
    return img


def make_card(topic, beat, index, path, cover=False):
    img = background(); d = ImageDraw.Draw(img)
    d.rounded_rectangle((74, 112, 493, 167), radius=12, fill=PINK)
    d.text((94, 120), 'MODO LEONIDA', font=font(30), fill='#161027')
    d.text((74, 190), 'GTA VI  /  ANÁLISIS', font=font(25, False), fill=CYAN)
    text_block(d, topic['hook'] if cover else beat['headline'], 245, 98, 2)
    if cover:
        text_block(d, topic['cover_subtitle'], 740, 72, 3, CYAN)
    else:
        d.rounded_rectangle((74, 590, 956, 1170), radius=34, fill='#30233f', outline='#65506c', width=2)
        d.text((112, 630), f'{index+1:02d}', font=font(42), fill=PINK)
        y = text_block(d, beat['card'], 760, 92, 3, CYAN, 815)
        if beat.get('detail'):
            text_block(d, beat['detail'], max(1005, y+35), 33, 2, '#e2d6e8', 815)
    d.text((74, 1645), 'Fuente visual: Rockstar Games · tráiler oficial', font=font(23, False), fill='#b7a5c5')
    d.text((74, 1690), 'GTA VI  ·  COMENTARIO Y ANÁLISIS', font=font(23, False), fill='#b7a5c5')
    img.save(path)
    return path


def valid_media_url(url):
    p = urlparse(url)
    return p.scheme == 'https' and p.hostname == 'media-rockstargames-com.akamaized.net' and p.path.startswith('/VI/downloads/videos/') and p.path.endswith('.mp4') and not p.query


def download_trailer(directory):
    if not valid_media_url(TRAILER): raise ValueError('Fuente no oficial')
    # Solo la descarga que Rockstar publica en su catálogo público; sin login ni extractor de YouTube.
    page = requests.get(MEDIA_PAGE, headers={'User-Agent': UA}, timeout=(15, 40))
    page.raise_for_status()
    if TRAILER not in page.text.replace('\\/', '/'):
        raise RuntimeError('Rockstar ya no ofrece este archivo en su página de descargas')
    cache = ROOT / '.cache' / 'rockstar'; cache.mkdir(parents=True, exist_ok=True)
    file = cache / 'launch_trailer.mp4'
    manifest = cache / 'launch_trailer.json'
    if file.exists() and manifest.exists():
        m = json.loads(manifest.read_text())
        with file.open('rb') as source: actual_hash = hashlib.file_digest(source, 'sha256').hexdigest()
        if m['url'] == TRAILER and file.stat().st_size == m['size'] and actual_hash == m['sha256'] == TRAILER_SHA256: return file, m
    part = file.with_suffix('.part'); size = 0; sha = hashlib.sha256()
    log('Descargando el tráiler oficial de Rockstar (no se publica ni se incluye completo en el artefacto).')
    try:
        with requests.get(TRAILER, headers={'User-Agent': UA}, timeout=(15, 90), stream=True) as r:
            r.raise_for_status()
            with part.open('wb') as target:
                for data in r.iter_content(1024*1024):
                    size += len(data)
                    if size > 900_000_000: raise ValueError('Descarga superior al límite previsto')
                    target.write(data); sha.update(data)
            expected = r.headers.get('Content-Length')
            if expected and size != int(expected): raise ValueError('Descarga incompleta')
        if sha.hexdigest() != TRAILER_SHA256: raise ValueError('El tráiler ha cambiado: revisar los planos antes de regenerar')
        if duration(part) < 70: raise ValueError('El tráiler no es el esperado')
        part.replace(file)
    finally:
        part.unlink(missing_ok=True)
    m = {'url':TRAILER, 'page':MEDIA_PAGE, 'size':size, 'sha256':sha.hexdigest(), 'downloaded_at':dt.datetime.now(dt.timezone.utc).isoformat()}
    manifest.write_text(json.dumps(m, indent=2))
    return file, m


def verify_sources(topic):
    docs = []
    for source in topic['sources']:
        r = requests.get(source, headers={'User-Agent':UA}, timeout=(15, 40)); r.raise_for_status()
        docs.append(r.text)
    combined = '\n'.join(docs)
    if not all(term.lower() in combined.lower() for term in topic['required_terms']):
        raise RuntimeError('Las fuentes actuales no confirman los términos del guion; requiere revisión editorial')
    log('Fuentes oficiales actuales comprobadas; no se usan rumores ni filtraciones.')


def caption_chunks(text):
    words = text.split(); chunks = []; current = []
    for word in words:
        candidate = current + [word]
        if current and (len(candidate) > 4 or len(wrap(' '.join(candidate), 66, 880)) > 2 or len(' '.join(candidate)) > 27):
            chunks.append(' '.join(current)); current = [word]
        else: current = candidate
    if current: chunks.append(' '.join(current))
    return chunks


def speak(topic, directory):
    from piper import PiperVoice, SynthesisConfig
    voice = PiperVoice.load(str(ensure_piper_model()), use_cuda=False)
    config = SynthesisConfig(length_scale=0.98, noise_scale=0.45, noise_w_scale=0.3)
    paths = []
    for i, beat in enumerate(topic['beats']):
        path = directory / f'voz_{i:02d}.wav'
        with wave.open(str(path), 'wb') as w: voice.synthesize_wav(beat['narration'], w, config)
        paths.append(path); log(f'Voz Short {i+1}/{len(topic["beats"])}: {duration(path):.1f}s')
    return paths


def ass_time(seconds):
    cs = round(seconds*100)
    return f'{cs//360000}:{cs//6000%60:02}:{cs//100%60:02}.{cs%100:02}'


def captions(topic, audio, directory):
    header = '''[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,DejaVu Sans,66,&H00FFFFFF,&H00FFFFFF,&H00201816,&H00201816,-1,0,0,0,100,100,0,0,3,8,0,2,90,150,360,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    events = []; srt = []; start = 0; index = 1
    for beat, wav in zip(topic['beats'], audio):
        seconds = duration(wav)
        phrases = caption_chunks(beat['narration'])
        weights = [sum(max(2,len(w)) for w in p.split()) for p in phrases]
        total = sum(weights); cursor = start
        # Sin alineación del modelo, se declara la sincronización por frases aproximada.
        for phrase, weight in zip(phrases, weights):
            end = cursor + seconds*weight/total
            text = r'\N'.join(wrap(phrase, 66, 840)).replace('{','').replace('}','')
            events.append(f'Dialogue: 0,{ass_time(cursor)},{ass_time(end)},Caption,,0,0,0,,{text}')
            srt += [str(index),f'{format_srt(cursor)} --> {format_srt(end)}',phrase,'']
            cursor = end; index += 1
        start += seconds
    ass = directory/'subtitulos.ass'; ass.write_text(header+'\n'.join(events)+'\n', encoding='utf-8')
    (directory/'subtitulos.srt').write_text('\n'.join(srt), encoding='utf-8')
    return ass


def render(topic, audio, trailer, directory, preset='veryfast'):
    work = directory/'render'; work.mkdir(exist_ok=True)
    files = []; excerpts = []
    for i, (beat, wav) in enumerate(zip(topic['beats'],audio)):
        seconds = duration(wav); card = make_card(topic,beat,i,work/f'card_{i}.png')
        target = work/f'beat_{i}.mp4'
        base = ['ffmpeg','-hide_banner','-loglevel','error','-y','-loop','1','-framerate',str(FPS),'-i',str(card)]
        excerpt = beat.get('excerpt')
        if excerpt:
            used = min(excerpt['duration'], seconds)
            if not 0 < used <= 3.2: raise ValueError('Recorte fuera del plan editorial')
            base += ['-ss',str(excerpt['start']),'-i',str(trailer)]
            vf = (f'[0:v]format=yuv420p[base];[1:v]scale=1080:940:force_original_aspect_ratio=increase,'
                  f'crop=1080:940,setsar=1,fps={FPS}[clip];'
                  f'[base][clip]overlay=0:460:enable=\'lt(t,{used:.3f})\':eof_action=pass[v]')
            base += ['-filter_complex',vf,'-map','[v]']
            excerpts.append({'beat':i,'source_start':excerpt['start'],'seconds':used,'reason':excerpt['reason']})
        else: base += ['-vf','format=yuv420p']
        run(base+['-t',f'{seconds:.6f}','-an','-r',str(FPS),'-c:v','libx264','-preset',preset,'-crf','20','-threads','2',str(target)], timeout=180)
        files.append(target);log(f'Montaje Short {i+1}/{len(audio)}')
    listing = work/'clips.txt'; listing.write_text(''.join(f"file '{p.resolve()}'\n" for p in files))
    wavlist = work/'voices.txt'; wavlist.write_text(''.join(f"file '{p.resolve()}'\n" for p in audio))
    full = work/'full.wav'
    run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(wavlist),'-ac','1','-ar','48000',str(full)])
    ass = captions(topic,audio,directory)
    ass_path = str(ass.resolve()).replace('\\','\\\\').replace(':','\\:').replace("'","\\'")
    out = directory/'short_vertical.mp4'
    run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(listing),'-i',str(full),
         '-vf',f"ass='{ass_path}'",'-af','loudnorm=I=-16:TP=-1.5:LRA=9','-ar','48000','-map','0:v','-map','1:a',
         '-c:v','libx264','-preset',preset,'-crf','20','-threads','2','-c:a','aac','-b:a','128k','-shortest','-movflags','+faststart',str(out)], timeout=600)
    make_card(topic,topic['beats'][0],0,directory/'portada_short.jpg',cover=True)
    return out, excerpts


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--topic-id',default=os.getenv('SHORT_TOPIC') or 'auto')
    args = parser.parse_args()
    if os.getenv('YOUTUBE_UPLOAD','false').lower() != 'false':
        raise RuntimeError('Los Shorts solo generan borradores; la publicación está desactivada')
    topics = json.loads((ROOT/'topics'/'shorts.json').read_text())
    if args.topic_id == 'auto':
        slot = max(0, (dt.date.today() - dt.date(2026,11,18)).days // 7)
        if slot >= len(topics): raise RuntimeError('Catálogo editorial agotado; no se repiten Shorts automáticamente')
        topic = topics[slot]
    else: topic = next((t for t in topics if t['id']==args.topic_id), None)
    if topic is None: raise ValueError('Tema Short desconocido')
    verify_sources(topic)
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d_%H%M%S')
    directory = OUT/f'{stamp}_{topic["id"]}';directory.mkdir(parents=True,exist_ok=True)
    (directory/'guion.json').write_text(json.dumps(topic,ensure_ascii=False,indent=2))
    trailer, source = download_trailer(directory)
    audios = speak(topic,directory)
    seconds = sum(duration(w) for w in audios)
    if not 25 <= seconds <= 59: raise ValueError(f'Duración de Short fuera de 25–59 s: {seconds:.1f}')
    video, excerpts = render(topic,audios,trailer,directory)
    metadata = {'title':topic['title'],'description':topic['summary']+'\n\nAnálisis original con voz sintética. Fragmentos del tráiler oficial de Rockstar Games sin su audio.\nFuentes:\n'+'\n'.join(topic['sources']+[MEDIA_PAGE]),
                'duration_seconds':duration(video),'width':WIDTH,'height':HEIGHT,'fps':FPS,'voice_provider':'piper','publication_enabled':False,
                'caption_timing':'Aproximación por longitud de frase dentro de cada toma de voz',
                'rights':{'status':'review_required','free_license':False,'copyright_clearance':False,'monetization_clearance':False,
                          'note':'No existe una duración que garantice evitar Content ID. El comentario y la atribución no garantizan una excepción legal.',
                          'rockstar_policy':POLICY,'youtube_policy':YOUTUBE_POLICY,'trailer_audio_used':False},
                'source':source,'excerpts':excerpts}
    (directory/'metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2))
    log(f'SHORT TERMINADO: {video} · {duration(video):.2f}s · 1080x1920 · NO PUBLICADO')


if __name__ == '__main__': main()
