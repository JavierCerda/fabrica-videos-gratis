"""Montaje real y mezcla de voz/música; sin descargas ni material ajeno."""
import json,subprocess,tempfile,sys
from pathlib import Path
from PIL import Image,ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.studio import render
from app.pipeline import duration
with tempfile.TemporaryDirectory() as temp:
    d=Path(temp);p=d/'test.jpg';im=Image.new('RGB',(1920,1080),'#213545');draw=ImageDraw.Draw(im);draw.ellipse((700,170,1200,900),fill='#88b8b1');im.save(p)
    wav=d/'voice.wav';subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','lavfi','-i','sine=frequency=180:sample_rate=48000:duration=4','-c:a','pcm_s16le',str(wav)],check=True)
    source=d/'source.mp4'
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','lavfi','-i','testsrc2=size=1280x720:rate=30:duration=3','-c:v','libx264','-preset','ultrafast',str(source)],check=True)
    topic={'id':'studio-test','hook':'UNA IDEA. MÁS IMÁGENES.','allowed_games':['gta6'],
           'beats':[{'narration':'Esta prueba comprueba una mezcla con música y una imagen completa, sin paneles de texto.',
                     'visuals':[{'game':'gta6','index':-1,'kind':'video','start':0,'focus':.5},
                                {'game':'gta6','index':0,'focus':.5}]}]}
    video,music,used=render(topic,[wav],{('gta6',0):(p,{'type':'test_fixture'}),('gta6',-1):(source,{'type':'test_fixture'})},d,preset='ultrafast')
    streams=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(video)]))['streams']
    v=next(s for s in streams if s['codec_type']=='video');a=next(s for s in streams if s['codec_type']=='audio')
    assert (v['width'],v['height'])==(1080,1920)
    assert a['channels']==2 and a['sample_rate']=='48000'
    assert 3.9<duration(video)<4.2
    assert music['ducking'] and (d/'musica_original.wav').exists()
    assert {item['kind'] for item in used}=={'video','image'}
    assert abs(sum(item['seconds'] for item in used)-duration(video))<1/30+.001
    frame=d/'frame.png'
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-ss','2.5','-i',str(video),'-frames:v','1',str(frame)],check=True)
    import numpy as np
    with Image.open(frame) as im:
        pixels=np.array(im)
        r,g,b=map(int,pixels[1800,100]);assert b>r>g  # Fondo lila fuera del medio.
        lower=pixels[1380:1650,80:960].astype(int)
        assert ((lower[:,:,0]>180)&(lower[:,:,1]>160)&(lower[:,:,2]<90)).sum()>1000  # Subtítulos realmente quemados.
    print('OK Studio: vídeo/foto en cuadrado, fondo lila, subtítulos amarillos, voz y música estéreo')
