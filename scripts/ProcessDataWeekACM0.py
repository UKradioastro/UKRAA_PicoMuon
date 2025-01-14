#!/usr/bin/env python3

#imports
from datetime import datetime, timedelta
import csv
import os
import shutil

# print message to log file to say started
print('Started processing ACM0 week data, from ', \
      datetime.strftime(datetime.now() - timedelta(7), '%Y-%m-%d'), \
      'to', datetime.strftime(datetime.now() - timedelta(1), '%Y-%m-%d'), \
      'on', datetime.strftime(datetime.now(), '%Y-%m-%d'), \
      'at', datetime.strftime(datetime.now(), '%H:%M:%S'))


# Set path for data file structure

# raw data file source
for i in range(1, 8):
    globals()['RawDataFile%s' % i] = '/home/pi/UKRAA_muons/data/processed/day/ACM0/' \
                                     + datetime.strftime(datetime.now() - timedelta(i), '%Y') \
                                     + '/' \
                                     + datetime.strftime(datetime.now() - timedelta(i), '%Y-%m') \
                                     + '/' \
                                     + datetime.strftime(datetime.now() - timedelta(i), '%Y-%m-%d') \
                                     + '.txt'
 

# Set file headers for data file structure
WeekFieldNames    = ['DateTime', \
                     'Position_T', \
                     'Position_B', \
                     'Position_M', \
                     'temperature', \
                     'pressure', \
                     'neutrons']


# create weeks worth of data
WeekPath = '/home/pi/UKRAA_muons/data/processed/week/ACM0/' \
           + datetime.strftime(datetime.now() - timedelta(1), '%Y') \
           + "/" \
           + datetime.strftime(datetime.now() - timedelta(1), '%Y-%m')

# check if the specific path exists
pathExists = os.path.exists(WeekPath)
if not pathExists:
    # create directory structure
    os.makedirs(WeekPath)

# week data file name
WeekDataFile = '/home/pi/UKRAA_muons/data/processed/week/ACM0/' \
               + datetime.strftime(datetime.now() - timedelta(1), '%Y') \
               + "/" \
               + datetime.strftime(datetime.now() - timedelta(1), '%Y-%m') \
               + "/temp.txt"

# merge day data to make week data file
with open(WeekDataFile,'wb') as wfd:
    for f in [RawDataFile7,
              RawDataFile6,
              RawDataFile5,
              RawDataFile4,
              RawDataFile3,
              RawDataFile2,
              RawDataFile1]:
        with open(f,'rb') as fd:
            shutil.copyfileobj(fd, wfd)

# Processed data path
ProcessedPath = '/home/pi/UKRAA_muons/data/processed/week/ACM0/'\
                + datetime.strftime(datetime.now() - timedelta(1), '%Y') \
                + "/" \
                + datetime.strftime(datetime.now() - timedelta(1), '%Y-%m')

# check if the specific path exists
pathExists = os.path.exists(ProcessedPath)
if not pathExists:
    # create directory structure
    os.makedirs(ProcessedPath)

# Processed data file name
ProcessedDataFile = "/home/pi/UKRAA_muons/data/processed/week/ACM0/" \
                     + datetime.strftime(datetime.now() - timedelta(1), '%Y') \
                     + "/" \
                     + datetime.strftime(datetime.now() - timedelta(1), '%Y-%m') \
                     + "/" \
                     + datetime.strftime(datetime.now() - timedelta(1), '%Y-%m-%d') \
                     + ".txt"

# =============================================================================
# Main program

StartTime_str = datetime.strftime(datetime.now() - timedelta(7), '%Y-%m-%d') \
                + ' 00:00:00.000000'

StartTime_datetime = datetime.strptime(StartTime_str, '%Y-%m-%d %H:%M:%S.%f')
# uncomment next lines to print the response
print('Value of variable (StartTime_datetime): ',StartTime_datetime)

EndTime_str = datetime.strftime(datetime.now() - timedelta(1), '%Y-%m-%d') \
              + ' 23:59:59.999999'

EndTime_datetime = datetime.strptime(EndTime_str, '%Y-%m-%d %H:%M:%S.%f')
# uncomment next lines to print the response
print('Value of variable (EndTime_datetime): ',EndTime_datetime)

# define what the time change will be
minute = timedelta(
    days         =  0,
    seconds      =  0,
    microseconds =  0,
    milliseconds =  0,
    minutes      = 10,
    hours        =  0,
    weeks        =  0)
# uncomment next lines to print the response
print('Value of variable (minute): ', minute)

# set up variable to use in loop
ProcessedTime = StartTime_datetime - minute

# number of 10 minutes in 7 days
n = 1008

# open file to store data in and append to end
ProcessedData = open(file=ProcessedDataFile, mode='a', encoding='UTF-8')

for i in range(1, n + 1):
    # add a minute to each time value from 00:00:00 to 23:59:00
    ProcessedTime = ProcessedTime + minute
    
    StartBinTime = ProcessedTime

    EndBinTime = StartBinTime + minute

    # using csv.DictReader
    WeekFile = open(file=WeekDataFile, mode='r', encoding='UTF-8')
    WeekCSV_reader = csv.DictReader(WeekFile,WeekFieldNames)

    # set counters to zero
    count_T     = 0
    count_B     = 0
    count_M     = 0
    temperature = 0.0
    pressure    = 0.0
    count_N     = 0.0

    for WeekLine in WeekCSV_reader:
        # try to get raw data after start StartBinTime
        # convert string to datetime.datetime format
        WeekDatetime = datetime.strptime(WeekLine['DateTime'], '%Y-%m-%d %H:%M:%S')
        
        # search file for data between two time points
        if (WeekDatetime >= StartBinTime) and (WeekDatetime < EndBinTime):
            # increase relevant counter
            count_T = count_T + int(WeekLine['Position_T'])
            count_B = count_B + int(WeekLine['Position_B'])
            count_M = count_M + int(WeekLine['Position_M'])
            temperature = temperature + float(WeekLine['temperature'])
            pressure = pressure + float(WeekLine['pressure'])
            count_N = count_N + float(WeekLine['neutrons'])


    ProcessedCPM_T = count_T
    ProcessedCPM_B = count_B
    ProcessedCPM_M = count_M
    ProcessedTemp  = temperature / 2.0
    ProcessedPres  = pressure / 2.0
    ProcessedCPM_N = count_N

    # write to file
    ProcessedData.write(str(ProcessedTime))          # Data time date
    ProcessedData.write(",")                         # "," separator
    ProcessedData.write(str(ProcessedCPM_T))         # Top detector count over 10 minutes
    ProcessedData.write(",")                         # "," separator
    ProcessedData.write(str(ProcessedCPM_B))         # Bottom detector count over 10 minutes
    ProcessedData.write(",")                         # "," separator
    ProcessedData.write(str(ProcessedCPM_M))         # Muon count over 10 minutes
    ProcessedData.write(",")                         # "," separator
    ProcessedData.write("%.1f" % (ProcessedTemp))    # Detector temperature over 10 minutes
    ProcessedData.write(",")                         # "," separator
    ProcessedData.write("%.1f" % (ProcessedPres))    # Detector pressure over 10 minutes
    ProcessedData.write(",")                         # "," separator
    ProcessedData.write("%.3f" % (ProcessedCPM_N))   # Neutron count over 10 minutes
    ProcessedData.write("\n")                        # new line

    # close open RawFile
    WeekFile.close()

# close open ProcessedData file
ProcessedData.close()

# =============================================================================
# Message to log file at end of program

# print message to log file to say completed
print('Completed processing weeks worth of ACM0 muon count data from ', \
      datetime.strftime(datetime.now() - timedelta(7), '%Y-%m-%d'), \
      'to', datetime.strftime(datetime.now() - timedelta(1), '%Y-%m-%d'), \
      'on', datetime.strftime(datetime.now(), '%Y-%m-%d'), \
      'at', datetime.strftime(datetime.now(), '%H:%M:%S'))

# =============================================================================
# END of program