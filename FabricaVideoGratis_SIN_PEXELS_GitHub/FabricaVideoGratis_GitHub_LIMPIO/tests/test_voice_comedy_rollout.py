"""El despliegue de Ximena y el humor sencillo no pierde la cola antigua."""
import copy
import json
import unittest
from app.pipeline import ROOT
from app.editorial_queue import validate_topic,select_pending,signature,timestamp
from app.neural_voice import DEFAULT_VOICE,VOICES,DELIVERIES

class RolloutTests(unittest.TestCase):
    def setUp(self):
        self.config=json.loads((ROOT/'config/automation.json').read_text())
        self.demo=json.loads((ROOT/'tests/fixtures/comedia_sencilla_topic.json').read_text())
        self.old=json.loads((ROOT/'tests/fixtures/informativo_packet.json').read_text())['topics'][0]
        self.now=timestamp(self.demo['research']['verified_at'])

    def test_new_profile_is_valid_and_does_not_force_jokes(self):
        self.assertEqual(self.config['editorial_version'],3)
        self.assertEqual(self.config['editorial_generation_version'],5)
        validate_topic(self.demo,self.now,self.config)
        clean=copy.deepcopy(self.demo)
        clean['editorial']['jokes']=[]
        validate_topic(clean,self.now,self.config)
        self.assertIn('Trevor',' '.join(x['narration'] for x in self.demo['beats']))

    def test_v5_rejects_short_v4_scripts_but_retains_legacy_compatibility(self):
        from app.neural_voice import spoken_tokens
        long_topic=copy.deepcopy(self.demo)
        long_topic['editorial_version']=5
        with self.assertRaisesRegex(ValueError,'Longitud inesperada'):
            validate_topic(long_topic,self.now,self.config)
        # Synthetic extra sentences exercise the boundary, not a publishable topic.
        index=0
        additions=[' Esta frase de prueba permite comprobar el límite.',
                   ' Otra frase comprueba la longitud del nuevo perfil.',
                   ' El validador conserva las reglas anteriores.']
        for extra in additions:
            long_topic['beats'][index]['narration']+=extra
            index=(index+1)%len(long_topic['beats'])
        words=len(spoken_tokens(' '.join(b['narration'] for b in long_topic['beats'])))
        self.assertTrue(120<=words<=150)
        validate_topic(long_topic,self.now,self.config)

    def test_legacy_queue_is_eligible_but_v4_runs_first(self):
        old=copy.deepcopy(self.old);new=copy.deepcopy(self.demo)
        for t in (old,new):
            t['queue_key']=signature(t);t['queued_at']=self.now.isoformat()
        state={'pending':[old,new],'history':[]}
        result=select_pending(state,self.now,self.config)
        self.assertEqual([x['id'] for x in result],[new['id'],old['id']])
        self.assertEqual(len(state['pending']),2)

    def test_voice_is_ximena_and_original_test_fallback_is_unmodified(self):
        self.assertIn('es-ES-XimenaNeural',VOICES)
        self.assertEqual(DELIVERIES['comedy_preview']['rate'],'+7%')
        self.assertEqual(DEFAULT_VOICE,'es-ES-AlvaroNeural')
        workflow=(ROOT.parents[1]/'.github/workflows/video_semanal.yml').read_text()
        self.assertIn('SHORT_VOICE: es-ES-XimenaNeural',workflow)
        self.assertIn('SHORT_VOICE: es-ES-AlvaroNeural',workflow)
        self.assertTrue(self.config['publication_enabled'])

if __name__=='__main__':unittest.main()
