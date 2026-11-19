"""Preparar el motor CPU reproducible de la referencia A1; nunca activar servicios."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import requests

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.reference_voice import profile,reference_file,RUNTIME,digest
from app.neural_voice import DEFAULT_VOICE


def ensure_runtime():
    p=profile();reference_file();RUNTIME.mkdir(parents=True,exist_ok=True)
    engine=RUNTIME/'engine'
    if not engine.exists():
        engine.mkdir();subprocess.run(['git','init',str(engine)],check=True)
        subprocess.run(['git','-C',str(engine),'fetch','--depth','1',p['engine_repository'],p['engine_revision']],check=True)
        subprocess.run(['git','-C',str(engine),'checkout','--detach','FETCH_HEAD'],check=True)
    actual=subprocess.check_output(['git','-C',str(engine),'rev-parse','HEAD'],text=True).strip()
    if actual!=p['engine_revision']:raise RuntimeError('La revisión del motor no coincide con la revisada')
    binary=engine/'build/bin/voxcpm2-cli'
    if not binary.exists():
        cmake=shutil.which('cmake')
        if not cmake:raise RuntimeError('Falta CMake para compilar el motor gratuito')
        subprocess.run([cmake,'-S',str(engine),'-B',str(engine/'build'),'-DCMAKE_BUILD_TYPE=Release',
            '-DGGML_CUDA=OFF','-DLLAMA_CURL=OFF','-DLLAMA_BUILD_TESTS=OFF','-DLLAMA_BUILD_EXAMPLES=OFF'],check=True)
        subprocess.run([cmake,'--build',str(engine/'build'),'--target','voxcpm2-cli','-j4'],check=True)
    models=RUNTIME/'models';models.mkdir(exist_ok=True)
    for item in p['weights']:
        target=models/item['name']
        if target.exists() and target.stat().st_size==item['size'] and digest(target)==item['sha256']:continue
        partial=target.with_suffix('.part');h=hashlib.sha256();size=0
        url=f"https://huggingface.co/{p['weights_repository']}/resolve/{p['weights_revision']}/{item['name']}"
        try:
            with requests.get(url,stream=True,timeout=(20,120)) as response:
                response.raise_for_status()
                with partial.open('wb') as stream:
                    for chunk in response.iter_content(1024*1024):
                        size+=len(chunk)
                        if size>item['size']:raise RuntimeError('Modelo con tamaño inesperado')
                        h.update(chunk);stream.write(chunk)
            if size!=item['size'] or h.hexdigest()!=item['sha256']:raise RuntimeError('Integridad del modelo no válida')
            partial.replace(target)
        finally:partial.unlink(missing_ok=True)
    print('VoxCPM2 A1 preparado: CPU, referencia y pesos verificados; sin fallback.')


if __name__=='__main__':
    config=json.loads((ROOT/'config/automation.json').read_text())
    selected=os.getenv('SHORT_VOICE') or DEFAULT_VOICE
    needed=selected=='voxcpm2-a1' and (os.getenv('RUN_MODE')=='preview' or config.get('publication_enabled',False))
    if '--when-needed' not in sys.argv or needed:ensure_runtime()
    else:print('La ejecución no necesita preparar VoxCPM2; se conserva la referencia archivada.')
