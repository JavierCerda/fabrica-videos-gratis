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
    topic={'id':'studio-test','hook':'UNA IDEA. MÁS IMÁGENES.','allowed_games':['gta4'],
           'beats':[{'narration':'Esta prueba comprueba una mezcla con música y una imagen completa, sin paneles de texto.',
                     'visuals':[{'game':'gta4','index':0,'focus':.5}]}]}
    video,music,used=render(topic,[wav],{('gta4',0):(p,{'type':'test_fixture'})},d,preset='ultrafast')
    streams=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(video)]))['streams']
    v=next(s for s in streams if s['codec_type']=='video');a=next(s for s in streams if s['codec_type']=='audio')
    assert (v['width'],v['height'])==(1080,1920)
    assert a['channels']==2 and a['sample_rate']=='48000'
    assert 3.9<duration(video)<4.2
    assert music['ducking'] and (d/'musica_original.wav').exists()
    print('OK Studio: vídeo vertical sin paneles, gancho breve, voz y música estéreo con ducking')
