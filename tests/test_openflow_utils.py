import unittest

from openflow_utils import has_usable_buffer_id


class OpenFlowBufferTests(unittest.TestCase):
    NO_BUFFER = 0xFFFFFFFF

    def test_zero_is_a_valid_buffer_identifier(self):
        self.assertTrue(has_usable_buffer_id(0, self.NO_BUFFER))

    def test_no_buffer_sentinel_requires_packet_data(self):
        self.assertFalse(has_usable_buffer_id(self.NO_BUFFER, self.NO_BUFFER))

    def test_missing_buffer_identifier_requires_packet_data(self):
        self.assertFalse(has_usable_buffer_id(None, self.NO_BUFFER))


if __name__ == "__main__":
    unittest.main()
