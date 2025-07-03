#!/usr/bin/env python3

#imports
import datetime as dt
import csv
import os

# print message to log file to say started
print('ProcessDataCpmACM0.py    :', \
      dt.datetime.strftime(dt.datetime.now(), '%Y-%m-%d %H:%M:%S'), \
      ': Started cpm ACM0 data processing for', \
      dt.datetime.strftime(dt.datetime.now() - dt.timedelta(1), '%Y-%m-%d'))

# Set file headers for data file structure
RawFieldNames    = ['RawDateTime', \
                    'RawPosition', \
                    'RawCount', \
                    'RawADC', \
                    'RawPicoTime', \
                    'RawDeadTime', \
                    'RawPicoTemp', \
                    'RawPicoPres']

# Set path for data file structure

# raw data file source
RawDataFile   = "/home/pi/UKRAA_PicoMuon/data/raw/ACM0/" \
                 + dt.datetime.strftime(dt.datetime.now() - dt.timedelta(1), '%Y') \
                 + "/" \
                 + dt.datetime.strftime(dt.datetime.now() - dt.timedelta(1), '%Y-%m') \
                 + "/" \
                 + dt.datetime.strftime(dt.datetime.now() - dt.timedelta(1), '%Y-%m-%d') \
                 + ".txt"

# Processed data path
ProcessedPath = '/home/pi/UKRAA_PicoMuon/data/processed/cpm/ACM0/'\
                + dt.datetime.strftime(dt.datetime.now() - dt.timedelta(1), '%Y') \
                + "/" \
                + dt.datetime.strftime(dt.datetime.now() - dt.timedelta(1), '%Y-%m')

# check if the specific path exists
pathExists = os.path.exists(ProcessedPath)
if not pathExists:
    # create directory structure
    os.makedirs(ProcessedPath)
    print('ProcessDataCpmACM0.py    :', \
          dt.datetime.strftime(dt.datetime.now(), '%Y-%m-%d %H:%M:%S'), \
          ': New ACM0 cpm directory created :', \
          ProcessedPath)

# Processed data file name
ProcessedDataFile = "/home/pi/UKRAA_PicoMuon/data/processed/cpm/ACM0/" \
                     + dt.datetime.strftime(dt.datetime.now() - dt.timedelta(1), '%Y') \
                     + "/" \
                     + dt.datetime.strftime(dt.datetime.now() - dt.timedelta(1), '%Y-%m') \
                     + "/" \
                     + dt.datetime.strftime(dt.datetime.now() - dt.timedelta(1), '%Y-%m-%d') \
                     + ".txt"

# =============================================================================
# Main program

StartTime_str = dt.datetime.strftime(dt.datetime.now() - dt.timedelta(1), '%Y-%m-%d') \
                + ' 00:00:00.000000'

StartTime_datetime = dt.datetime.strptime(StartTime_str, '%Y-%m-%d %H:%M:%S.%f')

EndTime_str = dt.datetime.strftime(dt.datetime.now() - dt.timedelta(1), '%Y-%m-%d') \
              + ' 23:59:59.999999'

EndTime_datetime = dt.datetime.strptime(EndTime_str, '%Y-%m-%d %H:%M:%S.%f')

# define what the time change will be
minute = dt.timedelta(
    days         =  0,
    seconds      = 60,
    microseconds =  0,
    milliseconds =  0,
    minutes      =  0,
    hours        =  0,
    weeks        =  0)

# set up variable to use in loop
ProcessedTime = StartTime_datetime - minute

# number of minutes in a day
n = 1440

# open file to store data in and append to end
ProcessedData = open(file=ProcessedDataFile, \
                     mode='a', \
                     encoding='UTF-8')

for i in range(1, n+1):
    # add a minute to each time value from 00:00:00 to 23:59:00
    ProcessedTime = ProcessedTime + minute
    
    StartBinTime = ProcessedTime

    EndBinTime = StartBinTime + minute

    # using csv.DictReader
    RawFile = open(file=RawDataFile, \
                   mode='r', \
                   encoding='UTF-8')
    
    RawCSV_reader = csv.DictReader(RawFile, \
                                   RawFieldNames)

    # set counters to zero
    count_T = 0
    count_B = 0
    count_M = 0

    for RawLine in RawCSV_reader:
        # try to get raw data after start StartBinTime
        # convert string to dt.datetime.datetime format
        RawDatetime = dt.datetime.strptime(RawLine['RawDateTime'], \
                                           '%Y-%m-%d %H:%M:%S.%f')
        
        # search file for data between two time points
        if (RawDatetime >= StartBinTime) and (RawDatetime < EndBinTime):
            # increase relevant counter
            if RawLine['RawPosition'] == 'T':
                count_T +=1
            elif RawLine['RawPosition'] == 'B':
                count_B +=1
            elif RawLine['RawPosition'] == 'C':
                count_M +=1

    # close open RawFile
    RawFile.close()

    ProcessedCPM_T = '{:.0f}'.format(count_T)
    ProcessedCPM_B = '{:.0f}'.format(count_B)
    ProcessedCPM_M = '{:.0f}'.format(count_M)

    # write to file
    ProcessedData.write(str(ProcessedTime))          # Data time date
    ProcessedData.write(",")                         # "," separator
    ProcessedData.write(str(ProcessedCPM_T))         # Top Sipm cpm
    ProcessedData.write(",")                         # "," separator
    ProcessedData.write(str(ProcessedCPM_B))         # Bottom Sipm cpm
    ProcessedData.write(",")                         # "," separator
    ProcessedData.write(str(ProcessedCPM_M))         # Muon cpm
    ProcessedData.write("\n")                        # new line


# close open ProcessedData file
ProcessedData.close()

# =============================================================================
# Message to log file at end of program

# print message to log file to say completed
print('ProcessDataCpmACM0.py    :', \
      dt.datetime.strftime(dt.datetime.now(), '%Y-%m-%d %H:%M:%S'), \
      ': Completed cpm ACM0 data processing for', \
      dt.datetime.strftime(dt.datetime.now() - dt.timedelta(1), '%Y-%m-%d'))


# =============================================================================
# END of program