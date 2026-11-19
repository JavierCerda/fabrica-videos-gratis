"""Transporte HMAC a Apps Script: pruebas privadas y publicación programada verificada."""
import base64
import datetime as dt
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
# Canal público autorizado por el propietario y fijado también en Apps Script.
EXPECTED_CHANNEL_ID = 'UCuMX_olnpHMCr06FQBdCzjQ'


def bridge_selected():
    return bool(os.getenv('YT_BRIDGE_URL') or os.getenv('YT_BRIDGE_KEY'))


def bridge_readiness():
    names = ('YT_BRIDGE_URL', 'YT_BRIDGE_KEY')
    missing = [n for n in names if not os.getenv(n)]
    return {'ready': not missing, 'missing': missing, 'backend': 'apps-script', 'requires_remote_verification': True}


class BridgeError(RuntimeError):
    def __init__(self, code):
        super().__init__('Conexión de Google: ' + code)
        self.code = code  # Código cerrado del protocolo; nunca cuerpos ni credenciales.
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
        self.channel_id = os.getenv('YT_CHANNEL_ID') or EXPECTED_CHANNEL_ID
        if self.channel_id != EXPECTED_CHANNEL_ID:
            raise RuntimeError('El canal configurado no coincide con el autorizado por el propietario')
        self.session = session or requests.Session()
        result = self.call('readiness')
        if result.get('channel_id') != self.channel_id or not isinstance(result.get('private_test_only'), bool):
            raise RuntimeError('El canal o los permisos del puente no coinciden')
        self.private_test_only = result['private_test_only']
        if not self.private_test_only and (result.get('publication_enabled') is not True or result.get('protocol_version') != 2):
            raise RuntimeError('El puente no ha confirmado la programación pública')
        self.channel = {'id': self.channel_id, 'snippet': {'title': result.get('title', '')}}

    def call(self, action, **values):
        payload = json.dumps({**values, 'action': action, 'channel_id': self.channel_id,
                              'timestamp': int(time.time()), 'nonce': uuid.uuid4().hex},
                             # El JSON firmado viaja en ASCII; JSON.parse restaura tildes y eñes.
                             # Evita diferencias de charset entre Python y Utilities de Google.
                             separators=(',', ':'), ensure_ascii=True)
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
                       'UNVERIFIED_SCHEDULE', 'PUBLICATION_PAUSED', 'BAD_SCHEDULE',
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

    def inspect_upload(self, key, publish_at=None):
        if not re.fullmatch(r'[a-f0-9]{24}', key):
            raise ValueError('Huella editorial inválida')
        result = self.call('inspect', key=key)
        if result.get('found') is not True:
            return {'found': False, 'uncertain': result.get('uncertain') is True}
        requested = publish_at if publish_at is not None else result.get('requested_publish_at')
        return {**self.verified_result(result, requested), 'found': True}

    def verified_result(self, result, requested):
        actual = result.get('status', {})
        if (not re.fullmatch(r'[A-Za-z0-9_-]{11}', result.get('video_id', '')) or
                result.get('channel_id', self.channel_id) != self.channel_id):
            raise BridgeError('UNVERIFIED_UPLOAD')
        if requested:
            scheduled = (actual.get('privacyStatus') == 'private' and actual.get('publishAt') and
                         parse_time(actual['publishAt']).replace(microsecond=0) == parse_time(requested).replace(microsecond=0))
            public = (actual.get('privacyStatus') == 'public' and result.get('public_verified') is True and
                      parse_time(requested) <= dt.datetime.now(dt.timezone.utc))
            if result.get('schedule_verified') is not True or not (scheduled or public):
                raise BridgeError('UNVERIFIED_SCHEDULE')
        elif (result.get('private_verified') is not True or actual.get('privacyStatus') != 'private' or actual.get('publishAt')):
            raise BridgeError('UNVERIFIED_PRIVACY')
        result['url'] = 'https://www.youtube.com/watch?v=' + result['video_id']
        result['schedule_verified'] = bool(requested)
        return result

    def upload(self, video, body, notify=False):
        requested = body.get('status', {}).get('publishAt')
        if notify or body.get('status', {}).get('privacyStatus') != 'private':
            raise RuntimeError('Cada subida debe comenzar privada y sin avisos')
        if requested:
            if self.private_test_only:
                raise RuntimeError('El puente solo admite pruebas privadas sin programación ni avisos')
            delay = (parse_time(requested) - dt.datetime.now(dt.timezone.utc)).total_seconds()
            if not 120 <= delay <= 7 * 86400:
                raise ValueError('La programación debe estar entre dos minutos y siete días en el futuro')
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
        return self.verified_result(result, requested)


def parse_time(value):
    try:
        parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError('timezone')
        return parsed.astimezone(dt.timezone.utc)
    except (AttributeError, TypeError, ValueError):
        raise BridgeError('BAD_SCHEDULE') from None
