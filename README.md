# Smarthubp

A parser for the ReadingService and utility-usage web call returns used in the Smarthub Webapp.

Smarthub provides a usage explorer that is often the only access provided to the daily and hourly
meter data given to customers.  While some utilities provide a way of exporting this data many
do not.  

In order to capture the data I open the network monitor (available in most web browsers in developer tools) and copy the response.  The response can captured to a file or provided as a string to this parser to
split into meter names, timestamps, and readings.

## Installation

This package is designed to be installed via pip:


```bash
pip install smarthubp
```

## Usage

```python
import smarthubp

reading_service = smarthubp.readings_from_file('filename.txt')

for meter in reading_service.meter_names:
    readings = reading_service[meter]
    if readings:
        first = readings[0]
        print(
            f"First result from {meter} is "
            f"{first.kwh} kWh at {first.timestamp}"
        )
```



