import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from app.pipeline import ROOT
from app.editorial_queue import validate_topic, timestamp
from app.neural_voice import VOICES, DEFAULT_VOICE, DELIVERIES, spoken_tokens
from app.smooth_media import plan_shots


class ComedyPreviewTests(unittest.TestCase):
    def setUp(self):
        self.topic=json.loads((ROOT/'experiments/comedy_preview/topic.json').read_text())
        self.config=json.loads((ROOT/'config/automation.json').read_text())
        self.config['editorial_version']=4

    def test_factual_hook_longer_script_and_natural_profanity(self):
        validate_topic(self.topic,timestamp(self.topic['research']['verified_at']),self.config)
        words=spoken_tokens(' '.join(b['narration'] for b in self.topic['beats']))
        self.assertGreaterEqual(len(words),90)
        self.assertLessEqual(len(words),125)
        self.assertEqual(len(self.topic['beats']),5)
        self.assertTrue(self.topic['beats'][0]['narration'].startswith('En GTA cinco'))
        self.assertIn('joder',words)
        self.assertEqual(len(self.topic['editorial']['jokes']),3)

    def test_no_unsupported_factual_claim_is_added(self):
        self.assertEqual(set(self.topic['editorial']['facts']),
            {f for source in self.topic['research']['sources'] for f in source['supported_facts']})
        self.assertEqual(len({(v['game'],v['index']) for beat in self.topic['beats'] for v in beat['visuals']}),5)
        self.assertEqual(self.topic['content_type'],'evergreen')

    def test_old_narrator_and_existing_profile_are_not_changed(self):
        self.assertEqual(DEFAULT_VOICE,'es-ES-AlvaroNeural')
        self.assertIn('es-ES-XimenaNeural',VOICES)
        self.assertEqual(DELIVERIES['comedy_preview']['rate'],'+7%')
        from experiments.comedy_preview import run
        self.assertNotIn('youtube',run.main.__code__.co_names)
        self.assertIn('preview',run.main.__code__.co_consts)

    def test_five_shots_cover_longer_audio_without_repetition(self):
        with patch('app.smooth_media.duration',return_value=8):
            shots=plan_shots(self.topic,[Path(str(i)) for i in range(5)])
        self.assertGreaterEqual(len(shots),5)
        self.assertEqual(sum(s['frames'] for s in shots),5*8*30)


if __name__=='__main__':
    unittest.main()
