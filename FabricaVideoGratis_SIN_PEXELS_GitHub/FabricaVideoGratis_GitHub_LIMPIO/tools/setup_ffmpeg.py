"""Instala FFmpeg/FFprobe desde la distribución pública de FFmpeg-Builds.

Usa un nombre de rama estable y el SHA-256 publicado por GitHub, sin analizar
HTML de terceros ni instalar paquetes de Ubuntu. Solo extrae los dos binarios.
"""
from pathlib import Path
import argparse
import hashlib
import os
import shutil
import subprocess
import tarfile
import tempfile

import requests

API = 'https://api.github.com/repos/FFmpeg-Builds/FFmpeg-Builds/releases/latest'
ASSET = 'ffmpeg-n8.1-latest-linux64-gpl-8.1.tar.xz'
PREFIX = 'https://github.com/FFmpeg-Builds/FFmpeg-Builds/releases/download/'


def install(destination):
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'FabricaVideoGratis/3.0'}
    token = os.getenv('FFMPEG_GITHUB_TOKEN')
    if token:
        headers['Authorization'] = f'Bearer {token}'
    result = requests.get(API, headers=headers, timeout=(15, 45))
    result.raise_for_status()
    asset = next((a for a in result.json()['assets'] if a['name'] == ASSET), None)
    if not asset:
        raise RuntimeError(f'No se encuentra la distribución estable {ASSET}')
    url = asset['browser_download_url']
    expected = asset.get('digest', '')
    if not url.startswith(PREFIX) or not expected.startswith('sha256:'):
        raise ValueError('Origen o checksum de FFmpeg no válido')
    print(f'Descargando {ASSET} ({asset["size"] // 1_000_000} MB)', flush=True)
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / 'ffmpeg.tar.xz'
        digest = hashlib.sha256(); size = 0
        # El token de GitHub NO se envía a los servidores de descarga.
        with requests.get(url, stream=True, timeout=(15, 60)) as response:
            response.raise_for_status()
            with archive.open('wb') as output:
                for chunk in response.iter_content(1024 * 1024):
                    size += len(chunk)
                    if size > 220_000_000:
                        raise ValueError('Distribución de FFmpeg demasiado grande')
                    output.write(chunk); digest.update(chunk)
        if size != asset['size'] or digest.hexdigest() != expected.removeprefix('sha256:'):
            raise ValueError('SHA-256 o tamaño de FFmpeg incorrecto; no se ejecutará')
        print('SHA-256 de FFmpeg verificado', flush=True)
        found = set()
        with tarfile.open(archive, 'r|xz') as bundle:
            for member in bundle:
                name = Path(member.name).name
                if not member.isfile() or name not in ('ffmpeg', 'ffprobe'):
                    continue
                if name in found or member.size > 350_000_000:
                    raise ValueError('Binario inesperado en la distribución de FFmpeg')
                target = destination / name
                with bundle.extractfile(member) as source, target.open('wb') as output:
                    shutil.copyfileobj(source, output)
                target.chmod(0o755)
                found.add(name)
        if found != {'ffmpeg', 'ffprobe'}:
            raise RuntimeError('La distribución no incluye FFmpeg y FFprobe')
    for binary in ('ffmpeg', 'ffprobe'):
        subprocess.run([str(destination / binary), '-version'], check=True)
    if os.getenv('GITHUB_PATH'):
        with open(os.environ['GITHUB_PATH'], 'a', encoding='utf-8') as paths:
            paths.write(str(destination.resolve()) + '\n')
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--destination', type=Path, default=Path(os.getenv('RUNNER_TEMP', tempfile.gettempdir())) / 'fabrica-ffmpeg')
    install(parser.parse_args().destination)
