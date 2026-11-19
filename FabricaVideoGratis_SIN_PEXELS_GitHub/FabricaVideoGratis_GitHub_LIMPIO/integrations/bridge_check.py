"""Diagnóstico del transporte: nunca envía una solicitud válida de subida."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.youtube_bridge import AppsScriptPublisher, BridgeError


def main():
    publisher = AppsScriptPublisher()
    print('BRIDGE_CHANNEL_VERIFIED_ASCII_TRANSPORT')
    markers = publisher.recent_markers()
    key = '2c9cf27381e1ac34887568f7'
    print('PRIOR_ATTEMPT_MARKER=' + markers.get(key, 'absent'))
    # El servidor rechaza privacyStatus public antes del diario y de videos.insert.
    # No se envía un MP4: solo texto sintético para probar tamaño y UTF-8.
    try:
        publisher.call('upload', key=key, notify=False,
                       body={'snippet': {'title': 'Diagnóstico español: botón'},
                             'status': {'privacyStatus': 'public'}},
                       video_base64='A' * 4_000_000)
    except BridgeError as error:
        code = str(error).removeprefix('Conexión de Google: ')
        print('LARGE_REQUEST_RESULT=' + code)
        if code == 'PRIVATE_TEST_ONLY':
            print('BRIDGE_TRANSPORT_VERIFIED_NO_UPLOAD')
            return
        raise RuntimeError('El transporte no confirmó el rechazo seguro esperado') from None
    raise RuntimeError('El servidor no rechazó la solicitud de diagnóstico')


if __name__ == '__main__':
    main()
