"""Prueba end-to-end sin Internet, Gemini, Pexels ni YouTube."""
import tempfile, subprocess, wave, math, struct, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.pipeline import render_video,duration,create_subtitles,create_thumbnail

with tempfile.TemporaryDirectory() as t:
    d=Path(t)
    sample=d/'sample.mp4'
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','lavfi','-i','testsrc2=size=640x360:rate=24:duration=8','-c:v','libx264','-pix_fmt','yuv420p',str(sample)],check=True)
    paths=[]
    for j in range(2):
        wav=d/f'voz_{j}.wav'
        with wave.open(str(wav),'wb') as f:
            f.setnchannels(1);f.setsampwidth(2);f.setframerate(24000)
            pcm=bytearray()
            for k in range(int(24000*3.1)):
                n=int(2500*math.sin(2*math.pi*(220+j*110)*k/24000))
                pcm+=struct.pack('<h',n)
            f.writeframes(pcm)
        paths.append(wav)
    plan={'sections':[{'narration':'Este vídeo de prueba verifica que los subtítulos y el montaje con metraje funcionen correctamente, sin conectar ninguna cuenta.','heading':'Test','stock_query':'test'}, {'narration':'Una segunda toma de prueba debe acabar después de la primera y conservar sonido sincronizado.','heading':'Test dos','stock_query':'test'}]}
    out=render_video(plan,paths,[[sample,sample],[sample,sample]],d,test_mode=True)
    thumb=create_thumbnail({'title':'Cinco comprobaciones antes de comprar tecnología usada'},out,d)
    assert thumb.exists() and thumb.stat().st_size > 5000
    print('OK',out.name,'duración',duration(out),'bytes',out.stat().st_size,'miniatura',thumb.stat().st_size)
