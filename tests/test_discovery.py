import os
import unittest
from unittest.mock import patch

from comfycast.discovery import (
    CastDevice,
    DiscoveryError,
    DiscoveryService,
    configured_known_hosts,
)


class DiscoveryConfigTests(unittest.TestCase):
    def test_known_hosts_from_environment(self):
        with patch.dict(
            os.environ,
            {"COMFYCAST_KNOWN_HOSTS": "192.168.1.10, 192.168.1.11"},
            clear=False,
        ):
            self.assertEqual(
                configured_known_hosts(),
                ["192.168.1.10", "192.168.1.11"],
            )

    def test_invalid_known_host_is_rejected(self):
        with patch.dict(
            os.environ,
            {"COMFYCAST_KNOWN_HOSTS": "living-room.local"},
            clear=False,
        ):
            with self.assertRaises(DiscoveryError):
                configured_known_hosts()


class DiscoveryCacheTests(unittest.TestCase):
    def setUp(self):
        self.device = CastDevice(
            name="TV",
            host="192.168.1.20",
            port=8009,
            model="Model",
            uuid="11111111-1111-1111-1111-111111111111",
            cast_type="cast",
        )

    @patch("comfycast.discovery.discover_video_devices")
    def test_cached_list_avoids_repeated_scan(self, discover):
        discover.return_value = [self.device]
        service = DiscoveryService(ttl_seconds=60)
        first = service.list_devices()
        second = service.list_devices()
        self.assertEqual(first, second)
        self.assertEqual(discover.call_count, 1)

    @patch("comfycast.discovery.discover_video_devices")
    def test_cached_uuid_resolves_without_new_scan(self, discover):
        discover.return_value = [self.device]
        service = DiscoveryService(ttl_seconds=60)
        service.list_devices()
        resolved = service.resolve(self.device.uuid)
        self.assertEqual(resolved, self.device)
        self.assertEqual(discover.call_count, 1)

    @patch("comfycast.discovery.discover_video_devices")
    def test_direct_ip_resolution_is_cached(self, discover):
        discover.return_value = [self.device]
        service = DiscoveryService(ttl_seconds=60)
        first = service.resolve(self.device.host)
        second = service.resolve(self.device.host)
        self.assertEqual(first, self.device)
        self.assertEqual(second, self.device)
        self.assertEqual(discover.call_count, 1)

    @patch("comfycast.discovery.discover_video_devices")
    def test_friendly_label_resolves_after_scan(self, discover):
        discover.return_value = [self.device]
        service = DiscoveryService(ttl_seconds=60)
        resolved = service.resolve(self.device.label)
        self.assertEqual(resolved, self.device)
        self.assertEqual(discover.call_count, 1)


if __name__ == "__main__":
    unittest.main()
