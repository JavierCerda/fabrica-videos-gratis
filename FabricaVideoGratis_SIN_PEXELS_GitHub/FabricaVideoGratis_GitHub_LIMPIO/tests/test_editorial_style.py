import copy
import datetime as dt
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from app.pipeline import ROOT
from app.editorial_queue import validate_editorial_style,ingest,select_pending,signature
from app.smooth_media import plan_shots


class EditorialStyleTests(unittest.TestCase):
    def setUp(self):
        self.packet=json.loads((ROOT/'tests/fixtures/editorial_packet.json').read_text())
        self.topic=copy.deepcopy(self.packet['topics'][0])
        self.config=json.loads((ROOT/'config/automation.json').read_text())
        self.now=dt.datetime.fromisoformat(self.packet['generated_at'])

    def test_long_sentence_and_unrelated_unreviewed_media_stop_the_new_profile(self):
        self.topic['beats'][0]['narration']=' '.join(['palabra']*23)+'.'
        with self.assertRaisesRegex(ValueError,'22 palabras'):validate_editorial_style(self.topic)
        self.topic=copy.deepcopy(self.packet['topics'][0])
        del self.topic['beats'][0]['visuals'][0]['relevance']
        with self.assertRaisesRegex(ValueError,'relación'):validate_editorial_style(self.topic)

    def test_two_ranges_of_one_video_remain_two_shots(self):
        visual={'game':'gta6','index':-1,'kind':'video','max_seconds':6}
        topic={'beats':[{'visuals':[{**visual,'start':8}]},{'visuals':[{**visual,'start':38}]}]}
        with patch('app.smooth_media.duration',return_value=4):
            shots=plan_shots(topic,[Path('a'),Path('b')])
        self.assertEqual(len(shots),2)
        self.assertEqual([s['visual']['start'] for s in shots],[8,38])

    def test_old_drafts_do_not_hide_new_eligible_drafts_in_a_full_batch(self):
        old={**self.topic,'editorial_version':0,'queued_at':self.now.isoformat()}
        new={**self.topic,'queued_at':self.now.isoformat()}
        state={'pending':[copy.deepcopy(old) for _ in range(5)]+[new]}
        self.assertEqual(select_pending(state,self.now,self.config),[new])
        self.assertEqual(len(state['pending']),6)

    def test_revision_replaces_only_unpublished_draft_and_preserves_queue_position(self):
        key=signature(self.topic)
        old={**self.topic,'editorial_version':0,'queue_key':key,'queued_at':'2026-11-18T10:00:00Z'}
        state={'pending':[copy.deepcopy(old)],'history':[]}
        self.assertEqual(ingest(state,{'schema_version':1,'topics':[self.topic]},self.now,self.config)[0]['status'],'revised')
        self.assertEqual(len(state['pending']),1)
        self.assertEqual(state['pending'][0]['queued_at'],old['queued_at'])
        state={'pending':[old],'history':[{'key':key,'status':'uploading'}]}
        self.assertEqual(ingest(state,{'schema_version':1,'topics':[self.topic]},self.now,self.config)[0]['status'],'duplicate')
        self.assertEqual(state['pending'][0]['editorial_version'],0)

    def test_queue_only_and_paused_production_cannot_create_a_publisher(self):
        from app.autopilot import run_batch
        with patch('app.autopilot.StateStore') as store,patch('app.autopilot.YouTubePublisher') as publisher,patch('app.autopilot.produce') as produce,patch('app.autopilot.report_summary'),patch('app.autopilot.readiness',return_value={'missing':[]}),patch('app.autopilot.dt.datetime') as clock:
            clock.now.return_value=self.now
            for mode,status in [('queue','queue_saved'),('production','publication_paused')]:
                store.return_value.load.return_value={'schema_version':1,'pending':[],'history':[]}
                self.assertEqual(run_batch(mode)['status'],status)
            publisher.assert_not_called();produce.assert_not_called()

    def test_news_priority_is_independent_of_the_number_of_news_in_the_live_inbox(self):
        a={**self.topic,'id':'old-news-fixture','content_type':'news','published_at':(self.now-dt.timedelta(hours=2)).isoformat(),'queued_at':self.now.isoformat()}
        b={**a,'id':'new-news-fixture','published_at':(self.now-dt.timedelta(hours=1)).isoformat()}
        evergreen={**self.topic,'queued_at':self.now.isoformat()}
        state={'pending':[evergreen,a,b]}
        self.assertEqual([t['id'] for t in select_pending(state,self.now,self.config)],[b['id'],a['id'],evergreen['id']])
