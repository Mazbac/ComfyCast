import tempfile
import unittest
from pathlib import Path
from urllib.request import Request, urlopen

import comfycast.media_server as media_server


class MediaServerTests(unittest.TestCase):
    def setUp(self):
        handle = tempfile.NamedTemporaryFile(delete=False, suffix=".bin")
        handle.write(b"0123456789")
        handle.close()
        self.path = Path(handle.name)
        self.server = media_server.LocalMediaServer()
        self.original_get_lan_ip = media_server.get_lan_ip
        media_server.get_lan_ip = lambda: "127.0.0.1"

    def tearDown(self):
        self.server.stop()
        media_server.get_lan_ip = self.original_get_lan_ip
        self.path.unlink(missing_ok=True)

    def test_full_file_and_head(self):
        url = self.server.publish(self.path, "application/octet-stream")
        with urlopen(url, timeout=3) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.read(), b"0123456789")
            self.assertEqual(response.headers["Accept-Ranges"], "bytes")

        request = Request(url, method="HEAD")
        with urlopen(request, timeout=3) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.headers["Content-Length"], "10")
            self.assertEqual(response.read(), b"")

    def test_byte_range(self):
        url = self.server.publish(self.path, "application/octet-stream")
        request = Request(url, headers={"Range": "bytes=2-5"})
        with urlopen(request, timeout=3) as response:
            self.assertEqual(response.status, 206)
            self.assertEqual(response.read(), b"2345")
            self.assertEqual(response.headers["Content-Range"], "bytes 2-5/10")

    def test_parse_range(self):
        self.assertEqual(media_server._parse_range("bytes=3-", 10), (3, 9))
        self.assertEqual(media_server._parse_range("bytes=-3", 10), (7, 9))
        self.assertIsNone(media_server._parse_range("", 10))
        with self.assertRaises(ValueError):
            media_server._parse_range("bytes=99-100", 10)


if __name__ == "__main__":
    unittest.main()
