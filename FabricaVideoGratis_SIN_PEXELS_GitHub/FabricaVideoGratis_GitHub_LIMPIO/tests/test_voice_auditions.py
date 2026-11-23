import json
import unittest
from pathlib import Path
from app.pipeline import ROOT


class VoiceAuditionsSafetyTests(unittest.TestCase):
    def test_auditions_have_no_youtube_dependencies_or_publish(self):
        from experiments.comedy_preview import voice_auditions as v
        self.assertNotIn("youtube", v.main.__code__.co_names)
        self.assertEqual(len(v.KOKORO_ASSETS), 2)
        self.assertTrue(v.SAMPLE.startswith("En GTA cinco"))
        self.assertIn("Trevor", v.SAMPLE)
        self.assertIn("perro", v.SAMPLE)
        self.assertNotIn("Óscar canino", v.SAMPLE)

    def test_voice_samples_use_only_local_output_folder(self):
        from experiments.comedy_preview import voice_auditions as v
        self.assertEqual(set(v.KOKORO_ASSETS),
                         {"kokoro-v1.0.onnx", "voices-v1.0.bin"})


if __name__ == "__main__":
    unittest.main()
