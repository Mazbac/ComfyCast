import os
import unittest
from unittest.mock import patch

from comfycast.discovery import DiscoveryError, configured_known_hosts


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


if __name__ == "__main__":
    unittest.main()
