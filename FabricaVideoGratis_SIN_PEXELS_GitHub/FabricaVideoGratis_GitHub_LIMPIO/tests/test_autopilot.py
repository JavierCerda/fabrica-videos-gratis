import copy
import datetime as dt
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from app.pipeline import ROOT
from app.editorial_queue import ingest,validate_topic,select_pending,signature
from app.production_state import StateStore
from app.youtube_publisher import YouTubePublisher,seo,quota_day,remaining_uploads,next_slot,classify_upload_error


class AutopilotTests(unittest.TestCase):
    def setUp(self):
        self.config=json.loads((ROOT/'config/automation.json').read_text())
        self.packet=json.loads((ROOT/'topics/inbox.json').read_text())
        self.now=dt.datetime.fromisoformat(self.packet['generated_at'])

    def test_previous_day_is_never_labeled_as_news_today(self):
        topic=copy.deepcopy(self.packet['topics'][0])
        topic['published_at']=(self.now-dt.timedelta(days=1)).isoformat()
        topic['research']['sources'][0]['published_at']=topic['published_at']
        with self.assertRaisesRegex(ValueError,'otro día'):validate_topic(topic,self.now,self.config)

    def test_fact_and_source_must_match(self):
        topic=copy.deepcopy(self.packet['topics'][0]);topic['editorial']['facts'].append('Dato inventado')
        with self.assertRaisesRegex(ValueError,'sin fuente'):validate_topic(topic,self.now,self.config)

    def test_stale_research_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'reciente'):
            validate_topic(self.packet['topics'][0],self.now+dt.timedelta(hours=3),self.config)

    def test_repeated_batch_is_not_queued_again_and_news_has_priority(self):
        state={'pending':[],'history':[]}
        self.assertEqual(sum(r['status']=='queued' for r in ingest(state,self.packet,self.now,self.config)),5)
        self.assertTrue(all(r['status']=='duplicate' for r in ingest(state,self.packet,self.now,self.config)))
        chosen=select_pending(state,self.now,self.config)
        self.assertEqual([t['content_type'] for t in chosen[:3]],['news']*3)
        self.assertGreaterEqual(chosen[0]['published_at'],chosen[1]['published_at'])

    def test_expired_news_is_not_published_but_curiosities_survive(self):
        state={'pending':[],'history':[]};ingest(state,self.packet,self.now,self.config)
        self.assertTrue(all(t['content_type']=='evergreen' for t in select_pending(state,self.now+dt.timedelta(days=2),self.config)))

    def test_upload_limit_uses_pacific_day_and_preserves_twelve_minute_spacing(self):
        state={'attempts':{quota_day(self.now):100}}
        self.assertEqual(remaining_uploads(state,self.now,100),0)
        a=next_slot(state,self.now,12);b=next_slot(state,self.now,12)
        self.assertEqual((dt.datetime.fromisoformat(b.replace('Z','+00:00'))-dt.datetime.fromisoformat(a.replace('Z','+00:00'))).total_seconds(),720)
        self.assertEqual(quota_day(dt.datetime(2026,11,19,1,tzinfo=dt.timezone.utc)),'2026-11-18')

    def test_wrong_channel_stops_before_uploading(self):
        client=Mock();client.channels.return_value.list.return_value.execute.return_value={'items':[{'id':'wrong-channel'}]}
        with patch.dict(os.environ,{'YT_CHANNEL_ID':'expected-channel'}):
            with self.assertRaisesRegex(RuntimeError,'no coincide'):YouTubePublisher(client)
        client.videos.assert_not_called()

    def test_remote_quota_error_pauses_until_reset_instead_of_retrying_uploads(self):
        error=RuntimeError();error.content=json.dumps({'error':{'errors':[{'reason':'quotaExceeded'}]}}).encode()
        reset=classify_upload_error(error,self.now)
        self.assertIsNotNone(reset)
        self.assertEqual(remaining_uploads({'quota_block_until':reset},self.now,100),0)
        self.assertIsNone(classify_upload_error(RuntimeError('network timeout'),self.now))

    def test_seo_uses_gaming_spanish_sources_and_explicit_public_schedule(self):
        topic=self.packet['topics'][0];body=seo(topic,signature(topic),'2026-11-18T20:00:00Z',self.config)
        self.assertEqual(body['snippet']['categoryId'],'20');self.assertEqual(body['snippet']['defaultAudioLanguage'],'es')
        self.assertIn(topic['sources'][0],body['snippet']['description']);self.assertIn('#Shorts',body['snippet']['description'])
        self.assertEqual(body['status']['privacyStatus'],'private');self.assertIn('publishAt',body['status'])

    def test_state_survives_new_process_without_secrets(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'state.json';one=StateStore('test',path);state=one.load()
            state['pending']=[{'id':'a-unique-topic'}];one.save(state)
            self.assertEqual(StateStore('test',path).load()['pending'],state['pending'])
