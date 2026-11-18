import tempfile
import unittest
from pathlib import Path
import numpy as np
import soundfile as sf
from app.studio import validate_visual,hook_layer
from app.studio_audio import compose_music

class StudioTests(unittest.TestCase):
    def test_wrong_game_is_rejected(self):
        with self.assertRaises(ValueError):validate_visual({'allowed_games':['gta4']},{'game':'sanandreas','focus':.5})
        with self.assertRaises(ValueError):validate_visual({'allowed_games':['gta4']},{'game':'gta4','focus':1.5})

    def test_music_is_finite_stereo_and_does_not_clip(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'music.wav';info=compose_music(p,6)
            audio,rate=sf.read(p)
            self.assertEqual(audio.shape,(6*48000,2))
            self.assertTrue(np.isfinite(audio).all())
            self.assertGreater(np.sqrt(np.mean(audio**2)),.01)
            self.assertLess(np.max(np.abs(audio)),.91)
            self.assertFalse(info['third_party_samples'])

    def test_hook_is_transparent_outside_its_brief_title(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as folder:
            p=hook_layer('TRES VIDAS. UNA CIUDAD.',Path(folder)/'hook.png')
            with Image.open(p) as image:
                self.assertEqual(image.size,(1080,1920))
                self.assertEqual(image.getpixel((400,400))[3],0)
                self.assertEqual(image.getpixel((400,1800))[3],0)
