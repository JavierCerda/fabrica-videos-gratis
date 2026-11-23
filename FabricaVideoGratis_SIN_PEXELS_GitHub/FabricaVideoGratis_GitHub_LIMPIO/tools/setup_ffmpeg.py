"""Comprueba FFmpeg y FFprobe del sistema sin depender de releases externas.

En el runner Ubuntu de GitHub, usa herramientas ya instaladas. Si faltan,
instala paquetes firmados de los repositorios de Ubuntu; no descarga binarios
de endpoints variables ni consume tokens de GitHub.
"""
from pathlib import Path
import argparse
import os
import shutil
import subprocess
import tempfile


def install(destination):
    binaries = ('ffmpeg', 'ffprobe')
    found = {name: shutil.which(name) for name in binaries}
    if not all(found.values()):
        if os.getenv('GITHUB_ACTIONS') != 'true' or not shutil.which('apt-get'):
            missing = ', '.join(name for name in binaries if not found[name])
            raise RuntimeError('Faltan herramientas gratuitas: ' + missing +
                               '. Instala ffmpeg del gestor de paquetes del sistema.')
        privilege = ['sudo'] if shutil.which('sudo') else []
        subprocess.run(privilege + ['apt-get', 'update', '-qq'], check=True, timeout=180)
        subprocess.run(privilege + ['apt-get', 'install', '-y', '--no-install-recommends',
                                    'ffmpeg'], check=True, timeout=240)
        found = {name: shutil.which(name) for name in binaries}
        if not all(found.values()):
            raise RuntimeError('Los paquetes de Ubuntu no proporcionaron ffmpeg y ffprobe')
    for name in binaries:
        subprocess.run([found[name], '-version'], check=True, timeout=30,
                       stdout=subprocess.DEVNULL)
    print('FFmpeg y FFprobe del sistema verificados: ' + str(found['ffmpeg']), flush=True)
    return Path(found['ffmpeg']).parent


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--destination', type=Path, default=Path(
        os.getenv('RUNNER_TEMP', tempfile.gettempdir())) / 'fabrica-ffmpeg')
    install(parser.parse_args().destination)
