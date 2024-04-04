# Smarthubp

A parser for the ReadingService and utility-usage web call returns used in the Smarthub Webapp.

Smarthub provides a usage explorer that is often the only access provided to the daily and hourly
meter data given to customers.  While some utilities provide a way of exporting this data many
do not.  

In order to capture the data I open the network monitor (available in most web browsers in developer tools) and copy the response.  The response can captured to a file or provided as a string to this parser to
split into meter names, timestamps, and readings.

## Installation

This package is designed to be installed via pip:

'''bash
pip install smarthubp
'''

## Usage

'''code
import smarthubp
smarthubp.set_import_time_offset(8)  # Number of hours to add to the readings for timezones.
reading_service = smarthubp.read_from_file('filename.txt')]

meter = reading_service.meters[0]
reading = reading_service[meter][0].reading
time = reading_service[meter][0].timestamp
print(f"First Result from {meter} is {reading} at {time}")
'''



