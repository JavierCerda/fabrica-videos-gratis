import tempfile
import json
import unittest
from unittest.mock import patch
from pathlib import Path
import numpy as np
import soundfile as sf
from app.studio import validate_visual,allocate_frames
from app.studio_audio import compose_music
from app.purple_layout import short_phrases,yellow_captions
from app.neural_voice import narrate as neural_narrate,spoken_tokens

class StudioTests(unittest.TestCase):
    def test_short_official_clip_does_not_loop_or_desynchronize_voice(self):
        frames=allocate_frames(241,[{'max_seconds':.8},{},{},{}])
        self.assertEqual(sum(frames),241)
        self.assertEqual(frames[0],24)
        self.assertLessEqual(max(frames[1:])-min(frames[1:]),1)
        with self.assertRaises(ValueError):allocate_frames(15,[{'max_seconds':.8},{}])

    def test_profanity_is_compared_without_masking(self):
        self.assertEqual(spoken_tokens('¡Joder, los putos pájaros, coño!'),['joder','los','putos','pájaros','coño'])
        with self.assertRaises(ValueError):
            neural_narrate({'beats':[{'narration':'Joder.','delivery':'invented'}]},Path('/tmp'))

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
            with patch('app.purple_layout.sf.info',return_value=type('Audio',(),{'frames':4*48000,'samplerate':48000})()):
                ass=yellow_captions({'beats':[{'narration':'Jason fue militar antes'}]},[wav],d).read_text()
            self.assertIn('Dialogue: 0,0:00:00.20,0:00:02.80,',ass)
            self.assertIn('Dialogue: 0,0:00:02.80,0:00:03.38,',ass)
            self.assertIn('JASON FUE MILITAR',ass)
            wav.with_suffix('.words.json').unlink()
            with patch('app.purple_layout.sf.info',return_value=type('Audio',(),{'frames':4*48000,'samplerate':48000})()),self.assertRaises(ValueError):
                yellow_captions({'beats':[{'narration':'Jason fue militar antes'}]},[wav],d)

    def test_wide_spanish_words_never_make_three_caption_lines(self):
        text='LAS COMUNICACIONES DE LA GUARDIA COSTERA COÑO'
        with tempfile.TemporaryDirectory() as folder:
            d=Path(folder);wav=d/'voice.wav'
            words=[{'text':w,'start':i*.5,'end':i*.5+.4} for i,w in enumerate(text.split())]
            wav.with_suffix('.words.json').write_text(json.dumps(words))
            with patch('app.purple_layout.sf.info',return_value=type('Audio',(),{'frames':5*48000,'samplerate':48000})()):
                ass=yellow_captions({'beats':[{'narration':text}]},[wav],d).read_text()
            events=[l.split(',',9)[9] for l in ass.splitlines() if l.startswith('Dialogue:')]
            self.assertTrue(all(e.count(r'\N')<=1 for e in events))
            self.assertEqual(' '.join(events).replace(r'\N',' '),text)
