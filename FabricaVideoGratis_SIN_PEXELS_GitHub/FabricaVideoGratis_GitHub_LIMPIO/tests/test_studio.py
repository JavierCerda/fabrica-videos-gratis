import tempfile
import json
import unittest
from unittest.mock import patch
from pathlib import Path
import numpy as np
import soundfile as sf
from app.studio import validate_visual
from app.studio_audio import compose_music
from app.purple_layout import short_phrases,yellow_captions
from app.neural_voice import narrate as neural_narrate

class StudioTests(unittest.TestCase):
    def test_neural_failure_stops_without_reusing_rejected_voices(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch('app.neural_voice.synthesize',side_effect=RuntimeError('unavailable')):
                with self.assertRaisesRegex(RuntimeError,'sin usar las voces rechazadas'):
                    neural_narrate({'beats':[{'narration':'Una frase.'}]},Path(folder))
            with self.assertRaises(ValueError):
                neural_narrate({'beats':[]},Path(folder),voice_name='em_alex')

    def test_wrong_game_is_rejected(self):
        with self.assertRaises(ValueError):validate_visual({'allowed_games':['gta4']},{'game':'sanandreas','focus':.5})
        with self.assertRaises(ValueError):validate_visual({'allowed_games':['gta4']},{'game':'gta4','focus':1.5})
        with self.assertRaises(ValueError):validate_visual({'allowed_games':['gta4']},{'game':'gta4','kind':'video','index':-1,'start':0})
        with self.assertRaises(ValueError):validate_visual({'allowed_games':['gta6']},{'game':'gta6','kind':'video','index':-1,'start':-1})

    def test_caption_phrases_preserve_every_word_without_overloading(self):
        text='¿Sabías que Liberty City guarda historias completamente diferentes entre sus calles?'
        phrases=short_phrases(text)
        self.assertEqual(' '.join(phrases),text)
        self.assertTrue(all(len(p.split())<=3 for p in phrases))

    def test_music_is_finite_stereo_and_does_not_clip(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'music.wav';info=compose_music(p,6)
            audio,rate=sf.read(p)
            self.assertEqual(audio.shape,(6*48000,2))
            self.assertTrue(np.isfinite(audio).all())
            self.assertGreater(np.sqrt(np.mean(audio**2)),.01)
            self.assertLess(np.max(np.abs(audio)),.91)
            self.assertFalse(info['third_party_samples'])

    def test_captions_follow_word_times_across_pauses(self):
        with tempfile.TemporaryDirectory() as folder:
            d=Path(folder);wav=d/'voice.wav'
            wav.with_suffix('.words.json').write_text(json.dumps([
                {'text':'Jason','start':.2,'end':.6},{'text':'fue','start':.7,'end':.9},
                {'text':'militar','start':1.,'end':1.4},{'text':'antes','start':2.8,'end':3.2}]))
            with patch('app.purple_layout.duration',return_value=4):
                ass=yellow_captions({'beats':[{'narration':'Jason fue militar antes'}]},[wav],d).read_text()
            self.assertIn('Dialogue: 0,0:00:00.20,0:00:01.46,',ass)
            self.assertIn('Dialogue: 0,0:00:02.80,0:00:03.26,',ass)
            self.assertIn('JASON FUE MILITAR',ass)
            wav.with_suffix('.words.json').unlink()
            with patch('app.purple_layout.duration',return_value=4),self.assertRaises(ValueError):
                yellow_captions({'beats':[{'narration':'Jason fue militar antes'}]},[wav],d)
