import unittest
from datetime import datetime, timedelta
from random import randint, random
from unittest.mock import patch

from smarthubp.parse import _extract_meters, InvalidMetadata, _read_combined, UNEXPECTED_EXIT_COMBINED_LIST, \
    _get_list_readings
from smarthubp.time_utils import encoded_from_timestamp, set_import_time_offset, time_offset


class ExtractMetersCase(unittest.TestCase):
    def test_extract_meters(self):
        """ Test the typical meter patterns with skipped values included. Ensure that only the meters
            are extracted. """
        test_data = ['"pre"', '"list"', '"data"', 'not', '"counted"', '"including.things"', '"that#are ignored"',
                     'starthere', '"xxxx+1"', '"metername1"', '"class.name"', '"other-name"']
        end_data = ['"column"', 'endhere']
        # Base 1 meter after + pattern.
        meters = _extract_meters(test_data + end_data)
        self.assertEqual(meters, ['metername1'])

        # Second meter and third meter no intervening + entry.
        test_data += ['xxxx+2', '"metername2"', '"#FFEE32"', '"some.class.second"', '"metername3"',
                      '"some.class.third"']
        meters = _extract_meters(test_data + end_data)
        self.assertEqual(meters, ['metername1', 'metername2', 'metername3'])

        # Third and sub-meters.
        test_data += ["'xxxx+3'", '"metername4"', '"#COLOR"', '"metername4 - sub1"',
                      '"some.class"', '"metername4 - sub2"', '"metername4 - sub3"']
        meters = _extract_meters(test_data + end_data)
        self.assertEqual(meters, ['metername1', 'metername2', 'metername3',
                                  'metername4 - sub1', 'metername4 - sub2',
                                  'metername4 - sub3'])

    def test_no_end_marker(self):
        """ The csv metadata must contain a column entry.
            A metadata without this would need to be flagged for analysis and needs to fail.
        """
        test_data = ['"1234+1"', '"metername1"', '"net-meter-column"', '"some.class"']

        with self.assertRaises(InvalidMetadata):
            meters = _extract_meters(test_data)

    def test_no_start_marker(self):
        """ The csv metadata must contain an entry with + in it to mark the start of the meters.
            A metadata without this would need to be flagged for analysis and needs to fail.
        """
        test_data = ['"metername1"', '"column"', '"some.class.stuff"']

        with self.assertRaises(InvalidMetadata):
            meters = _extract_meters(test_data)


def _generate_entry(reading: float, timestamp: datetime):
    return [str(reading), '10', encoded_from_timestamp(timestamp), '9', '0', '0', '1', '0', '0', '8']


def _generate_reference(idx):
    """ Generate a reference into the combined list. """
    file_idx = (-idx * 3) - 7
    return [str(file_idx), str(file_idx - 1), '0', '0', '1', '0', '0', '8']


class CombinedListCase(unittest.TestCase):

    def test_combined_read(self):
        test_data = [(random(), datetime(2015, 3, 1, i)) for i in range(12, 20)]
        test_csv = ['13', '12', '11']
        for entry in test_data: test_csv += _generate_entry(entry[0], entry[1])

        result = _read_combined(test_csv)

        self.assertEqual(len(result), len(test_data))
        for reading, entry in zip(result, test_data):
            self.assertEqual(reading.kwh, entry[0])
            self.assertEqual(reading.timestamp, entry[1])

    def test_combined_read_no_end_condition(self):
        # Generate a bunch of random entries at the beginning, making sure to omit the end marker.
        test_csv = [str(randint(12, 100)) for _ in range(100)]

        test_data = [(random(), datetime(2015, 3, 1, i)) for i in range(12, 20)]
        for entry in test_data: test_csv += _generate_entry(entry[0], entry[1])

        with self.assertLogs(level='WARNING') as cm:
            result = _read_combined(test_csv)
        self.assertIn(UNEXPECTED_EXIT_COMBINED_LIST, cm.records[0].getMessage())

        self.assertEqual(len(result), len(test_data))
        for reading, entry in zip(result, test_data):
            self.assertEqual(reading.kwh, entry[0])
            self.assertEqual(reading.timestamp, entry[1])


class MeterListCase(unittest.TestCase):

    def test_meter_no_indexing(self):
        test_csv = [str(randint(12, 100)) for _ in range(100)]
        test_csv.append('24')  # end marker for list
        test_data = [(random(), datetime(2020, 12, 5, i)) for i in range(0, 19)]
        for entry in test_data: test_csv += _generate_entry(entry[0], entry[1])

        idx, result = _get_list_readings(test_csv, len(test_csv)-1, [])

        self.assertEqual(len(result), len(test_data))

        result.reverse()
        for reading, entry in zip(result, test_data):
            self.assertEqual(reading.kwh, entry[0], f"{reading=} {entry=}")
            self.assertEqual(reading.timestamp, entry[1]+timedelta(hours=time_offset), f"{reading=} {entry=}")

    def test_meter_with_indexing(self):
        """ Same as previous, but interleave indexed readings (readings that retrieve their value from
            the combined list) with explicit readings. """
        test_csv = [str(randint(12, 100)) for _ in range(10)]
        test_data = [(random(), datetime(2020, 12, 5, i)) for i in range(0, 19)]

        from smarthubp import MeterReading
        combined_list = [MeterReading(kwh=entry[0], timestamp=entry[1]) for entry in test_data]
        combined_list.reverse()
        test_csv.append('24')
        for idx, entry in enumerate(test_data):
            if idx % 3:
                test_csv += _generate_entry(entry[0], entry[1])
            else:
                test_csv += _generate_reference(idx)

        idx, result = _get_list_readings(test_csv, len(test_csv)-1, combined_list)

        self.assertEqual(len(test_data), len(result))

        result.reverse()
        for reading, entry in zip(result, test_data):
            self.assertEqual(reading.kwh, entry[0], f"{reading=} {entry=}")
            self.assertEqual(reading.timestamp, entry[1]+timedelta(hours=time_offset), f"{reading=} {entry=}")

    def test_meter_with_offset(self):
        """ Rerun the above tests w/ randomized time offset to ensure it is handled properly. """
        set_import_time_offset(randint(1, 9))
        self.test_meter_with_indexing()
        self.test_meter_no_indexing()
