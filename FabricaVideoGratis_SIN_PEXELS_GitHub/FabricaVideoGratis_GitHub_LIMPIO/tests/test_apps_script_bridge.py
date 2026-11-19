import shutil
import subprocess
import unittest
import base64
import hashlib
import hmac
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from app.youtube_bridge import AppsScriptPublisher, BridgeError
from app.youtube_publisher import YouTubePublisher, readiness


class AppsScriptBridgeTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node necesario para verificar el puente de Google')
    def test_authentication_and_upload_safety(self):
        root = Path(__file__).resolve().parents[1]
        subprocess.run(['node', str(root/'tests/test_apps_script_bridge.cjs'),
                        str(root/'integrations/apps-script/Code.gs')], check=True, capture_output=True, text=True)


class BridgeTransportTests(unittest.TestCase):
    def setUp(self):
        self.channel = 'UCuMX_olnpHMCr06FQBdCzjQ'
        self.env = {'YT_BRIDGE_URL':'https://script.google.com/macros/s/test/exec',
                    'YT_BRIDGE_KEY':'a'*64, 'YT_CHANNEL_ID':self.channel}
        self.session=Mock()
        self.ready={'channel_id':self.channel,'title':'JMDopamine','private_test_only':True}
        self.session.post.return_value=self.response(self.ready)

    def response(self,result):
        response=Mock(status_code=200,headers={})
        response.json.return_value={'ok':True,'result':result}
        return response

    def test_signed_request_and_unexpected_redirect_do_not_leak_credentials(self):
        with patch.dict(os.environ,self.env):publisher=AppsScriptPublisher(self.session)
        envelope=self.session.post.call_args.kwargs['json']
        signature=base64.urlsafe_b64encode(hmac.new(b'a'*64,envelope['payload'].encode(),hashlib.sha256).digest()).decode().rstrip('=')
        self.assertEqual(envelope['signature'],signature)
        self.assertEqual(json.loads(envelope['payload'])['channel_id'],self.channel)
        response=Mock(status_code=302,headers={'Location':'https://evil.example/steal'})
        self.session.post.return_value=response
        with self.assertRaisesRegex(BridgeError,'UNEXPECTED_REDIRECT'):publisher.recent_markers()
        self.session.get.assert_not_called()

    def test_content_service_redirect_uses_get_without_signed_body(self):
        redirect=Mock(status_code=302,headers={'Location':'https://script.googleusercontent.com/macros/echo?test=1'})
        self.session.post.return_value=redirect;self.session.get.return_value=self.response(self.ready)
        with patch.dict(os.environ,self.env):AppsScriptPublisher(self.session)
        self.assertNotIn('json',self.session.get.call_args.kwargs)
        self.assertEqual(self.session.post.call_count,1)

    def test_network_errors_are_redacted_and_not_retried(self):
        self.session.post.side_effect=RuntimeError('DO_NOT_SHOW_KEY_OR_URL')
        with patch.dict(os.environ,self.env):
            with self.assertRaises(BridgeError) as caught:AppsScriptPublisher(self.session)
        self.assertNotIn('DO_NOT_SHOW',str(caught.exception))
        self.assertEqual(self.session.post.call_count,1)

    def test_wrong_channel_and_public_upload_are_rejected(self):
        with patch.dict(os.environ,self.env):publisher=AppsScriptPublisher(self.session)
        with self.assertRaisesRegex(RuntimeError,'privadas'):
            publisher.upload('not-opened.mp4',{'status':{'privacyStatus':'private','publishAt':'2026-11-20T00:00:00Z'}})
        self.assertEqual(self.session.post.call_count,1)
        self.session.post.return_value=self.response({**self.ready,'channel_id':'wrong'})
        with patch.dict(os.environ,self.env):
            with self.assertRaisesRegex(RuntimeError,'no coinciden'):AppsScriptPublisher(self.session)

    def test_private_confirmation_requires_real_status_and_valid_id(self):
        with patch.dict(os.environ,self.env):publisher=AppsScriptPublisher(self.session)
        body={'snippet':{'tags':['fvg-'+'b'*24]},'status':{'privacyStatus':'private'}}
        with tempfile.TemporaryDirectory() as temp:
            video=Path(temp)/'test.mp4';video.write_bytes(b'\x00\x00\x00\x10ftyp0000')
            self.session.post.return_value=self.response({'video_id':'XTxEf6oC8Og','private_verified':True,
                'status':{'privacyStatus':'public'},'url':'https://evil.example'})
            with self.assertRaisesRegex(BridgeError,'UNVERIFIED_PRIVACY'):publisher.upload(video,body)
            self.session.post.return_value=self.response({'video_id':'XTxEf6oC8Og','private_verified':True,
                'status':{'privacyStatus':'private'},'url':'https://evil.example'})
            result=publisher.upload(video,body)
            self.assertEqual(result['url'],'https://www.youtube.com/watch?v=XTxEf6oC8Og')
            self.assertFalse(result['schedule_verified'])

    def test_optional_backend_does_not_replace_oauth_without_bridge_configuration(self):
        with patch.dict(os.environ,self.env),patch('app.youtube_bridge.AppsScriptPublisher',return_value='bridge'):
            self.assertEqual(YouTubePublisher(),'bridge')
            self.assertTrue(readiness()['private_test_only'])
        with patch.dict(os.environ,{'YT_BRIDGE_URL':'','YT_BRIDGE_KEY':''}):
            self.assertNotIn('private_test_only',readiness())

    def test_production_stops_before_rendering_or_reserving_uploads(self):
        from app import autopilot
        publisher=Mock(private_test_only=True)
        state={'pending':[],'history':[],'attempts':{}}
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'config').mkdir();(root/'topics').mkdir()
            (root/'config/automation.json').write_text(json.dumps({'publication_enabled':True,'state_branch':'test'}))
            (root/'topics/inbox.json').write_text('{}')
            with patch.object(autopilot,'ROOT',root),patch.object(autopilot,'OUT',root/'output'),\
                patch.object(autopilot,'StateStore') as store,patch.object(autopilot,'ingest',return_value=[]),\
                patch.object(autopilot,'select_pending',return_value=[]),\
                patch.object(autopilot,'readiness',return_value={'ready':True,'missing':[]}),\
                patch.object(autopilot,'YouTubePublisher',return_value=publisher),\
                patch.object(autopilot,'produce') as produce,patch.object(autopilot,'next_slot') as slot:
                store.return_value.load.return_value=state
                report=autopilot.run_batch('production')
                self.assertEqual(report['status'],'private_connection_only')
                produce.assert_not_called();slot.assert_not_called();publisher.upload.assert_not_called()
                self.assertEqual(state['attempts'],{});self.assertEqual(state['history'],[])

    def test_bridge_uses_pinned_channel_without_an_actions_variable(self):
        with patch.dict(os.environ, {**self.env, 'YT_CHANNEL_ID':''}):
            self.assertTrue(readiness()['ready'])
            publisher=AppsScriptPublisher(self.session)
        self.assertEqual(publisher.channel_id,self.channel)
        self.assertEqual(json.loads(self.session.post.call_args.kwargs['json']['payload'])['channel_id'],self.channel)
        self.session.post.reset_mock()
        with patch.dict(os.environ,{**self.env,'YT_CHANNEL_ID':'different-channel'}):
            with self.assertRaisesRegex(RuntimeError,'no coincide'):AppsScriptPublisher(self.session)
        self.session.post.assert_not_called()
