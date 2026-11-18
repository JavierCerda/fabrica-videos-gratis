import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import soundfile as sf
from app.continuity import tighten_pauses,silent_spans
from app.neural_voice import narrate
from app.smooth_media import plan_shots


class ContinuityTests(unittest.TestCase):
    def test_only_silence_is_shortened_and_word_times_follow_the_edit(self):
        rate=48000;t=np.arange(rate)/rate
        voice=np.sin(2*np.pi*220*t)*.2
        samples=np.r_[voice,np.zeros(rate),voice]
        words=[{'text':'Joder','start':.01,'end':.95},{'text':'coño','start':2.05,'end':2.95}]
        edited,times,info=tighten_pauses(samples,rate,words)
        np.testing.assert_array_equal(edited[:rate],voice)
        np.testing.assert_array_equal(edited[-rate:],voice)
        self.assertEqual([w['text'] for w in times],['Joder','coño'])
        self.assertAlmostEqual(times[1]['start'],2.05-info['removed_seconds'])
        self.assertFalse(silent_spans(edited,rate,minimum=.7))

    def test_single_take_splits_without_losing_any_audio_samples(self):
        async def fake(text,path,voice,delivery):
            self.assertEqual(text,'Joder. Coño.')
            samples=np.sin(np.arange(4*48000)*.03)*.1
            sf.write(path,samples,48000,subtype='PCM_16')
            path.with_suffix('.words.json').write_text(json.dumps([
                {'text':'Joder','start':.1,'end':1.8},{'text':'Coño','start':2.1,'end':3.8}]))
        with tempfile.TemporaryDirectory() as temp:
            d=Path(temp)
            with patch('app.neural_voice.synthesize',side_effect=fake) as synth:
                paths,meta=narrate({'beats':[{'narration':'Joder.'},{'narration':'Coño.'}]},d)
            self.assertEqual(synth.call_count,1)
            joined=np.concatenate([sf.read(p,dtype='int16')[0] for p in paths])
            np.testing.assert_array_equal(joined,sf.read(d/'toma_continua.wav',dtype='int16')[0])
            self.assertTrue(meta['continuous_take'])

    def test_flash_clips_are_excluded_and_consecutive_duplicate_photos_are_merged(self):
        topic={'beats':[{'visuals':[{'game':'gta6','index':-2,'kind':'video','max_seconds':.8},
            {'game':'gta6','index':14},{'game':'gta6','index':15}]}]*2}
        with patch('app.smooth_media.duration',return_value=7):shots=plan_shots(topic,[Path('a'),Path('b')])
        self.assertTrue(all(s['visual']['index']>=0 for s in shots))
        self.assertTrue(all(s['frames']>=90 for s in shots))
        self.assertEqual(sum(s['frames'] for s in shots),14*30)
        self.assertTrue(all(a['visual']['index']!=b['visual']['index'] for a,b in zip(shots,shots[1:])))
