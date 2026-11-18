"""Plantilla lila con ventana cuadrada y subtítulos amarillos de lectura rápida."""
from PIL import ImageDraw

from .pipeline import duration, format_srt
from .shorts import ass_time, background, wrap

SIZE, X, Y = 940, 70, 430


def frame_background(path):
    image = background()
    draw = ImageDraw.Draw(image)
    draw.rectangle((X-6,Y-6,X+SIZE+5,Y+SIZE+5),fill='#6d458f')
    draw.rectangle((X-2,Y-2,X+SIZE+1,Y+SIZE+1),fill='#bd92df')
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
        seconds=duration(wav);phrases=short_phrases(beat['narration'])
        weights=[sum(max(2,len(w)) for w in p.split()) for p in phrases]
        total=sum(weights);cursor=start
        for phrase,weight in zip(phrases,weights):
            end=cursor+seconds*weight/total
            text=r'\N'.join(wrap(phrase.upper(),74,820)).replace('{','').replace('}','')
            events.append(f'Dialogue: 0,{ass_time(cursor)},{ass_time(end)},Caption,,0,0,0,,{text}')
            srt += [str(index),f'{format_srt(cursor)} --> {format_srt(end)}',phrase,'']
            cursor=end;index+=1
        start+=seconds
    ass=directory/'subtitulos.ass';ass.write_text(header+'\n'.join(events)+'\n',encoding='utf-8')
    (directory/'subtitulos.srt').write_text('\n'.join(srt),encoding='utf-8')
    return ass
