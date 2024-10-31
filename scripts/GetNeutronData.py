import datetime as dt
import pandas as pd
import os

# local library that generates the html strings to download NEST data
import nest

#now = dt.datetime.now()
#print(now)

#today = dt.date.today()
#print(today)

yesterday = dt.date.today() - dt.timedelta(days = 1)
#print(yesterday)

#year = dt.date.today().year
#print(year)

#month=dt.date.today().month
#print(month)

#day = dt.date.today().day
#print(day)

yesterdayYear = yesterday.year
#print(yesterdayYear)

yesterdayMonth=yesterday.month
#print(yesterdayMonth)

yesterdayDay = yesterday.day
#print(yesterdayDay)

path = '/home/pi/UKRAA_muons/data/neutrons/'\
       + dt.datetime.strftime(dt.date.today() - dt.timedelta(days = 1), '%Y')\
       + '/'\
       + dt.datetime.strftime(dt.date.today() - dt.timedelta(days = 1), '%Y-%m')
#print(path)

# Check if the specific path exists or not
pathExist = os.path.exists(path)
if not pathExist:
    # Create a new directory because it does not exist
    os.makedirs(path)
    print('New directory created')

outfile = '/home/pi/UKRAA_muons/data/neutrons/'\
          + dt.datetime.strftime(dt.date.today() - dt.timedelta(days = 1), '%Y')\
          + '/'\
          + dt.datetime.strftime(dt.date.today() - dt.timedelta(days = 1), '%Y-%m')\
          + '/'\
          + dt.datetime.strftime(dt.date.today() - dt.timedelta(days = 1), '%Y-%m-%d')\
          + '.txt'
#print(outfile)

# Start date/time for data to be extraction - should be start of day yesterday, i.e. 00:00:00
start   = dt.datetime(yesterdayYear, yesterdayMonth, yesterdayDay, 0, 0, 0)

# End date/time for data to be extracted - should be end of day yesterday, i.e. 23:59:59
end     = dt.datetime(yesterdayYear, yesterdayMonth, yesterdayDay, 23, 59, 59)

table   = "revori"  # virtual table with merge original and revised data

station = "oulu"  # station short name as used in NMDB

data    = ["p", "u", "c", "e"]  # download pressure, uncorrected, corrected (for pressure) and efficiency corrected data

# Create download string to access NMDB NEST data files
download = nest.single(station, table, data, start, end)
# the download string for the data we selected
#print(download)

names = data.copy()  # keep the original columns, work only with a copy

names.insert(0, "start_date_time") # add header for first column

# create panda dataframe
df = pd.read_table(download, sep=";", comment="#", header=0, names=names)

# Save panda dataframe to csv file
df.to_csv(outfile,  sep=",", index=False, header=False, encoding='utf-8') 