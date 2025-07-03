import datetime as dt
import pandas as pd
import os

# local library that generates the html strings to download NEST data
import nest

# print message to log file to say started
print('GetDataNMDBNeutron.py    :', \
      dt.datetime.strftime(dt.datetime.now(), '%Y-%m-%d %H:%M:%S'), \
      ': Started scraping NMDB Oulu neutron data for', \
      dt.datetime.strftime(dt.datetime.now() - dt.timedelta(1), '%Y-%m-%d'))

# create path to save data
path = '/home/pi/UKRAA_PicoMuon/data/NMDB/neutrons/'\
       + dt.datetime.strftime(dt.date.today() - dt.timedelta(days = 1), '%Y')\
       + '/'\
       + dt.datetime.strftime(dt.date.today() - dt.timedelta(days = 1), '%Y-%m')

# Check if the specific path exists or not
pathExist = os.path.exists(path)
if not pathExist:
    # Create a new directory because it does not exist
    os.makedirs(path)
    print('GetDataNMDBNeutron.py    :',\
          dt.datetime.strftime(dt.datetime.now(), '%Y-%m-%d %H:%M:%S'), \
          ': New NMDB Oulu neutron directory created')

# create file for yesterdays data
outfile = '/home/pi/UKRAA_PicoMuon/data/NMDB/neutrons/'\
          + dt.datetime.strftime(dt.date.today() - dt.timedelta(days = 1), '%Y')\
          + '/'\
          + dt.datetime.strftime(dt.date.today() - dt.timedelta(days = 1), '%Y-%m')\
          + '/'\
          + dt.datetime.strftime(dt.date.today() - dt.timedelta(days = 1), '%Y-%m-%d')\
          + '.txt'

# Start date/time for data to be extraction - should be start of day yesterday, i.e. 00:00:00
start   = dt.datetime(int(dt.datetime.strftime(dt.date.today() - dt.timedelta(days = 1), '%Y')), \
                      int(dt.datetime.strftime(dt.date.today() - dt.timedelta(days = 1), '%m')), \
                      int(dt.datetime.strftime(dt.date.today() - dt.timedelta(days = 1), '%d')), \
                      0, \
                      0, \
                      0)

# End date/time for data to be extracted - should be end of day yesterday, i.e. 23:59:59
end     = dt.datetime(int(dt.datetime.strftime(dt.date.today() - dt.timedelta(days = 1), '%Y')), \
                      int(dt.datetime.strftime(dt.date.today() - dt.timedelta(days = 1), '%m')), \
                      int(dt.datetime.strftime(dt.date.today() - dt.timedelta(days = 1), '%d')), \
                      23, \
                      59, \
                      59)

table   = "revori"  # virtual table with merge original and revised data

station = "oulu"  # station short name as used in NMDB

data    = ["p", "u", "c", "e"]  # download pressure, uncorrected, corrected (for pressure) and efficiency corrected data

# Create download string to access NMDB NEST data files
download = nest.single(station, \
                       table, \
                       data, \
                       start, \
                       end)

names = data.copy()  # keep the original columns, work only with a copy

names.insert(0, "start_date_time") # add header for first column

# create panda dataframe
df = pd.read_table(download, \
                   sep=";", \
                   comment="#", \
                   header=0, \
                   names=names)

# Save panda dataframe to csv file
df.to_csv(outfile, \
          sep=",", \
          index=False, \
          header=False, \
          encoding='utf-8')

# =============================================================================
# Message to log file at end of program

# print message to log file to say completed
print('GetDataNMDBNeutron.py    :', \
      dt.datetime.strftime(dt.datetime.now(), '%Y-%m-%d %H:%M:%S'), \
      ': Completed scraping NMDB Oulu neutron data for', \
      dt.datetime.strftime(dt.datetime.now() - dt.timedelta(1), '%Y-%m-%d'))
