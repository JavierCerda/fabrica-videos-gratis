"""Transporte opcional a Apps Script. Solo pruebas privadas, con peticiones HMAC."""
import base64
import hashlib
import hmac
import json
import os
import re
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse

import requests

MAX_VIDEO_BYTES = 32 * 1024 * 1024


def bridge_selected():
    return bool(os.getenv('YT_BRIDGE_URL') or os.getenv('YT_BRIDGE_KEY'))


def bridge_readiness():
    names = ('YT_BRIDGE_URL', 'YT_BRIDGE_KEY', 'YT_CHANNEL_ID')
    missing = [n for n in names if not os.getenv(n)]
    return {'ready': not missing, 'missing': missing, 'backend': 'apps-script', 'private_test_only': True}


class BridgeError(RuntimeError):
    def __init__(self, code):
        super().__init__('Conexión de Google: ' + code)
        reason = 'quotaExceeded' if code == 'DAILY_UPLOAD_LIMIT' else code
        self.content = json.dumps({'error': {'errors': [{'reason': reason}]}}).encode()


class AppsScriptPublisher:
    private_test_only = True

    def __init__(self, session=None):
        check = bridge_readiness()
        if not check['ready']:
            raise RuntimeError('Conexión de Google pendiente: ' + ', '.join(check['missing']))
        self.endpoint = os.environ['YT_BRIDGE_URL']
        if not re.fullmatch(r'https://script\.google\.com/macros/s/[A-Za-z0-9_-]+/exec', self.endpoint):
            raise ValueError('El puente debe ser una implementación HTTPS de Google Apps Script')
        self.key = os.environ['YT_BRIDGE_KEY']
        if len(self.key) < 43:
            raise ValueError('La clave del puente debe tener al menos cuarenta y tres caracteres')
        self.channel_id = os.environ['YT_CHANNEL_ID']
        self.session = session or requests.Session()
        result = self.call('readiness')
        if result.get('channel_id') != self.channel_id or result.get('private_test_only') is not True:
            raise RuntimeError('El canal o los permisos del puente no coinciden')
        self.channel = {'id': self.channel_id, 'snippet': {'title': result.get('title', '')}}

    def call(self, action, **values):
        payload = json.dumps({**values, 'action': action, 'channel_id': self.channel_id,
                              'timestamp': int(time.time()), 'nonce': uuid.uuid4().hex},
                             separators=(',', ':'), ensure_ascii=False)
        signature = base64.urlsafe_b64encode(hmac.new(self.key.encode(), payload.encode(), hashlib.sha256).digest()).decode().rstrip('=')
        envelope = {'payload': payload, 'signature': signature}
        try:
            # Nunca reintentar un POST de subida. Una respuesta perdida se reconcilia por el diario.
            response = self.session.post(self.endpoint, json=envelope, timeout=(15, 330), allow_redirects=False)
            for _ in range(2):
                if response.status_code not in (302, 303):
                    break
                location = response.headers.get('Location', '')
                target = urlparse(location)
                if target.scheme != 'https' or target.hostname != 'script.googleusercontent.com' or target.username or target.password:
                    raise BridgeError('UNEXPECTED_REDIRECT')
                # La redirección de ContentService es un GET; no reenviar cuerpo o firma.
                response = self.session.get(location, timeout=(15, 30), allow_redirects=False)
            if response.status_code != 200:
                raise BridgeError('HTTP_ERROR_DO_NOT_RETRY_UPLOAD')
            data = response.json()
        except BridgeError:
            raise
        except Exception:
            raise BridgeError('NETWORK_OR_RESPONSE_ERROR_DO_NOT_RETRY_UPLOAD') from None
        if not isinstance(data, dict) or data.get('ok') is not True:
            code = data.get('error') if isinstance(data, dict) else None
            allowed = {'NOT_CONFIGURED', 'UNAUTHORIZED', 'WRONG_CHANNEL', 'PRIVATE_TEST_ONLY',
                       'UNCERTAIN_UPLOAD_DO_NOT_RETRY', 'DAILY_UPLOAD_LIMIT', 'REPLAY',
                       'UNVERIFIED_UPLOAD', 'UNVERIFIED_PRIVACY', 'BAD_METADATA', 'BAD_MEDIA',
                       'GOOGLE_API_ERROR_DO_NOT_RETRY_UPLOAD', 'BUSY_DO_NOT_RETRY_UPLOAD'}
            raise BridgeError(code if code in allowed else 'INVALID_RESPONSE_DO_NOT_RETRY_UPLOAD')
        result = data.get('result')
        if not isinstance(result, dict):
            raise BridgeError('INVALID_RESPONSE_DO_NOT_RETRY_UPLOAD')
        return result

    def recent_markers(self):
        result = self.call('markers')
        if any(not re.fullmatch(r'[a-f0-9]{24}', key) or not isinstance(value, str) for key, value in result.items()):
            raise BridgeError('INVALID_MARKERS')
        return result

    def upload(self, video, body, notify=False):
        if notify or body.get('status', {}).get('privacyStatus') != 'private' or body.get('status', {}).get('publishAt'):
            raise RuntimeError('El puente solo admite pruebas privadas sin programación ni avisos')
        tags = body.get('snippet', {}).get('tags', [])
        keys = [tag[4:] for tag in tags if isinstance(tag, str) and re.fullmatch(r'fvg-[a-f0-9]{24}', tag)]
        if len(keys) != 1:
            raise ValueError('La prueba debe llevar una sola huella editorial')
        path = Path(video)
        if not 12 <= path.stat().st_size <= MAX_VIDEO_BYTES:
            raise ValueError('El puente admite MP4 de hasta treinta y dos MiB')
        content = path.read_bytes()
        if content[4:8] != b'ftyp':
            raise ValueError('El archivo no tiene cabecera MP4')
        result = self.call('upload', key=keys[0], body=body, notify=False,
                           video_base64=base64.b64encode(content).decode())
        actual = result.get('status', {})
        if (not re.fullmatch(r'[A-Za-z0-9_-]{11}', result.get('video_id', '')) or
                result.get('private_verified') is not True or actual.get('privacyStatus') != 'private' or actual.get('publishAt')):
            raise BridgeError('UNVERIFIED_PRIVACY')
        result['url'] = 'https://www.youtube.com/watch?v=' + result['video_id']
        result['schedule_verified'] = False
        return result
