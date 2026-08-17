import unittest
from unittest.mock import MagicMock, patch

from comfycast.cast_service import CastError, _build_load_message, _load_with_retry


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


class CastRetryTests(unittest.TestCase):
    @patch("comfycast.cast_service.time.sleep", return_value=None)
    @patch("comfycast.cast_service._wait_for_media")
    @patch("comfycast.cast_service._send_load")
    def test_transient_idle_retries_once(self, send_load, wait_for_media, _sleep):
        cast = MagicMock()
        cast.media_controller.status.player_state = "IDLE"
        cast.media_controller.status.idle_reason = None
        cast.media_controller.status.media_session_id = 1
        cast.media_controller.status.content_id = "http://example.test/video.mp4"
        wait_for_media.side_effect = [CastError("idle"), "PLAYING"]

        result = _load_with_retry(
            cast,
            "http://example.test/video.mp4",
            "video/mp4",
            title="Example",
            autoplay=True,
            loop=True,
        )

        self.assertEqual(result, "PLAYING")
        self.assertEqual(send_load.call_count, 2)
        self.assertEqual(wait_for_media.call_count, 2)
        cast.media_controller.update_status.assert_called_once()

    @patch("comfycast.cast_service.time.sleep", return_value=None)
    @patch("comfycast.cast_service._wait_for_media")
    @patch("comfycast.cast_service._send_load")
    def test_second_failure_is_reported(self, send_load, wait_for_media, _sleep):
        cast = MagicMock()
        cast.media_controller.status.player_state = "IDLE"
        cast.media_controller.status.idle_reason = "ERROR"
        wait_for_media.side_effect = [CastError("first"), CastError("second")]

        with self.assertRaisesRegex(CastError, "second"):
            _load_with_retry(
                cast,
                "http://example.test/video.mp4",
                "video/mp4",
                title="Example",
                autoplay=True,
                loop=False,
            )
        self.assertEqual(send_load.call_count, 2)


if __name__ == "__main__":
    unittest.main()
