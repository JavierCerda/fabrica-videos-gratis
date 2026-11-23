import copy
import datetime as dt
import json
from contextlib import ExitStack
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
from app import autopilot
from app.editorial_queue import signature
from app.youtube_bridge import BridgeError
from app.pipeline import ROOT


class ProductionSafetyTests(unittest.TestCase):
    def test_hourly_budget_survives_restarts_and_excludes_private_tests(self):
        now=dt.datetime(2026,11,19,14,30,tzinfo=dt.timezone.utc)
        state={'history':[{'started_at':now.isoformat(),'status':'scheduled'} for _ in range(4)]}
        state['history'].append({'started_at':now.isoformat(),'purpose':'private_test'})
        self.assertEqual(autopilot.remaining_this_hour(state,now,5),1)
        state['history'].append({'started_at':now.isoformat(),'status':'uncertain'})
        self.assertEqual(autopilot.remaining_this_hour(state,now,5),0)
    def setUp(self):
        self.packet=json.loads((ROOT/'tests/fixtures/informativo_packet.json').read_text())
        self.now=dt.datetime.fromisoformat(self.packet['generated_at'])
        self.topic=copy.deepcopy(self.packet['topics'][0])
        self.key=signature(self.topic)
        self.config=json.loads((ROOT/'config/automation.json').read_text())
        self.config['publication_enabled']=True
        self.state={'pending':[],'history':[],'attempts':{}}
        self.publisher=Mock(private_test_only=False)
        self.publisher.inspect_upload.return_value={'found':False,'uncertain':False}
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);(self.root/'config').mkdir();(self.root/'topics').mkdir()
        (self.root/'config/automation.json').write_text(json.dumps(self.config))
        (self.root/'topics/inbox.json').write_text(json.dumps(self.packet))
        self.video=self.root/'output/short_vertical.mp4';self.video.parent.mkdir()
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        now=self.now
        class Clock(dt.datetime):
            @classmethod
            def now(cls,tz=None):return now.astimezone(tz or dt.timezone.utc)
        self.stack.enter_context(patch('app.autopilot.dt.datetime',Clock))
        self.stack.enter_context(patch.multiple('app.autopilot',ROOT=self.root,OUT=self.root/'output'))
        store=self.stack.enter_context(patch('app.autopilot.StateStore'))
        store.return_value.load.return_value=self.state
        self.stack.enter_context(patch('app.autopilot.YouTubePublisher',return_value=self.publisher))
        self.stack.enter_context(patch('app.autopilot.readiness',return_value={'ready':True,'missing':[]}))
        self.render=self.stack.enter_context(patch('app.autopilot.produce',return_value=self.video))
        self.stack.enter_context(patch('app.autopilot.inspect',return_value={'passed':True}))
        self.stack.enter_context(patch('app.autopilot.report_summary'))

    def result(self,body):
        return {'video_id':'video123456','url':'https://www.youtube.com/watch?v=video123456',
            'title':'Test','status':copy.deepcopy(body['status']),'schedule_verified':True,
            'channel_id':'authorized','public_verified':False}

    def test_verified_schedule_is_journaled_once_and_hour_is_not_repeated(self):
        self.publisher.upload.side_effect=lambda video,body,notify:self.result(body)
        report=autopilot.run_batch('production')
        self.assertEqual(report['status'],'complete')
        self.assertEqual(len(report['published']),1)
        entry=self.state['history'][0]
        self.assertEqual(entry['status'],'scheduled');self.assertTrue(entry['schedule_verified'])
        self.assertIn('publishAt',self.publisher.upload.call_args.args[1]['status'])
        self.assertEqual(self.state['pending'],[])
        autopilot.run_batch('production')
        self.publisher.upload.assert_called_once()

    def test_uncertain_upload_blocks_every_new_insert_until_read_only_reconciliation(self):
        self.publisher.upload.side_effect=RuntimeError('timeout')
        with self.assertRaisesRegex(RuntimeError,'no se ha confirmado'):autopilot.run_batch('production')
        self.assertEqual(self.state['history'][0]['status'],'uncertain')
        self.assertIn('publication_hold',self.state)
        with self.assertRaisesRegex(RuntimeError,'Publicación bloqueada'):
            autopilot.run_batch('production')
        self.assertEqual(self.publisher.upload.call_count,1)
        entry=self.state['history'][0]
        recovered=self.result({'status':{'privacyStatus':'private','publishAt':entry['publish_at']}})
        self.publisher.inspect_upload.return_value={**recovered,'found':True}
        report=autopilot.run_batch('production')
        self.assertEqual(entry['status'],'scheduled');self.assertNotIn('publication_hold',self.state)
        self.assertEqual(self.state['pending'],[]);self.assertEqual(self.publisher.upload.call_count,1)

    def test_existing_private_test_is_not_uploaded_in_production(self):
        self.state['history']=[{'key':self.key,'status':'private_test','video_id':'already-made'}]
        report=autopilot.run_batch('production')
        self.publisher.upload.assert_not_called();self.render.assert_not_called()
        self.assertEqual(report['status'],'waiting_for_research')

    def test_remote_duplicate_stops_before_reserving_attempt(self):
        self.publisher.inspect_upload.return_value={'found':True}
        report=autopilot.run_batch('production')
        self.assertEqual(report['status'],'publication_needs_review')
        self.publisher.upload.assert_not_called();self.assertEqual(self.state['attempts'],{})

    def test_delayed_youtube_verification_never_repeats_the_upload(self):
        self.publisher.upload.side_effect=BridgeError('UNVERIFIED_UPLOAD')
        recovered={'found':True,'video_id':'CaYx-v8uEAQ','url':'https://www.youtube.com/watch?v=CaYx-v8uEAQ',
            'title':'Verificado','status':{'privacyStatus':'private'},
            'schedule_verified':True,'public_verified':False,'channel_id':'authorized'}
        self.publisher.inspect_upload.side_effect=[{'found':False},recovered]
        with patch('app.autopilot.time.sleep') as sleeper:
            report=autopilot.run_batch('production')
        self.assertEqual(report['status'],'complete')
        self.assertEqual(report['published'][0]['video_id'],'CaYx-v8uEAQ')
        self.publisher.upload.assert_called_once()
        self.assertEqual(self.publisher.inspect_upload.call_count,2)
        sleeper.assert_not_called()
        self.assertNotIn('publication_hold',self.state)

    def test_unverified_bridge_stays_blocked_after_read_only_attempts(self):
        self.publisher.upload.side_effect=BridgeError('UNVERIFIED_UPLOAD')
        with patch('app.autopilot.time.sleep') as sleeper:
            with self.assertRaisesRegex(RuntimeError,'no se ha confirmado'):
                autopilot.run_batch('production')
        self.publisher.upload.assert_called_once()
        self.assertEqual(self.publisher.inspect_upload.call_count,5)
        self.assertEqual(sleeper.call_count,3)
        self.assertEqual(self.state['history'][0]['status'],'uncertain')
        self.assertIn('publication_hold',self.state)

    def test_bridge_daily_limit_is_safe_to_retry_after_reset(self):
        self.publisher.upload.side_effect=BridgeError('DAILY_UPLOAD_LIMIT')
        report=autopilot.run_batch('production')
        self.assertEqual(report['status'],'quota_wait')
        self.assertEqual(self.state['history'][0]['status'],'rejected_before_upload')
        self.assertTrue(self.state['history'][0]['reconciliation']['confirmed_no_upload'])
        self.assertEqual(len(self.state['pending']),1)
        self.assertNotIn('publication_hold',self.state)
        self.assertIn('quota_block_until',self.state)
        self.publisher.upload.assert_called_once()

    def test_bad_render_is_quarantined_but_next_topic_is_published(self):
        # Un tema imposible no puede parar el resto de los cinco Shorts.
        first=copy.deepcopy(self.topic)
        first['queue_key']=signature(first)
        first['queued_at']=self.now.isoformat()
        second=copy.deepcopy(first)
        second['id']='other-valid-topic'
        second['editorial']['facts']=['Dato verificado distinto para prueba']
        second['queue_key']=signature(second)
        self.state['pending']=[first,second]
        self.publisher.upload.side_effect=lambda video,body,notify:self.result(body)
        self.render.side_effect=[ValueError('Bloque demasiado breve para un plano sostenido'),self.video]
        with patch('app.autopilot.ingest',return_value=[]):
            report=autopilot.run_batch('production')
        self.assertEqual(report['status'],'complete')
        self.assertEqual(len(report['published']),1)
        self.assertEqual(report['skipped'][0]['id'],first['id'])
        self.assertIn(first['queue_key'],self.state['render_failures'])
        self.assertEqual(self.state['pending'],[first])
        self.publisher.upload.assert_called_once()
        self.assertEqual(len(self.state['history']),1)

    def test_quality_failure_never_attempts_upload(self):
        with patch('app.autopilot.inspect',return_value={'passed':False}):
            with self.assertRaisesRegex(RuntimeError,'calidad'):autopilot.run_batch('production')
        self.publisher.upload.assert_not_called();self.assertEqual(self.state['history'],[])

    def test_due_publication_is_verified_without_another_insert(self):
        record={'key':self.key,'status':'scheduled','publish_at':(self.now-dt.timedelta(minutes=2)).isoformat()}
        self.state['history']=[record]
        self.publisher.inspect_upload.return_value={'found':True,'video_id':'video123456','url':'https://www.youtube.com/watch?v=video123456',
            'status':{'privacyStatus':'public'},'schedule_verified':True,'public_verified':True,'channel_id':'authorized'}
        autopilot.run_batch('production')
        self.assertEqual(record['status'],'published');self.assertTrue(record['public_verified'])
        self.publisher.upload.assert_not_called()
