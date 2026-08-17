import os
import unittest
from unittest.mock import patch

from comfycast.network import _common_prefix_bits, _is_lan_ipv4, get_lan_ip


class NetworkTests(unittest.TestCase):
    def test_ipv4_filter(self):
        self.assertTrue(_is_lan_ipv4("192.168.2.10"))
        self.assertTrue(_is_lan_ipv4("10.0.0.5"))
        self.assertFalse(_is_lan_ipv4("127.0.0.1"))
        self.assertFalse(_is_lan_ipv4("169.254.1.1"))
        self.assertFalse(_is_lan_ipv4("0.0.0.0"))
        self.assertFalse(_is_lan_ipv4("not-an-ip"))

    def test_common_prefix(self):
        self.assertGreater(
            _common_prefix_bits("192.168.2.2", "192.168.2.12"),
            _common_prefix_bits("100.64.223.41", "192.168.2.12"),
        )

    @patch(
        "comfycast.network._local_ipv4_candidates",
        return_value=["100.64.223.41", "192.168.2.2"],
    )
    def test_target_prefers_physical_lan_over_vpn(self, _candidates):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("COMFYCAST_HOST_IP", None)
            self.assertEqual(get_lan_ip("192.168.2.12"), "192.168.2.2")


if __name__ == "__main__":
    unittest.main()
