import unittest
from unittest.mock import MagicMock, patch

from comfycast.discovery import CastDevice

from comfycast.cast_service import (
    CastError, PlaybackRecord, PlaybackRegistry, _build_load_message,
    _control_connected, _load_with_retry,
)


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


class PlaybackControlTests(unittest.TestCase):
    def setUp(self):
        self.device = CastDevice(
            name="TV", host="192.168.1.20", port=8009, model="Model",
            uuid="11111111-1111-1111-1111-111111111111", cast_type="cast",
        )
        self.video = PlaybackRecord("http://test/video.mp4", "video/mp4", "Video", True)
        self.image = PlaybackRecord("http://test/image.png", "image/png", "Image", False)

    def test_registry_remembers_last_media_per_device(self):
        registry = PlaybackRegistry()
        registry.remember(self.device, self.video)
        self.assertEqual(registry.get(self.device), self.video)

    @patch("comfycast.cast_service._wait_for_states", return_value="PAUSED")
    def test_pause_video(self, _wait):
        cast = MagicMock()
        cast.media_controller.status.content_id = self.video.media_url
        cast.media_controller.status.player_state = "PLAYING"
        result = _control_connected(cast, self.video, "pause")
        cast.media_controller.pause.assert_called_once()
        self.assertEqual(result["player_state"], "PAUSED")

    @patch("comfycast.cast_service._load_with_retry", return_value="PLAYING")
    def test_start_reloads_stopped_video(self, load):
        cast = MagicMock()
        cast.media_controller.status.content_id = self.video.media_url
        cast.media_controller.status.player_state = "IDLE"
        result = _control_connected(cast, self.video, "start")
        load.assert_called_once()
        self.assertEqual(result["player_state"], "PLAYING")

    def test_start_keeps_displayed_image(self):
        cast = MagicMock()
        cast.media_controller.status.content_id = self.image.media_url
        cast.media_controller.status.player_state = "PAUSED"
        result = _control_connected(cast, self.image, "start")
        cast.media_controller.play.assert_not_called()
        self.assertEqual(result["player_state"], "PAUSED")

    def test_end_cast_quits_default_receiver(self):
        cast = MagicMock()
        cast.app_id = "CC1AD845"
        result = _control_connected(cast, self.video, "end")
        cast.quit_app.assert_called_once_with(timeout=10)
        self.assertEqual(result["player_state"], "ENDED")


if __name__ == "__main__":
    unittest.main()
