"""Montaje real y mezcla de voz/música; sin descargas ni material ajeno."""
import json,subprocess,tempfile,sys
from pathlib import Path
from PIL import Image,ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.studio import render
from app.pipeline import duration
with tempfile.TemporaryDirectory() as temp:
    d=Path(temp);p=d/'test.jpg';im=Image.new('RGB',(1920,1080),'#213545');draw=ImageDraw.Draw(im);draw.ellipse((700,170,1200,900),fill='#88b8b1');im.save(p)
    wav=d/'voice.wav';subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','lavfi','-i','sine=frequency=180:sample_rate=48000:duration=8','-c:a','pcm_s16le',str(wav)],check=True)
    wav.with_suffix('.words.json').write_text(json.dumps([
        {'text':w,'start':a,'end':b} for w,a,b in [('Esta',.1,.5),('prueba',.55,1.),('comprueba',1.05,1.5),
        ('título',1.55,2.),('y',2.05,2.2),('subtítulos',2.25,2.9),('amarillos',2.95,3.7)]]))
    source=d/'source.mp4'
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','lavfi','-i','color=c=red:size=1280x720:rate=30:duration=5','-c:v','libx264','-preset','ultrafast',str(source)],check=True)
    topic={'id':'studio-test','hook':'UNA IDEA. MÁS IMÁGENES.','allowed_games':['gta6'],
           'beats':[{'narration':'Esta prueba comprueba una mezcla con música y una imagen completa, sin paneles de texto.',
                     'visuals':[{'game':'gta6','index':-1,'kind':'video','start':0,'focus':.5,'max_seconds':5,'fit':'contain'},
                                {'game':'gta6','index':0,'focus':.5,'fit':'contain'}]}]}
    video,music,used=render(topic,[wav],{('gta6',0):(p,{'type':'test_fixture'}),('gta6',-1):(source,{'type':'test_fixture'})},d,preset='ultrafast')
    streams=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(video)]))['streams']
    v=next(s for s in streams if s['codec_type']=='video');a=next(s for s in streams if s['codec_type']=='audio')
    assert (v['width'],v['height'])==(1080,1920)
    assert a['channels']==2 and a['sample_rate']=='48000'
    assert 7.9<duration(video)<8.2
    assert music['ducking'] and (d/'musica_original.wav').exists()
    assert {item['kind'] for item in used}=={'video','image'}
    assert abs(sum(item['seconds'] for item in used)-duration(video))<1/30+.001
    frame=d/'frame.png'
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-ss','2.5','-i',str(video),'-frames:v','1',str(frame)],check=True)
    import numpy as np
    with Image.open(frame) as im:
        pixels=np.array(im)
        assert np.max(np.abs(pixels[1800,100].astype(int)-np.array([139,101,181])))<5
        upper=pixels[80:350,48:1032].astype(int)
        assert ((upper[:,:,0]>220)&(upper[:,:,1]>220)&(upper[:,:,2]>220)).sum()>1000  # Título sigue presente a los 2,5 s.
        lower=pixels[1400:1650,80:960].astype(int)
        assert ((lower[:,:,0]>180)&(lower[:,:,1]>160)&(lower[:,:,2]<90)).sum()>1000  # Subtítulos realmente quemados.
    # El fundido ocurre solo dentro del marco; comprobar su punto medio en el MP4 real.
    colors=[]
    for i,t in enumerate((3.9,4.166667,4.4)):
        sample=d/f'fade_{i}.png'
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-ss',str(t),'-i',str(video),'-frames:v','1',str(sample)],check=True)
        with Image.open(sample) as im:
            colors.append(np.array(im)[900,540].astype(int))
            assert np.max(np.abs(np.array(im)[1800,100].astype(int)-np.array([139,101,181])))<5
    assert colors[0][0]>colors[1][0]+10>colors[2][0]+20
    assert colors[0][1]+10<colors[1][1]<colors[2][1]-10
    print('OK Studio: medios 984×984, lila plano, título permanente y subtítulos con marcas de voz')
