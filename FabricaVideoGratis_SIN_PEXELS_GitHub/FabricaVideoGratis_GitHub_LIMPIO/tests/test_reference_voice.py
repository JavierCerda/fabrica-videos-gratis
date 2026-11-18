import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from app.reference_voice import reference_file,checked_words,profile
from app.neural_voice import DEFAULT_VOICE


class ReferenceVoiceTests(unittest.TestCase):
    def test_selected_reference_is_present_and_pinned(self):
        self.assertEqual(DEFAULT_VOICE,'voxcpm2-a1')
        self.assertEqual(hashlib.sha256(reference_file().read_bytes()).hexdigest(),profile()['reference_sha256'])

    def test_altered_reference_stops_instead_of_selecting_another_voice(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'sample.flac';p.write_bytes(b'wrong audio')
            with patch('app.reference_voice.ROOT',Path(d)),patch('app.reference_voice.profile',return_value={'reference':p.name,'reference_sha256':'0'*64}):
                with self.assertRaisesRegex(RuntimeError,'sin sustituirla'):reference_file()

    def test_recognition_cannot_silently_drop_a_word_or_profanity(self):
        heard=[{'text':'Joder','start':.1,'end':.5},{'text':'vecino','start':.6,'end':1.}]
        with self.assertRaisesRegex(RuntimeError,'coincide'):checked_words('Joder puto vecino',heard)
        with self.assertRaisesRegex(RuntimeError,'final'):checked_words('Joder vecino coño',heard)

    def test_real_word_span_can_hold_two_written_words_without_inventing_times(self):
        words=checked_words('GTA cinco, joder.',[{'text':'GTA5','start':.2,'end':.9},{'text':'joder','start':1.,'end':1.4}])
        self.assertEqual(words,[{'text':'GTA cinco','start':.2,'end':.9},{'text':'joder','start':1.,'end':1.4}])

    def test_invalid_timestamps_are_rejected(self):
        with self.assertRaisesRegex(RuntimeError,'no fiables'):
            checked_words('Joder',[{'text':'Joder','start':1.,'end':1.}])

    def test_zero_duration_article_uses_a_real_recognized_phrase_span(self):
        words=checked_words('el problema viene',[
            {'text':'el','start':1.,'end':1.},{'text':'problema','start':1.,'end':1.4},
            {'text':'viene','start':1.4,'end':1.7}])
        self.assertEqual(words,[{'text':'el problema','start':1.,'end':1.4},
            {'text':'viene','start':1.4,'end':1.7}])
