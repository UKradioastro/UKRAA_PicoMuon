#!/usr/bin/env python3

#imports
import datetime as dt
import csv
import os
import shutil

# print message to log file to say started
print('ProcessDataWeekACM0.py      :', \
      dt.datetime.strftime(dt.datetime.now(), '%Y-%m-%d %H:%M:%S'), 
      ': Started ACM0 weeks % deviation data processing, from', 
      dt.datetime.strftime(dt.datetime.now() - dt.timedelta(7), '%Y-%m-%d'), 
      'to', 
      dt.datetime.strftime(dt.datetime.now() - dt.timedelta(1), '%Y-%m-%d'))

# Set path for data file structure

# raw data file source
for i in range(1, 8):
    globals()['RawDataFile%s' % i] = '$HOME/UKRAA_PicoMuon/data/processed/day/ACM0/' \
                                     + dt.datetime.strftime(dt.datetime.now() - dt.timedelta(i), '%Y') \
                                     + '/' \
                                     + dt.datetime.strftime(dt.datetime.now() - dt.timedelta(i), '%Y-%m') \
                                     + '/' \
                                     + dt.datetime.strftime(dt.datetime.now() - dt.timedelta(i), '%Y-%m-%d') \
                                     + '.txt'
 

# Set file headers for data file structure
WeekFieldNames    = ['DateTime', 
                     'Position_T', 
                     'Position_B', 
                     'Position_M', 
                     'temperature', 
                     'pressure', 
                     'neutrons']


# create weeks worth of data
WeekPath = '$HOME/UKRAA_PicoMuon/data/processed/week/ACM0/' \
           + dt.datetime.strftime(dt.datetime.now() - dt.timedelta(1), '%Y') \
           + "/" \
           + dt.datetime.strftime(dt.datetime.now() - dt.timedelta(1), '%Y-%m')

# check if the specific path exists
pathExists = os.path.exists(WeekPath)
if not pathExists:
    # create directory structure
    os.makedirs(WeekPath)
    print('ProcessDataWeekACM0.py      :', 
          dt.datetime.strftime(dt.datetime.now(), '%Y-%m-%d %H:%M:%S'), 
          ': New ACM0 week directory created :', 
          WeekPath)

# week data file name
WeekDataFile = '$HOME/UKRAA_PicoMuon/data/processed/week/ACM0/' \
               + dt.datetime.strftime(dt.datetime.now() - dt.timedelta(1), '%Y') \
               + "/" \
               + dt.datetime.strftime(dt.datetime.now() - dt.timedelta(1), '%Y-%m') \
               + "/temp.txt"

# merge day data to make week data file
if os.path.exists(RawDataFile7):
    with open(WeekDataFile,'wb') as wfd:
        for f in [RawDataFile7,RawDataFile6,
                  RawDataFile5,RawDataFile4,RawDataFile3,RawDataFile2,RawDataFile1]:
            with open(f,'rb') as fd:
                shutil.copyfileobj(fd, wfd)

else:
    print('ProcessDataWeekACM0.py      :', 
          dt.datetime.strftime(dt.datetime.now(), '%Y-%m-%d %H:%M:%S'), 
          ': Not enough ACM0 day files are available yet to process weeks % deviation data...')
    print('ProcessDataWeekACM0.py      :', 
          dt.datetime.strftime(dt.datetime.now(), '%Y-%m-%d %H:%M:%S'), 
          ': **FAILED** to process ACM0 weeks % deviation data, from', 
          dt.datetime.strftime(dt.datetime.now() - dt.timedelta(7), '%Y-%m-%d'), 
          'to', 
          dt.datetime.strftime(dt.datetime.now() - dt.timedelta(1), '%Y-%m-%d'))
    exit()
    
# Processed data path
ProcessedPath = '$HOME/UKRAA_PicoMuon/data/processed/week/ACM0/'\
                + dt.datetime.strftime(dt.datetime.now() - dt.timedelta(1), '%Y') \
                + "/" \
                + dt.datetime.strftime(dt.datetime.now() - dt.timedelta(1), '%Y-%m')

# check if the specific path exists
pathExists = os.path.exists(ProcessedPath)
if not pathExists:
    # create directory structure
    os.makedirs(ProcessedPath)
    print('ProcessDataWeekACM0.py      :', 
          dt.datetime.strftime(dt.datetime.now(), '%Y-%m-%d %H:%M:%S'), 
          ': New ACM0 week directory created :', 
          ProcessedPath)

# Processed data file name
ProcessedDataFile = "$HOME/UKRAA_PicoMuon/data/processed/week/ACM0/" \
                     + dt.datetime.strftime(dt.datetime.now() - dt.timedelta(1), '%Y') \
                     + "/" \
                     + dt.datetime.strftime(dt.datetime.now() - dt.timedelta(1), '%Y-%m') \
                     + "/" \
                     + dt.datetime.strftime(dt.datetime.now() - dt.timedelta(1), '%Y-%m-%d') \
                     + ".txt"

# =============================================================================
# Main program

StartTime_str = dt.datetime.strftime(dt.datetime.now() - dt.timedelta(7), '%Y-%m-%d') \
                + ' 00:00:00.000000'

StartTime_datetime = dt.datetime.strptime(StartTime_str, '%Y-%m-%d %H:%M:%S.%f')

EndTime_str = dt.datetime.strftime(dt.datetime.now() - dt.timedelta(1), '%Y-%m-%d') \
              + ' 23:59:59.999999'

EndTime_datetime = dt.datetime.strptime(EndTime_str, '%Y-%m-%d %H:%M:%S.%f')

# define what the time change will be
minute = dt.timedelta(
    days         =  0,
    seconds      =  0,
    microseconds =  0,
    milliseconds =  0,
    minutes      = 10,
    hours        =  0,
    weeks        =  0)

# set up variable to use in loop
ProcessedTime = StartTime_datetime - minute

# number of 10 minutes in 7 days
n = 1008

# open file to store data in and append to end
ProcessedData = open(file=ProcessedDataFile, 
                     mode='a', 
                     encoding='UTF-8')

for i in range(1, n + 1):
    # add timedelta to each time value from 00:00:00 to 23:59:00
    ProcessedTime = ProcessedTime + minute
    
    StartBinTime = ProcessedTime

    EndBinTime = StartBinTime + minute

    # using csv.DictReader
    WeekFile = open(file=WeekDataFile, 
                    mode='r', 
                    encoding='UTF-8')
    
    WeekCSV_reader = csv.DictReader(WeekFile, 
                                    WeekFieldNames)

    # set counters to zero (remember 'NaN' is a float)
    count_T     = 0.0
    count_B     = 0.0
    count_M     = 0.0
    temperature = 0.0
    pressure    = 0.0
    count_N     = 0.0

    for WeekLine in WeekCSV_reader:
        # try to get raw data after start StartBinTime
        # convert string to dt.datetime.datetime format
        WeekDatetime = dt.datetime.strptime(WeekLine['DateTime'], 
                                            '%Y-%m-%d %H:%M:%S')
        
        # search file for data between two time points
        if (WeekDatetime >= StartBinTime) and (WeekDatetime < EndBinTime):
            # increase relevant counter
            count_T = count_T + float(WeekLine['Position_T'])
            count_B = count_B + float(WeekLine['Position_B'])
            count_M = count_M + float(WeekLine['Position_M'])
            temperature = temperature + float(WeekLine['temperature'])
            pressure = pressure + float(WeekLine['pressure'])
            count_N = count_N + float(WeekLine['neutrons'])

    # close open WeekFile
    WeekFile.close()

    # no need for 'nan' as already included in day data
    # check if there is some top counts data
    if (count_T != 0.0):
        ProcessedCPM_T = '{:.0f}'.format(count_T)
    else:
        ProcessedCPM_T = float('nan')
    # check if there is some bottom counts data
    if (count_B != 0.0):
        ProcessedCPM_B = '{:.0f}'.format(count_B)
    else:
        ProcessedCPM_B = float('nan')
    # check if there is some coincidence counts data
    if (count_M != 0.0):
        ProcessedCPM_M = '{:.0f}'.format(count_M)
    else:
        ProcessedCPM_M = float('nan')

    # check if there is some count data
    if ((count_T + count_B + count_M) != 0.0):
        ProcessedTemp  = '{:.1f}'.format(temperature / 2.0)
        ProcessedPres  = '{:.1f}'.format(pressure / 2.0)
    else:
        ProcessedTemp = float('nan')
        ProcessedPres = float('nan')

    # check if there is some neutron counts data
    if (count_N > (400.0 * 2.0)):
        ProcessedCPM_N = '{:.3f}'.format(count_N)
    else:
        ProcessedCPM_N = float('nan')

    # write to file
    ProcessedData.write(str(ProcessedTime))          # Data time date
    ProcessedData.write(",")                         # "," separator
    ProcessedData.write(str(ProcessedCPM_T))         # Top detector count over 10 minutes
    ProcessedData.write(",")                         # "," separator
    ProcessedData.write(str(ProcessedCPM_B))         # Bottom detector count over 10 minutes
    ProcessedData.write(",")                         # "," separator
    ProcessedData.write(str(ProcessedCPM_M))         # Muon count over 10 minutes
    ProcessedData.write(",")                         # "," separator
    ProcessedData.write(str(ProcessedTemp))          # Detector temperature over 10 minutes
    ProcessedData.write(",")                         # "," separator
    ProcessedData.write(str(ProcessedPres))          # Detector pressure over 10 minutes
    ProcessedData.write(",")                         # "," separator
    ProcessedData.write(str(ProcessedCPM_N))         # Neutron count over 10 minutes
    ProcessedData.write("\n")                        # new line

# close open ProcessedData file
ProcessedData.close()

# =============================================================================
# Message to log file at end of program

# print message to log file to say completed
print('ProcessDataWeekACM0.py      :', 
      dt.datetime.strftime(dt.datetime.now(), '%Y-%m-%d %H:%M:%S'), 
      ': Completed ACM0 weeks % deviation data processing, from', 
      dt.datetime.strftime(dt.datetime.now() - dt.timedelta(7), '%Y-%m-%d'), 
      'to', 
      dt.datetime.strftime(dt.datetime.now() - dt.timedelta(1), '%Y-%m-%d'))


# =============================================================================
# END of program