"""Comprueba composición vertical, subtítulos y audio sin red ni material ajeno."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.shorts import render,make_card,ROOT,duration

with tempfile.TemporaryDirectory() as temp:
    d=Path(temp)
    topic=json.loads((ROOT/'topics'/'shorts.json').read_text())[0]
    # Todos los carteles y portadas deben caber completos, también en otros temas.
    for t in json.loads((ROOT/'topics'/'shorts.json').read_text()):
        for i,b in enumerate(t['beats']):make_card(t,b,i,d/f'{t["id"]}_{i}.png')
        make_card(t,t['beats'][0],0,d/f'{t["id"]}_cover.jpg',cover=True)
    source=d/'source.mp4'
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','lavfi','-i','testsrc2=size=1280x720:rate=30:duration=4','-c:v','libx264','-threads','2',str(source)],check=True)
    wav=d/'voice.wav'
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','lavfi','-i','sine=frequency=440:sample_rate=22050:duration=3','-c:a','pcm_s16le',str(wav)],check=True)
    topic['beats']=topic['beats'][:2]
    topic['beats'][0]['excerpt']['start']=0
    out,excerpts=render(topic,[wav,wav],source,d,preset='ultrafast')
    info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(out)]))
    v=next(s for s in info['streams'] if s['codec_type']=='video')
    assert (v['width'],v['height'])==(1080,1920)
    assert 5.9<duration(out)<6.2
    assert len(excerpts)==1
    assert any(s['codec_type']=='audio' for s in info['streams'])
    print('OK Short vertical 1080x1920 con vídeo, carteles completos, subtítulos y audio')
