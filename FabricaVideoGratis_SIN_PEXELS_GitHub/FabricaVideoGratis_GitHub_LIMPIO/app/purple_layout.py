"""Plantilla lila con ventana cuadrada y subtítulos amarillos de lectura rápida."""
import json
from PIL import Image, ImageDraw

from .pipeline import duration, format_srt
from .shorts import ass_time, wrap, fit, font

SIZE, X, Y = 984, 48, 414
PURPLE = '#8B65B5'


def frame_background(path, title):
    image = Image.new('RGB',(1080,1920),PURPLE)
    draw = ImageDraw.Draw(image)
    size,lines=fit(title.upper(),max_size=78,max_lines=3,width=950)
    top=105+(230-len(lines)*(size+10))/2
    for i,line in enumerate(lines):
        draw.text(((1080-font(size).getlength(line))/2,top+i*(size+10)),line,
                  font=font(size),fill='white',stroke_width=3,stroke_fill='#31203F')
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
    events, srt, start, index = [], [], 0., 1
    for beat, wav in zip(topic['beats'],audio):
        seconds=duration(wav)
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
                if group and (len(group)>=3 or len(candidate)>23 or not fits):
                    groups.append(group);group=[]
                group.append(word)
            if group:groups.append(group)
            spans=[(' '.join(w['text'] for w in g),start+g[0]['start'],
                    start+min(seconds,g[-1]['end']+.06,
                              groups[k+1][0]['start'] if k+1<len(groups) else seconds)) for k,g in enumerate(groups)]
        else:
            raise ValueError('Faltan los tiempos de palabra de la voz; no se inventa la sincronización')
        for phrase,cursor,end in spans:
            size,lines=fit(phrase.upper(),max_size=74,max_lines=2,width=820)
            override=f'{{\\fs{size}}}' if size!=74 else ''
            text=override+r'\N'.join(lines).replace('{','').replace('}','')
            events.append(f'Dialogue: 0,{ass_time(cursor)},{ass_time(end)},Caption,,0,0,0,,{text}')
            srt += [str(index),f'{format_srt(cursor)} --> {format_srt(end)}',phrase,'']
            index+=1
        start+=seconds
    ass=directory/'subtitulos.ass';ass.write_text(header+'\n'.join(events)+'\n',encoding='utf-8')
    (directory/'subtitulos.srt').write_text('\n'.join(srt),encoding='utf-8')
    return ass
