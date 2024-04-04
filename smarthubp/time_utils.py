import base64
from datetime import datetime

time_offset = 0

def timestamp_from_encoded(ts_str: str) -> datetime:
    """ Convert from uuencode 4msec from epoch format to datetime.

        Args:
            ts_str (str): Encoded timestamp to decode.

        Returns:
            datetime: Timestamp in datetime format.
    """
    byte_str = (ts_str + "==").encode()          # "Yf3U_WA" => b"YF3U_WA=="
    byte_str = base64.b64decode(byte_str, altchars=b"$_")  # => b"a\xfd\xd4\xfd"
    msec4epoch = int.from_bytes(byte_str, "big")
    return datetime.fromtimestamp(msec4epoch//250)


def encoded_from_timestamp(timestamp: datetime) -> str:
    """ Convert from timestamp to uuencode 4msec from epoch format.
        Note: This may not be identical to the string provided to timestamp_from_encoded
              but will decode to the same value.

        Args:
            timestamp (datetime): Timestamp to be encoded.

        Returns:
            string: UUEncoded string representing the number of 4 millisecond intervals from the epoch.
    """
    sec_from_epoch = int(timestamp.timestamp())
    msec4epoch = sec_from_epoch * 250
    byte_str = msec4epoch.to_bytes(8, "big")
    return base64.b64encode(byte_str, altchars=b"$_").decode()


def set_import_time_offset(hours:int):
    """ Apply the following offset to data produced by this parser. """
    global time_offset
    time_offset = hours