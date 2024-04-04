import binascii
import unittest
from datetime import datetime
from smarthubp.time_utils import timestamp_from_encoded


class TestTimestampFromEncoded(unittest.TestCase):
    def test_valid_inputs(self):
        test_cases = [
            ('VdPMRgA', datetime(2016, 9, 21, 19, 0)),
            ('Xuo9HwA', datetime(2021, 9, 2, 19, 0)),
            ('YGoQF$A', datetime(2022, 6, 27, 22, 0)),  # Special Character test: $
            ('YGou_gg', datetime(2022, 6, 28, 0, 15)),  # Special Character test: _
            ('ZQjBkEA', datetime(2025, 1, 1, 12, 0)),
            ('3hvvMEA', datetime(2090, 12, 1, 4, 0)),  # Arbitrary far future date.
        ]
        for encoded, expected in test_cases:
            with self.subTest(encoded=encoded):
                result = timestamp_from_encoded(encoded)
                self.assertEqual(result, expected)

    def test_invalid_inputs(self):
        """ Test various invalid inputs.
            The base64 decoder can be used to create an arbitrarily high timestamp value.
            In this case an overflow error is expected from the datetime class.
            The base64 decoder only except characters within the defined range.
            The base64 encoded string must not be one more than a multiple of 4 characters.
        """
        test_cases = [
            ('invalid_string', OverflowError),
            ('invalid_input', binascii.Error),
            ('a', binascii.Error),
        ]

        for encoded, expected_error in test_cases:
            print(encoded)
            with self.assertRaises(expected_error):
                timestamp_from_encoded(encoded)


if __name__ == '__main__':
    unittest.main()
