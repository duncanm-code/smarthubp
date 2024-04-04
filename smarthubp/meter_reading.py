from dataclasses import dataclass
from datetime import datetime


@dataclass
class MeterReading:
    """ Contains information related to a meter reading. """
    timestamp: datetime
    kwh: float
