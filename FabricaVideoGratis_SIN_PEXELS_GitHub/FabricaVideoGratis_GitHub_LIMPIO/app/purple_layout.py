"""Plantilla lila con ventana cuadrada y subtítulos amarillos de lectura rápida."""
import json
import itertools
import soundfile as sf
from PIL import Image, ImageDraw, ImageFont

from .pipeline import ROOT, duration, format_srt
from .shorts import ass_time, wrap, fit, font

SIZE, X, Y = 984, 48, 414
PURPLE = '#8B65B5'


def title_font(size):
    face=ImageFont.truetype(str(ROOT/'assets/fonts/Manrope.ttf'),size)
    face.set_variation_by_name('ExtraBold')
    return face


def title_lines(title):
    words=title.upper().split()
    for size in range(82,49,-2):
        face=title_font(size);candidates=[]
        for count in (1,2,3):
            for breaks in itertools.combinations(range(1,len(words)),count-1):
                cuts=(0,*breaks,len(words))
                lines=[' '.join(words[a:b]) for a,b in zip(cuts,cuts[1:])]
                widths=[face.getlength(s) for s in lines]
                if max(widths)<=880 and count*(size+8)<=207:
                    # Evitar una última línea de una sola palabra o separar GTA VI.
                    penalty=500 if any(a.endswith('GTA') and b.startswith(('VI','IV','V ')) for a,b in zip(lines,lines[1:])) else 0
                    candidates.append((count*80+max(widths)-min(widths)+penalty,lines))
        if candidates:return size,min(candidates,key=lambda c:c[0])[1]
    raise ValueError('El título no cabe en la cabecera moderna')


def frame_background(path, title, label='GTA', news_date=None):
    image = Image.new('RGB',(1080,1920),PURPLE)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((48,64,1032,370),radius=32,fill='#291F3E')
    small=title_font(27);badge=label.upper()
    if news_date:badge+='  ·  '+news_date
    draw.rounded_rectangle((80,91,106+small.getlength(badge),135),radius=12,fill='#FFE600')
    draw.text((94,94),badge,font=small,fill='#291F3E')
    size,lines=title_lines(title)
    top=158+(190-len(lines)*(size+8))/2
    for i,line in enumerate(lines):
        draw.text((80,top+i*(size+8)),line,font=title_font(size),fill='white' if i==0 else '#EEE4FF')
    image.save(path)
    return path


def short_phrases(text):
    phrases, words = [], []
    for word in text.split():
        candidate = ' '.join(words+[word])
        if words and (len(words)>=3 or len(candidate)>23):
            phrases.append(' '.join(words));words=[]
        words.append(word)
    if words:phrases.append(' '.join(words))
    return phrases


def yellow_captions(topic, audio, directory):
    # ASS usa colores BGR: 00E6FF equivale a amarillo #FFE600.
    header = '''[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,DejaVu Sans,74,&H0000E6FF,&H0000E6FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,5,2,2,100,140,330,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    events, srt, start, index, all_spans = [], [], 0., 1, []
    for beat, wav in zip(topic['beats'],audio):
        # FFprobe redondea a microsegundos; las marcas usan la precisión real del WAV.
        info=sf.info(wav)
        seconds=info.frames/info.samplerate
        timing=wav.with_suffix('.words.json')
        if timing.exists():
            words=json.loads(timing.read_text());groups=[];group=[]
            if not words or any(not w['text'] or not 0<=w['start']<w['end']<=seconds for w in words):
                raise ValueError('Marcas de palabra vacías o fuera del audio')
            if any(a['end']>b['start'] for a,b in zip(words,words[1:])):
                raise ValueError('Marcas de palabra solapadas')
            for word in words:
                candidate=' '.join(w['text'] for w in group+[word])
                try:fits=len(wrap(candidate.upper(),74,820))<=2
                except ValueError:fits=False
                if group and (sum(len(w['text'].split()) for w in group+[word])>3 or len(candidate)>23 or not fits):
                    groups.append(group);group=[]
                group.append(word)
            if group:groups.append(group)
            spans=[(' '.join(w['text'] for w in g),start+g[0]['start'],
                    start+min(seconds,g[-1]['end']+.06,
                              groups[k+1][0]['start'] if k+1<len(groups) else seconds)) for k,g in enumerate(groups)]
        else:
            raise ValueError('Faltan los tiempos de palabra de la voz; no se inventa la sincronización')
        all_spans.extend(spans)
        start+=seconds
    # Mantener cada grupo hasta el siguiente: no apagar y encender el texto entre palabras.
    for k,(phrase,cursor,end) in enumerate(all_spans):
        end=all_spans[k+1][1] if k+1<len(all_spans) else min(start,end+.12)
        size,lines=fit(phrase.upper(),max_size=74,max_lines=2,width=820)
        override=('{'+r'\fs'+str(size)+'}') if size!=74 else ''
        text=override+r'\N'.join(lines).replace('{','').replace('}','')
        events.append(f'Dialogue: 0,{ass_time(cursor)},{ass_time(end)},Caption,,0,0,0,,{text}')
        srt += [str(index),f'{format_srt(cursor)} --> {format_srt(end)}',phrase,'']
        index+=1
    ass=directory/'subtitulos.ass';ass.write_text(header+'\n'.join(events)+'\n',encoding='utf-8')
    (directory/'subtitulos.srt').write_text('\n'.join(srt),encoding='utf-8')
    return ass
