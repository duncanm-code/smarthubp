""" Smarthub Reading Service Parser.

    The smarthub product used by many electrical coop's calls many services to retrieve cost information, meter
    readings, historical weather data among other pieces of data.  This class is designed to present the information
    returned by the ReadingService remote call or utility-usage remote call.

    The ReadingService call masquerades as a json call, but in fact returns //OK followed by a javascript list,
    all on one line.  The list consists of multiple parts, which includes meter readings for each meter associated
    with the account.  A secondary metadata list, near the end of the data, can give information on the account and
    the names of the meters, allowing for the data in the call to be associated with the actual piece of equipment.

    The utility-usage poll is a newer version of Smarthub's interface which returns a json object that can be
    directly loaded.  The kwh data can be found in data.ELECTRIC[0].series and the combined list in
    data.ELECTRIC[0].baseSeries.  series contains all meter data necessary.

    Obtain a ReadingService object by calling the factory methods: readings_from_file(filename) or
    readings_from_str(str).
 """
import logging
import json
from datetime import datetime, timedelta

from smarthubp.meter_reading import MeterReading
from smarthubp.parse import _read_combined, meter_reading_generator, _transform_data_to_list
from smarthubp.time_utils import time_offset
from smarthubp.parse import InvalidData


def readings_from_file(fname: str):
    """ Factory method: Load readings from a file.

        Args:
            fname (str): A filename containing the reading service return.
        Returns:
            ReadingService: A ReadingService object allowing access to the data read from fname.
        Exceptions:
            InvalidData : If the data format isn't recognized.
            InvalidMetaData : If the metadata format isn't recognized.
    """
    return readings_from_str(open(fname).readlines()[0])


def readings_from_str(data: str) -> "ReadingService":
    """ Factory method: Given a data line from the reading service, determines which format is likely and
        instantiates a ReadingService contained kwh and timestamp values for each meter.

        Args:
            data (str): The data read from a reading service call, all on one line.
        Returns:
            ReadingService: A ReadingService object allowing access to the data from data.
        Exceptions:
            InvalidData : If the data format isn't recognized.
            InvalidMetaData : If the metadata format isn't recognized.
    """
    # Reading Service (old style) type data.
    if data[0:5] == "//OK[":
        return readings_from_reading_service(data)
    # Utility-Usage (or potentially other json based) type data.
    try:
        jsd = json.loads(data)
    except json.JSONDecodeError:
        raise InvalidData("Data does match a known smarthub format.")

    return readings_from_utility_usage(jsd)


def readings_from_reading_service(data) -> "ReadingService":
    """ Factory method: Given data known to be in Smarthub's ReadingService RPC response format, determines
        the number of meters, parses all kwh and timestamp values for each meter.

        Args:
            data (str): The data read from a reading service call, all on one line.
        Returns:
            ReadingService: A ReadingService object allowing access to the data from data.
        Exceptions:
            InvalidData : If the data format isn't recognized.
            InvalidMetaData : If the metadata format isn't recognized.
    """
    meter_names, csvd = _transform_data_to_list(data)
    combined_readings = _read_combined(csvd)
    # combined_readings are required because _if_ there is only one reading during a time period it comes from
    # the combined list, otherwise it comes from the meter specific list.
    reading_gen = meter_reading_generator(csvd, combined_readings)
    reading_lists = {meter_names.pop(): reading_list for reading_list in reading_gen}
    if meter_names:
        logging.warning("Identified more meters than could be matched to readings.  There may be a list mismatch.")
        logging.warning(f"Remaining lists: {meter_names}")

    return ReadingService(combined_readings, reading_lists)


def readings_from_utility_usage(jsd: dict):
    """ Factory method: Given data assumed to be from Smarthub's utility-usage RPC response, and provided as a
        json loaded dict, creates a ReadingService object.

        Args:
            jsd (dict): The data read and transformed as json from the utility-usage call.
        Returns:
            ReadingService: A ReadingService object allowing access to the data from jsd.
        Exceptions:
            InvalidData: Generated if critical keys are not present, indicating that the json may not be from a
                         valid source.
    """
    base_data = jsd['data']['ELECTRIC'][0]
    combined_readings = [MeterReading(datetime.fromtimestamp((v["x"]//1000)+21600), v["y"])
                         for v in base_data["baseSeries"]["data"]]
    reading_lists = {}
    for series in base_data["series"]:
        meter = series['name']
        readings = [MeterReading(datetime.fromtimestamp((v["x"]//1000)+21600), v["y"]) for v in series['data']]
        reading_lists[meter] = readings
    return ReadingService(combined_readings, reading_lists)


class ReadingService:
    """ Class exposes data from the Smarthub's ReadingService RPC response and provides related utility functions.

        Instantiate this class via the readings_from_str or readings_from_file factory methods.
    """
    def __init__(self, combined: list[MeterReading], meters: dict[str, list[MeterReading]]):
        """Initializes a new instance of ReadingService.

        Args:
            combined (list[MeterReading]): A list of combined meter readings.
            meters (dict[str, list[MeterReading]]): A dictionary mapping meter names to lists of meter readings.
        """
        self.meter: dict[str, list[MeterReading]] = meters
        self.combined: list[MeterReading] = combined

    def __getitem__(self, key) -> list[MeterReading]:
        """Retrieves the meter readings for the specified meter name.

        Args:
            key (str): The meter name.

        Returns:
            list[MeterReading]: A list of meter readings for the specified meter.
        """
        return self.meter[key]

    @property
    def meter_names(self) -> list[str]:
        """Returns a list of meter names present in the ReadingService.

        Returns:
            list[str]: The meter names.
        """
        return self.meter.keys()

    def get_rlist(self, meter_name: str) -> list[float]:
        """Extracts a reading-only list from the specified meter.

        Args:
            meter_name (str): The name of the meter.

        Returns:
            list[float]: A list of readings from the specified meter.
        """
        return [r.kwh for r in self.meter[meter_name]]

    def get_tslist(self, meter_name: str) -> list[datetime]:
        """Extracts a timestamp-only list from the specified meter.

        Args:
            meter_name (str): The name of the meter.

        Returns:
            list[datetime]: A list of timestamps from the specified meter.
        """
        return [r.timestamp for r in self.meter[meter_name]]

    def get_combined(self) -> list[MeterReading]:
        """Retrieves the combined list of meter readings.

        The combined list is always present, and should be the most complete source of valid timestamps.
        The values in the combined list may not be an accurate representation of power used depending on
        the types of meters being reported.

        Returns:
            list[MeterReading]: The combined list of meter readings.
        """
        return self.combined

    def report(self, fname):
        """Dumps the meter readings, aligned by timestamp, to a file.

        Args:
            fname (str): The name of the file to write the report to.
        """
        with open(fname, 'w') as hndl:
            for entry in self.combined:
                dt = entry.timestamp.isoformat()
                dtc = entry.timestamp + timedelta(hours=time_offset)
                kwh_c = entry.kwh
                kwh_m = []
                for m in self.meter:
                    mr = [me for me in m if me.timestamp == dtc]
                    if mr:
                        if len(mr) > 1: kwh_m.append([v.kwh for v in mr])
                        else: kwh_m.append(mr[0].kwh)
                    else: kwh_m.append("")
                print(f"{dtc.isoformat()}\t{kwh_c:.2f}\t{kwh_m}")
                hndl.write(f"{dtc.isoformat()}\t{kwh_c:.2f}\t{kwh_m}\n")

    def apply_subtractive_meter(self, primary_meter, subtractive_meter):
        """Subtracts the contributions of the secondary meter from the primary meter.

        A primary meter with a subtractive meter has the total power consumption.
        This method subtracts out all the secondary meters contributions leading
        to two independent sets of readings.  This is important as the readings
        not subtracted out are usually billed at a different rate.

        Args:
            primary_meter (str): The name of the primary meter.
            subtractive_meter (str): The name of the subtractive (secondary) meter.
        """
        if primary_meter not in self.meter or subtractive_meter not in self.meter: return

        primary = self.meter[primary_meter]
        subtractive = self.meter[subtractive_meter]

        subtractive_idx = 0
        for reading in primary:
            while subtractive_idx < len(subtractive) and subtractive[subtractive_idx].timestamp < reading.timestamp:
                subtractive_idx += 1
            if subtractive_idx == len(subtractive): return  # No further values to subtractive.
            if subtractive[subtractive_idx].timestamp == reading.timestamp:
                reading.kwh -= subtractive[subtractive_idx].kwh
