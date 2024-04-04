import logging
from datetime import timedelta

from smarthubp.meter_reading import MeterReading
from smarthubp.time_utils import timestamp_from_encoded, time_offset

UNEXPECTED_EXIT_COMBINED_LIST = "Unexpected exit from combined list processing."


def _read_combined(csvd: list[str]) -> list[MeterReading]:
    """ Read the combined list, a list near the end of the dataset which contains values from all other lists
        combined into one value.  This list is important because meter reading lists may reference values in
        this list by index, so this data must be available to generate values for those entries.

        Args:
            csvd (list): The comma separated value list.
        Returns:
            list[MeterReading]: The combined readings list.
    """

    # Entries look like f.ff,10,"TIMESTAMP",9,0,0,1,0,0,8
    # The end pattern may differ, but I believe the 10, 9, 8 will remain as separators.
    # I have reason to believe that this list will never use indexing logic, since the indexing logic
    # in _read_list refers to this list.
    # The number '11' should immediately follow the list.

    idx = len(csvd)-1

    ret = []
    while idx >= 0:
        while idx >= 0 and csvd[idx] != '9' and csvd[idx] != '11': idx -= 1

        # Processing outside the list which has repeated 8, 9, 10 patterns.  Exit processing.
        if idx < 0 or csvd[idx-2] != '10':
            logging.warning(UNEXPECTED_EXIT_COMBINED_LIST)
            break

        # Normal Exit condition at end of list.
        if csvd[idx] == '11':
            break

        ts = timestamp_from_encoded(csvd[idx - 1])
        ret.append(MeterReading(ts, float(csvd[idx-3])))
        idx -= 1
    # Must be reversed to correspond to meter idx values.  The timestamps will be opposite the other meters.
    ret.reverse()
    return ret


def _get_list_readings(csvd: list[str],
                       idx: int,
                       combined_readings: list[MeterReading]) -> tuple[int, list[MeterReading]]:
    """
    Given the comma-separated value list (csvd) and a starting index (idx),
    retrieve the timestamps and readings for the next list. Return the stop index and
    MeterReadings. This function requires the combined_readings to be provided.

    Args:
        csvd (list): The comma-separated value list.
        idx (int): The starting index for processing the csvd list.
        combined_readings (list): The list of combined readings to be provided. This list should
            be generated using the `_read_combined` method to ensure the expected format.  This list is used
            when a reading is referenced by index.

    Returns:
        tuple: A tuple containing the stop index and MeterReadings.

    """
    # Entries look like:
    # f.ff, 10, TIMESTAMP, 9, 0, 0, 1, 0, 0, 8
    # -1200, TIMESTAMP, 9, 0, 0, 1, 0, 0, 8
    # -1203, -1204, 0, 0, 1, 0, 0, 8
    # f.ff, 10, -1207, 0, 0, 1, 0, 0, 8
    # When an index is present instead of an reading or timestamp it is an index into the combined list, which must
    # be separately read and provided to this function.
    readings = []
    while idx >= 0:
        while idx >= 0 and csvd[idx] not in ['8', '24', '3']: idx -= 1
        if idx < 8 or csvd[idx] != '8': break
        idx -= 6

        ts = None
        if csvd[idx] == '9':
            ts = timestamp_from_encoded(csvd[idx - 1])
            idx -= 2
        else:  # index into combined list instead of giving a timestamp
            j = (int(csvd[idx]) // 3) + 2
            ts = combined_readings[j].timestamp
            idx -= 1
        ts += timedelta(hours=time_offset)

        kwh = None
        if csvd[idx] == '10':
            kwh = float(csvd[idx-1])
        else:  # index into combined list instead of giving a reading
            j = (int(csvd[idx]) // 3) + 2
            kwh = combined_readings[j].kwh
        readings.append(MeterReading(ts, kwh))
    return idx, readings


def meter_reading_generator(csvd: list[str], combined_readings: list[MeterReading]):
    """ This is a generator that runs from the end to the beginning of a dataset,
        yielding readings at each identified list beginning.

        Args:
            csvd (list): The comma-separated value list.
            combined_readings (list): The list of combined readings to be provided to _get_list_readings.

        Yields:
            list[MeterReading]: The next reading list in the comma-separated value list.
    """

    idx = len(csvd)-1
    while idx >= 0 and csvd[idx] != '24': idx -= 1

    while idx >= 0:
        if csvd[idx] == '3': break
        # The beginning of a list block
        assert csvd[idx] == '24'
        # Between 24 and the list there are two datetime stamps.
        # Really should read the time offset off of the second timestamp.
        # Find the beginning of list data.
        while csvd[idx] != '8': idx -= 1
        idx, reading_list = _get_list_readings(csvd, idx, combined_readings)
        yield reading_list


def _extract_meters(meta_csv: list[str]) -> list[str]:
    """ Returns a list of meters given the metadata list.
        Args:
            meta_csv (list): The metadata list, extracted from the primary comma-separated values.
        Returns:
            list[str]: The meter names present in this data set.
        Raises:
            InvalidMetadata: If the metadata list does cannot be processed due to lack of expected markers.
    """
    # The second list contains an array of class names and account information.
    # The meters correspond, in reverse order, to the kwh lists above.
    # Net meters are expanded into a consumption/generation/net set of lists.
    # I'm following the rules: '####+#" is always followed by a meter name and is never itself a meter name.
    # a value with a . in it is always a class name
    # a value with a # in it always relates to a color and is never a meter name.
    #    a value with a - in it is either a net meter name or not a meter. (gray-stroke for example)
    # all values between the first + and the "column" label that aren't
    # a color, class name, or contain a -, are meters.
    indices = [i for i, n in enumerate(meta_csv) if "+" in n]
    if not indices:
        raise InvalidMetadata("The provided meta-data values lack any appropriate start marker.")

    # The meter portion ends with a "net-meter", "column", type structure.
    try:
        indices.append(meta_csv.index('"column"'))
    except ValueError:
        raise InvalidMetadata("The provided meta-data values lacks the appropriate end marker.")

    ret = []

    for start, end in zip(indices, indices[1:]):
        # Strip off the first and last characters to eliminate quotation marks.
        meter_name = meta_csv[start+1][1:-1]
        submeter_names = []
        for v in meta_csv[start+2:end]:
            # Assume that none of these characters can be in meter names.
            if '.' in v: continue  # class name
            if '#' in v: continue  # color name, url(#anchor)
            v = v[1:-1]  # Strip off first and last characters to eliminate quotation marks.
            if meter_name in v:  # submeter (meter_name - Consumption, for example)
                submeter_names.append(v)
            elif '-' in v: continue
            else:
                if submeter_names:
                    ret += submeter_names
                    submeter_names = []
                else:
                    ret.append(meter_name)
                meter_name = v

        if submeter_names: ret += submeter_names
        else: ret.append(meter_name)
    return ret


def _transform_data_to_list(data: str) -> tuple[list[str], list[str]]:
    """ Process metadata list and convert the remaining data string
        to a list of strings for further processing.

        Args:
            data (str): The return value from the reading service, in string form, on a single line.
        Returns:
            tuple: A tuple containing:
               - list[str]: A list of meter names generated by _extract_meters.
               - list[str]: The remaining comma-separated data in a list of strings.
        Raises:
            InvalidData: When the data list does not have expected elements.
            InvalidMetaData: When no metadata is found, or metadata cannot be processed.
    """
    if data[0:5] != "//OK[": raise InvalidData("Input does not start with //OK and a list open.")
    data = data.strip()
    data = data.replace('].concat([', ',')  # long arrays get javascript concats inside.  Fun!
    data = data.replace(']).concat([', ',')  # In case we get a concat of a concat?  Haven't actually seen this.
    data = data.replace('],[', ',')    # concat seems to do a list of lists... like [].concat([], [], [], ...)
    data = data.rstrip(')')            # Finally remove the closing paren of the concat function, if present.

    if data[-1] != ']': raise InvalidData("Input does not close with list termination.")

    # Expect //OK[data list, [metadata], footer] format
    metadata_start = data.rfind('[')
    if metadata_start == 4: raise InvalidMetadata("No metadata found within input.")

    # raises InvalidMetadata
    meter_names: list[str] = _extract_meters(data[metadata_start:-4].split(','))
    meter_names.reverse()
    logging.debug(f'Found {meter_names=}.')

    csvd = data[5:metadata_start].split(',')  # Drop header, metadata, and footer.

    return meter_names, csvd


class InvalidMetadata(Exception):
    """ Indicates that the metadata is unparseable. """
    pass


class InvalidData(Exception):
    """ Indicates that the data is unparseable. """
    pass
