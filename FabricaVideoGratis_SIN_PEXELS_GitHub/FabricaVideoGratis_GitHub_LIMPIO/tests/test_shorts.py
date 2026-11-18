import unittest
from app.shorts import valid_media_url, caption_chunks, wrap, fit, ass_time, TRAILER

class ShortsTests(unittest.TestCase):
    def test_media_source_is_exact_official_host(self):
        self.assertTrue(valid_media_url(TRAILER))
        for bad in ['http://media-rockstargames-com.akamaized.net/VI/downloads/videos/a.mp4',
                    'https://media-rockstargames-com.akamaized.net.evil.example/VI/downloads/videos/a.mp4',
                    'https://youtube.com/watch?v=123']:
            self.assertFalse(valid_media_url(bad))

    def test_long_titles_are_preserved_inside_frame(self):
        title='Guía práctica Siete comprobaciones para comprar un iPhone usado'
        size,lines=fit(title)
        self.assertEqual(' '.join(lines),title)
        self.assertLessEqual(len(lines),3)
        for line in lines:self.assertLessEqual(__import__('app.shorts',fromlist=['font']).font(size).getlength(line),880)

    def test_captions_keep_all_words_and_fit_safe_area(self):
        sentence='El tráiler espectacular no confirma automáticamente cuántos fotogramas tendrá tu partida.'
        chunks=caption_chunks(sentence)
        self.assertEqual(' '.join(chunks),sentence)
        for chunk in chunks:
            self.assertLessEqual(len(chunk.split()),4)
            self.assertLessEqual(len(wrap(chunk,66,840)),2)

    def test_ass_clock_carries_seconds(self):
        self.assertEqual(ass_time(59.999),'0:01:00.00')
