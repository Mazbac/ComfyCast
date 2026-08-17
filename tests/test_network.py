import unittest

from comfycast.network import _is_lan_ipv4


class NetworkTests(unittest.TestCase):
    def test_ipv4_filter(self):
        self.assertTrue(_is_lan_ipv4("192.168.2.10"))
        self.assertTrue(_is_lan_ipv4("10.0.0.5"))
        self.assertFalse(_is_lan_ipv4("127.0.0.1"))
        self.assertFalse(_is_lan_ipv4("0.0.0.0"))
        self.assertFalse(_is_lan_ipv4("not-an-ip"))


if __name__ == "__main__":
    unittest.main()
