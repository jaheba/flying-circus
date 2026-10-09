import unittest

from flying_circus.formatting import milliseconds


class TimingFormatTests(unittest.TestCase):
    def test_submillisecond_values_never_round_to_zero(self):
        for value in (0.12, 0.004, 0.0000001):
            self.assertGreater(float(milliseconds(value)), 0)
        self.assertEqual(milliseconds(12.345), '12')
        self.assertEqual(milliseconds(0.12345), '0.12')
        self.assertEqual(milliseconds(None), 'n/a')
