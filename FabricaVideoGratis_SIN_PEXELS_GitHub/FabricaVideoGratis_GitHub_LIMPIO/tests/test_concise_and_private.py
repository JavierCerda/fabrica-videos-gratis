import copy
import datetime as dt
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
from app.pipeline import ROOT
from app.editorial_queue import validate_topic,ingest,signature,select_pending
from app.smooth_media import plan_shots
from app.autopilot import run_batch
from app.youtube_publisher import seo,YouTubePublisher


class ConciseTests(unittest.TestCase):
    def setUp(self):
        self.packet=json.loads((ROOT/'tests/fixtures/informativo_packet.json').read_text())
        self.topic=copy.deepcopy(self.packet['topics'][0])
        self.now=dt.datetime.fromisoformat(self.packet['generated_at'])
        self.config=json.loads((ROOT/'config/automation.json').read_text())

    def test_short_factual_script_needs_no_jokes_or_profanity(self):
        self.assertEqual(validate_topic(self.topic,self.now,self.config),self.topic)
        self.assertEqual(self.topic['editorial']['jokes'],[])

    def test_revision_keeps_fact_id_and_original_queue_position(self):
        key=signature(self.topic)
        old={**self.topic,'editorial_version':2,'queue_key':key,'queued_at':'2026-11-18T10:00:00Z'}
        state={'pending':[copy.deepcopy(old)],'history':[]}
        self.assertEqual(select_pending(state,self.now,self.config),[])
        result=ingest(state,self.packet,self.now,self.config)
        self.assertEqual(result[0]['status'],'revised')
        self.assertEqual(len(state['pending']),1)
        self.assertEqual(state['pending'][0]['id'],old['id'])
        self.assertEqual(state['pending'][0]['editorial']['facts'],old['editorial']['facts'])
        self.assertEqual(state['pending'][0]['queued_at'],old['queued_at'])
        state={'pending':[copy.deepcopy(old)],'history':[{'key':key,'status':'uncertain'}]}
        self.assertEqual(ingest(state,self.packet,self.now,self.config)[0]['status'],'duplicate')
        wrong=copy.deepcopy(self.packet);wrong['topics'][0]['id']='different-editorial-id'
        state={'pending':[old],'history':[]}
        self.assertEqual(ingest(state,wrong,self.now,self.config)[0]['status'],'rejected')

    def test_image_cannot_return_later_even_under_another_crop(self):
        a,b,c=[copy.deepcopy(x['visuals'][0]) for x in self.topic['beats']]
        self.topic['beats']=[{'visuals':[a]},{'visuals':[b]},{'visuals':[c]},
            {'visuals':[{**a,'source_crop':[0,0,900,900]}]}]
        with patch('app.smooth_media.duration',return_value=5):
            with self.assertRaisesRegex(ValueError,'sin repetir'):
                plan_shots(self.topic,[Path(str(i)) for i in range(4)])

    def test_only_related_unused_alternatives_are_selected(self):
        a,b,c=[copy.deepcopy(x['visuals'][0]) for x in self.topic['beats']]
        self.topic['beats']=[{'visuals':[a]},{'visuals':[b]},{'visuals':[a,c]}]
        with patch('app.smooth_media.duration',return_value=5):shots=plan_shots(self.topic,[Path('a'),Path('b'),Path('c')])
        self.assertEqual([s['visual']['index'] for s in shots],[a['index'],b['index'],c['index']])
        self.assertEqual(sum(s['frames'] for s in shots),450)

    def test_overlapping_video_fragments_are_rejected(self):
        clip={'game':'gta6','index':-1,'kind':'video','max_seconds':5}
        self.topic['beats']=[{'visuals':[{**clip,'start':s}]} for s in (1,2,20)]
        with patch('app.smooth_media.duration',return_value=4):
            with self.assertRaisesRegex(ValueError,'sin repetir'):
                plan_shots(self.topic,[Path('a'),Path('b'),Path('c')])
        self.topic['beats']=[{'visuals':[{**clip,'start':s}]} for s in (1,10,20)]
        with patch('app.smooth_media.duration',return_value=4):shots=plan_shots(self.topic,[Path('a'),Path('b'),Path('c')])
        self.assertEqual(len(shots),3)

    def test_private_test_body_has_no_public_schedule(self):
        body=seo(self.topic,signature(self.topic),None,self.config)
        self.assertEqual(body['status']['privacyStatus'],'private')
        self.assertNotIn('publishAt',body['status'])

    def test_private_confirmation_depends_on_youtube_response(self):
        client=Mock();client.channels.return_value.list.return_value.execute.return_value={'items':[{'id':'channel'}]}
        client.videos.return_value.insert.return_value.next_chunk.return_value=(None,{'id':'video'})
        body=seo(self.topic,signature(self.topic),None,self.config)
        with tempfile.TemporaryDirectory() as temp,patch.dict(os.environ,{'YT_CHANNEL_ID':'channel'}):
            video=Path(temp)/'video.mp4';video.write_bytes(b'placeholder')
            publisher=YouTubePublisher(client)
            for actual,verified in [('private',True),('public',False)]:
                client.videos.return_value.list.return_value.execute.return_value={
                    'items':[{'status':{'privacyStatus':actual},'snippet':{'title':'Prueba'}}]}
                result=publisher.upload(video,body,notify=False)
                self.assertEqual(result['private_verified'],verified)
                self.assertFalse(result['schedule_verified'])

    def private_run(self,ready=True,quality=True,upload_error=False):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);root=Path(temp.name)
        (root/'config').mkdir();(root/'topics').mkdir()
        (root/'config/automation.json').write_text(json.dumps(self.config))
        (root/'topics/inbox.json').write_text(json.dumps(self.packet))
        video=root/'output/topic/short_vertical.mp4';video.parent.mkdir(parents=True)
        state={'pending':[],'history':[],'attempts':{}}
        publisher=Mock();publisher.recent_markers.return_value={}
        publisher.upload.return_value={'video_id':'verified-private-id','url':'https://www.youtube.com/watch?v=verified-private-id',
            'title':self.topic['title'],'private_verified':True,'schedule_verified':False}
        if upload_error:publisher.upload.side_effect=RuntimeError('interrupted')
        now=self.now
        class Clock(dt.datetime):
            @classmethod
            def now(cls,tz=None):return now.astimezone(tz or dt.timezone.utc)
        context=patch.multiple('app.autopilot',ROOT=root,OUT=root/'output')
        return context,patch('app.autopilot.dt.datetime',Clock),patch('app.autopilot.StateStore'),\
            patch('app.autopilot.YouTubePublisher',return_value=publisher),\
            patch('app.autopilot.produce',return_value=video),patch('app.autopilot.inspect',return_value={'passed':quality}),\
            patch('app.autopilot.report_summary'),patch('app.autopilot.readiness',return_value={'ready':ready,'missing':[] if ready else ['YT_REFRESH_TOKEN']}),state,publisher

    def test_missing_oauth_still_generates_preview_without_uploading(self):
        a,b,c,d,e,f,g,h,state,publisher=self.private_run(ready=False)
        with a,b,c as store,d as factory,e as produce,f,g,h:
            store.return_value.load.return_value=state
            report=run_batch('upload-test')
            self.assertEqual(report['status'],'connection_required')
            self.assertEqual(report['published'],[]);self.assertEqual(report['test_uploads'],[])
            produce.assert_called_once();factory.assert_not_called();publisher.upload.assert_not_called()
            self.assertFalse(self.config['publication_enabled']);self.assertEqual(state['attempts'],{})

    def test_verified_private_upload_is_journaled_once_without_activating_publication(self):
        a,b,c,d,e,f,g,h,state,publisher=self.private_run()
        with a,b,c as store,d,e,f,g,h:
            store.return_value.load.return_value=state
            report=run_batch('upload-test')
            self.assertEqual(report['status'],'private_test_complete')
            body=publisher.upload.call_args.args[1]
            self.assertNotIn('publishAt',body['status']);self.assertEqual(body['status']['privacyStatus'],'private')
            self.assertFalse(publisher.upload.call_args.kwargs['notify'])
            self.assertEqual(state['history'][0]['status'],'private_test')
            self.assertEqual(state['history'][0]['video_id'],'verified-private-id')
            self.assertEqual(report['published'],[]);self.assertEqual(len(report['test_uploads']),1)
            run_batch('upload-test');self.assertEqual(publisher.upload.call_count,1)
            self.assertFalse(self.config['publication_enabled'])

    def test_failed_quality_never_uploads_and_interrupted_upload_is_not_repeated(self):
        a,b,c,d,e,f,g,h,state,publisher=self.private_run(quality=False)
        with a,b,c as store,d,e,f,g,h:
            store.return_value.load.return_value=state
            with self.assertRaisesRegex(RuntimeError,'calidad'):run_batch('upload-test')
            publisher.upload.assert_not_called();self.assertEqual(state['history'],[])
        a,b,c,d,e,f,g,h,state,publisher=self.private_run(upload_error=True)
        with a,b,c as store,d,e,f,g,h:
            store.return_value.load.return_value=state
            with self.assertRaisesRegex(RuntimeError,'no se repetirá'):run_batch('upload-test')
            self.assertEqual(state['history'][0]['status'],'uncertain')
            run_batch('upload-test');self.assertEqual(publisher.upload.call_count,1)
