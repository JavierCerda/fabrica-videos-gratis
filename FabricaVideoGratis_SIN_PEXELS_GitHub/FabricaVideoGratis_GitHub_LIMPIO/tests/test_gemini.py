"""Regresiones de la API, sin red, secretos ni consumo de cuota."""
import base64
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import pipeline


def response(status, obj):
    return Mock(status_code=status, json=Mock(return_value=obj))


def text_response(text='{}'):
    return response(200, {'candidates': [{'content': {'parts': [
        {'text': 'pensamiento interno', 'thought': True}, {'text': text}
    ]}}]})


@patch.dict(os.environ, {'GEMINI_API_KEY': 'test-secret'})
class GeminiTests(unittest.TestCase):
    @patch.object(pipeline.time, 'sleep')
    @patch.object(pipeline.requests, 'post')
    def test_404_uses_free_fallback(self, post, sleep):
        post.side_effect = [response(404, {}), text_response()]
        self.assertEqual(pipeline.gemini('guion', pipeline.FREE_TEXT_MODELS[0]), '{}')
        self.assertEqual(post.call_count, 2)
        self.assertIn('gemini-3-flash-preview:', post.call_args.args[0])
        sleep.assert_not_called()

    @patch.object(pipeline.time, 'sleep')
    @patch.object(pipeline.requests, 'post')
    def test_quota_error_does_not_switch_models(self, post, sleep):
        post.return_value = response(429, {'error': {'message': 'Quota exceeded test-secret'}})
        with self.assertRaisesRegex(RuntimeError, 'HTTP 429') as error:
            pipeline.gemini('guion', pipeline.FREE_TEXT_MODELS[0])
        self.assertNotIn('test-secret', str(error.exception))
        self.assertEqual(post.call_count, 3)
        self.assertEqual(len({c.args[0] for c in post.call_args_list}), 1)

    @patch.object(pipeline.requests, 'post')
    def test_tts_404_never_uses_text_model(self, post):
        post.return_value = response(404, {'error': {'message': 'not available'}})
        with self.assertRaisesRegex(RuntimeError, 'HTTP 404'):
            pipeline.gemini('voz', pipeline.FREE_TTS_MODELS[0], audio=True)
        self.assertEqual(post.call_count, 1)

    @patch.object(pipeline.requests, 'post')
    def test_paid_model_is_rejected_before_request(self, post):
        with self.assertRaisesRegex(ValueError, 'nivel gratuito'):
            pipeline.gemini('guion', 'gemini-premium')
        post.assert_not_called()

    @patch.object(pipeline.time, 'sleep')
    @patch.object(pipeline.requests, 'post')
    def test_empty_candidates_are_retried(self, post, sleep):
        post.side_effect = [response(200, {'candidates': []}), text_response()]
        self.assertEqual(pipeline.gemini('guion', pipeline.FREE_TEXT_MODELS[0]), '{}')

    @patch.object(pipeline.requests, 'post')
    def test_tts_decodes_pcm(self, post):
        post.return_value = response(200, {'candidates': [{'content': {'parts': [
            {'inlineData': {'data': base64.b64encode(b'\0\0').decode(),
                            'mimeType': 'audio/L16;rate=24000'}}
        ]}}]})
        self.assertEqual(pipeline.gemini('voz', pipeline.FREE_TTS_MODELS[0], audio=True),
                         (b'\0\0', 'audio/L16;rate=24000'))

    @patch.dict(os.environ, {'YOUTUBE_UPLOAD': 'false'})
    def test_upload_disabled_needs_no_oauth(self):
        pipeline.maybe_upload(Path('no-video.mp4'), {})


if __name__ == '__main__':
    unittest.main()
