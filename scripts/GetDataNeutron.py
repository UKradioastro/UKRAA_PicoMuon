import datetime as dt
import pandas as pd
import os
from picomuon_common import get_base_path, log_message, utc_yesterday

# local library that generates the html strings to download NEST data
import nest

PROCESS_NAME = "GetDataNeutron.py"

# get yesterday variable
yesterday = utc_yesterday()
base_path = get_base_path()

# print message to log file to say started
log_message(PROCESS_NAME, f"Started neutron data scraping for {yesterday.strftime('%Y-%m-%d')}")

# year
yesterdayYear = yesterday.year

#month
yesterdayMonth=yesterday.month

# day
yesterdayDay = yesterday.day

# create path to save data
path = str(base_path / 'data/neutrons') + '/'\
       + yesterday.strftime('%Y')\
       + '/'\
       + yesterday.strftime('%Y-%m')

# Check if the specific path exists or not
pathExist = os.path.exists(path)
if not pathExist:
    # Create a new directory because it does not exist
    os.makedirs(path)
    log_message(PROCESS_NAME, "New directory created")

# create file for yesterdays data
outfile = str(base_path / 'data/neutrons') + '/'\
          + yesterday.strftime('%Y')\
          + '/'\
          + yesterday.strftime('%Y-%m')\
          + '/'\
          + yesterday.strftime('%Y-%m-%d')\
          + '.txt'

# Start date/time for data to be extraction - should be start of day yesterday, i.e. 00:00:00
start   = dt.datetime(yesterdayYear, yesterdayMonth, yesterdayDay, 0, 0, 0)

# End date/time for data to be extracted - should be end of day yesterday, i.e. 23:59:59
end     = dt.datetime(yesterdayYear, yesterdayMonth, yesterdayDay, 23, 59, 59)

table   = "revori"  # virtual table with merge original and revised data

station = "oulu"  # station short name as used in NMDB

data    = ["p", "u", "c", "e"]  # download pressure, uncorrected, corrected (for pressure) and efficiency corrected data

# Create download string to access NMDB NEST data files
download = nest.single(station, table, data, start, end)

names = data.copy()  # keep the original columns, work only with a copy

names.insert(0, "start_date_time") # add header for first column

# create panda dataframe
df = pd.read_table(download, sep=";", comment="#", header=0, names=names)

# Save panda dataframe to csv file
df.to_csv(outfile,  sep=",", index=False, header=False, encoding='utf-8')

# =============================================================================
# Message to log file at end of program

# print message to log file to say completed
log_message(PROCESS_NAME, f"Completed neutron data scraping for {yesterday.strftime('%Y-%m-%d')}")
