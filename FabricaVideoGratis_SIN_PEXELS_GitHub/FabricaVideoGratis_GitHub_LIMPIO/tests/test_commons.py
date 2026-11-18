"""No aceptar CC BY-SA/NC/ND al buscar únicamente CC BY, CC0 o dominio público."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import pipeline


class CommonsTests(unittest.TestCase):
    def setUp(self):
        sleeper = patch.object(pipeline.time, 'sleep')
        sleeper.start()
        self.addCleanup(sleeper.stop)

    @patch.object(pipeline.requests, 'get')
    def test_excludes_restricted_cc_variants(self, get):
        licenses = ['CC BY 4.0', 'CC BY-SA 4.0', 'CC BY-NC 4.0',
                    'CC BY-ND 4.0', 'CC0', 'Public domain']
        pages = [{'pageid': i, 'title': f'File:{i}.jpg', 'imageinfo': [{
            'mime': 'image/jpeg', 'width': 1200, 'height': 800,
            'url': f'https://upload.wikimedia.org/{i}.jpg',
            'thumburl': f'https://upload.wikimedia.org/thumb/{i}.jpg',
            'extmetadata': {'LicenseShortName': {'value': lic}}
        }]} for i, lic in enumerate(licenses)]
        get.return_value = Mock(json=Mock(return_value={'query': {'pages': pages}}))
        self.assertEqual([r['license'] for r in pipeline.commons_search('phone')],
                         ['CC BY 4.0', 'CC0', 'Public domain'])

    def test_plain_url_metadata_has_no_parser_warning(self):
        self.assertEqual(pipeline.clean_metadata('https://example.org/license'),
                         'https://example.org/license')
        self.assertEqual(pipeline.clean_metadata('<b>Ana &amp; Luis</b>'), 'Ana & Luis')

    def test_only_official_https_media_hosts(self):
        self.assertTrue(pipeline.commons_media_url('https://thumb.wikimedia.org/a.jpg'))
        self.assertTrue(pipeline.commons_media_url('https://upload.wikimedia.org/a.jpg'))
        self.assertFalse(pipeline.commons_media_url('http://thumb.wikimedia.org/a.jpg'))
        self.assertFalse(pipeline.commons_media_url('https://thumb.wikimedia.org.evil.test/a.jpg'))

    @patch.object(pipeline.requests, 'get')
    def test_rate_limit_stops_after_one_retry(self, get):
        get.return_value = Mock(status_code=429, headers={'Retry-After': '10'})
        with self.assertRaises(pipeline.CommonsRateLimit):
            pipeline.commons_get('https://thumb.wikimedia.org/a.jpg')
        self.assertEqual(get.call_count, 2)

    @patch.object(pipeline.requests, 'get')
    def test_long_retry_after_stops_without_extra_request(self, get):
        get.return_value = Mock(status_code=429, headers={'Retry-After': '120'})
        with self.assertRaisesRegex(pipeline.CommonsRateLimit, '120 s'):
            pipeline.commons_get('https://thumb.wikimedia.org/a.jpg')
        self.assertEqual(get.call_count, 1)

    @patch.object(pipeline, 'commons_get')
    def test_interrupted_download_does_not_cache_partial_file(self, get):
        response = Mock()
        response.iter_content.side_effect = pipeline.requests.ConnectionError('interrumpido')
        context = Mock()
        context.__enter__ = Mock(return_value=response)
        context.__exit__ = Mock(return_value=False)
        get.return_value = context
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            with self.assertRaises(pipeline.requests.ConnectionError):
                pipeline.download_commons({'kind':'image','id':'42',
                    'url':'https://thumb.wikimedia.org/a.jpg'},folder)
            self.assertEqual(list(folder.iterdir()), [])

    @patch.object(pipeline, 'download_commons')
    @patch.object(pipeline, 'commons_search')
    def test_cached_reuse_allows_more_sections_without_repeating_search(self, search, download):
        search.return_value = [{'id':str(i),'kind':'image','artist':'Ana',
            'page_url':f'https://commons.wikimedia.org/wiki/File:{i}.jpg',
            'license':'CC0','license_url':''} for i in range(3)]
        download.side_effect = lambda clip, folder: folder / (clip['id']+'.jpg')
        plan={'title':'iPhone', 'sections':[{'stock_query':'iPhone'} for _ in range(12)]}
        with tempfile.TemporaryDirectory() as tmp:
            result=pipeline.get_stock(plan,Path(tmp))
            self.assertEqual(len(result),12)
            self.assertTrue(all(len(set(section)) == 3 for section in result))
            self.assertEqual(search.call_count,1)


if __name__ == '__main__':
    unittest.main()
