import unittest

from comfycast.cast_service import _build_load_message


class CastLoadMessageTests(unittest.TestCase):
    def test_regular_load_has_no_queue(self):
        message = _build_load_message(
            "http://example.test/video.mp4",
            "video/mp4",
            title="Example",
            autoplay=True,
            loop=False,
        )
        self.assertEqual(message["type"], "LOAD")
        self.assertNotIn("queueData", message)
        self.assertTrue(message["autoplay"])

    def test_loop_uses_native_repeat_single_queue(self):
        url = "http://example.test/video.mp4"
        message = _build_load_message(
            url,
            "video/mp4",
            title="Loop me",
            autoplay=True,
            loop=True,
        )
        queue = message["queueData"]
        self.assertEqual(queue["repeatMode"], "REPEAT_SINGLE")
        self.assertEqual(queue["startIndex"], 0)
        self.assertEqual(queue["items"][0]["media"]["contentId"], url)
        self.assertTrue(queue["items"][0]["autoplay"])


if __name__ == "__main__":
    unittest.main()
