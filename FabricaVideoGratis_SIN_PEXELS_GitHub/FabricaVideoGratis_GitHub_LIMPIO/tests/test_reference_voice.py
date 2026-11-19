import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from app.reference_voice import reference_file,checked_words,profile,verified_recognition,PRECISE_ASR
from app.neural_voice import DEFAULT_VOICE


class ReferenceVoiceTests(unittest.TestCase):
    def test_current_narrator_and_archived_reference_are_preserved(self):
        self.assertEqual(DEFAULT_VOICE,'es-ES-AlvaroNeural')
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

    def test_roman_game_title_and_written_accents_preserve_spoken_words(self):
        words=checked_words('GTA cinco, qué película.',[
            {'text':'GTA V','start':.1,'end':.8},{'text':'que','start':.8,'end':1.},
            {'text':'pelicula','start':1.,'end':1.5}])
        self.assertEqual([w['text'] for w in words],['GTA cinco','qué','película'])
        with self.assertRaisesRegex(RuntimeError,'coincide'):
            checked_words('GTA cinco',[{'text':'GTA VI','start':.1,'end':.8}])
        with self.assertRaisesRegex(RuntimeError,'coincide'):
            checked_words('cinco',[{'text':'V','start':.1,'end':.8}])

    def test_zero_duration_article_uses_a_real_recognized_phrase_span(self):
        words=checked_words('el problema viene',[
            {'text':'el','start':1.,'end':1.},{'text':'problema','start':1.,'end':1.4},
            {'text':'viene','start':1.4,'end':1.7}])
        self.assertEqual(words,[{'text':'el problema','start':1.,'end':1.4},
            {'text':'viene','start':1.4,'end':1.7}])

    def test_second_recognizer_rechecks_identical_audio_without_accepting_near_matches(self):
        bad=[{'text':'tene','start':.1,'end':.5}]
        good=[{'text':'tiene','start':.1,'end':.5}]
        with tempfile.TemporaryDirectory() as temp:
            wav=Path(temp)/'voice.wav'
            with patch('app.reference_voice.recognize',side_effect=[bad,good]) as recognize:
                words,verification=verified_recognition(wav,'tiene',temp)
            self.assertEqual([call.args[0] for call in recognize.call_args_list],[wav,wav])
            self.assertEqual([call.kwargs['precise'] for call in recognize.call_args_list],[False,True])
            self.assertEqual(words,good)
            self.assertEqual(verification['asr_repository'],PRECISE_ASR[0])
            with patch('app.reference_voice.recognize',return_value=bad):
                with self.assertRaisesRegex(RuntimeError,"esperado 'tiene', reconocido 'tene'"):
                    verified_recognition(wav,'tiene',temp)

    def test_precise_recognizer_cannot_approve_a_missing_word(self):
        heard=[{'text':'puto','start':.1,'end':.5}]
        with tempfile.TemporaryDirectory() as temp:
            with patch('app.reference_voice.recognize',return_value=heard):
                with self.assertRaisesRegex(RuntimeError,'final'):
                    verified_recognition(Path(temp)/'voice.wav','puto casting',temp)
