import shutil
import subprocess
import unittest
from pathlib import Path


class AppsScriptBridgeTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node necesario para verificar el puente de Google')
    def test_authentication_and_upload_safety(self):
        root = Path(__file__).resolve().parents[1]
        subprocess.run(['node', str(root/'tests/test_apps_script_bridge.cjs'),
                        str(root/'integrations/apps-script/Code.gs')], check=True, capture_output=True, text=True)
