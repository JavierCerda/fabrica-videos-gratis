"""La voz local no usa Gemini y la alternativa mantiene una voz uniforme."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import pipeline


class NarrationTests(unittest.TestCase):
    @patch.dict(os.environ, {'VOICE_PROVIDER':'piper'})
    @patch.object(pipeline, '_narration_audio', return_value=['voz.wav'])
    @patch.object(pipeline, 'gemini')
    def test_local_voice_never_calls_gemini(self, gemini, synthesize):
        self.assertEqual(pipeline.narration_audio({}, Path('.')), ['voz.wav'])
        self.assertEqual(synthesize.call_args.args[2], 'piper')
        gemini.assert_not_called()

    @patch.dict(os.environ, {'VOICE_PROVIDER':'gemini','VOICE_FALLBACK':'piper'})
    def test_quota_regenerates_entire_episode_with_one_provider(self):
        plan={'sections':[{'narration':'texto'} for _ in range(12)]}
        def synthesize(plan, directory, provider):
            if provider == 'gemini':
                raise pipeline.GeminiAPIError('tts', 429, 'daily quota')
            plan['voice']={'provider':provider}
            return [f'voz_{i:02d}.wav' for i in range(12)]
        with patch.object(pipeline, '_narration_audio', side_effect=synthesize) as build:
            result=pipeline.narration_audio(plan, Path('.'))
        self.assertEqual(len(result),12)
        self.assertEqual([c.args[2] for c in build.call_args_list],['gemini','piper'])
        self.assertEqual(plan['voice'], {'provider':'piper','fallback_from':'gemini'})

    @patch.dict(os.environ, {'VOICE_PROVIDER':'gemini','VOICE_FALLBACK':'piper'})
    @patch.object(pipeline, '_narration_audio', side_effect=pipeline.GeminiAPIError('tts',401,'unauthorized'))
    def test_auth_failure_does_not_get_hidden_by_fallback(self, build):
        with self.assertRaises(pipeline.GeminiAPIError):
            pipeline.narration_audio({},Path('.'))
        self.assertEqual(build.call_count,1)

    @patch.object(pipeline.requests, 'get')
    def test_voice_checksum_failure_leaves_no_model(self, get):
        response=Mock()
        response.iter_content.return_value=[b'corrupted model']
        context=Mock()
        context.__enter__=Mock(return_value=response)
        context.__exit__=Mock(return_value=False)
        get.return_value=context
        with tempfile.TemporaryDirectory() as tmp, patch.object(pipeline,'ROOT',Path(tmp)), patch.object(pipeline,'PIPER_FILES',{'test.onnx':'0'*64}):
            with self.assertRaisesRegex(ValueError,'Integridad'):
                pipeline.ensure_piper_model()
            self.assertEqual(list(Path(tmp).rglob('*.onnx')),[])
            self.assertEqual(list(Path(tmp).rglob('*.part')),[])


if __name__ == '__main__':
    unittest.main()
