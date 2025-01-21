#!/usr/bin/env python3

#imports
from datetime import datetime, timedelta
import csv
import os

# print message to log file to say started
print('Started processing ACM0 day data, for ', \
      datetime.strftime(datetime.now() - timedelta(1), '%Y-%m-%d'), \
      'on', datetime.strftime(datetime.now(), '%Y-%m-%d'), \
      'at',datetime.strftime(datetime.now(), '%H:%M:%S'))

# Set file headers for data file structure
RawFieldNames    = ['RawDateTime',\
                    'RawPosition', \
                    'RawCount', \
                    'RawADC', \
                    'RawPicoTime', \
                    'RawPicoDeadTime', \
                    'RawPicoTemp', \
                    'RawPicoPres', \
                    'RawPicoName']

# Set path for data file structure

# raw data file source
RawDataFile   = "/home/pi/UKRAA_PicoMuon/data/raw/ACM0/" \
                 + datetime.strftime(datetime.now() - timedelta(1), '%Y') \
                 + "/" \
                 + datetime.strftime(datetime.now() - timedelta(1), '%Y-%m') \
                 + "/" \
                 + datetime.strftime(datetime.now() - timedelta(1), '%Y-%m-%d') \
                 + ".txt"

# Set file headers for data file structure
NeutronFieldNames    = ['NeutronDateTime', \
                        'NeutronPressure', \
                        'Uncorrected', \
                        'PressureCorrected', \
                        'EfficiencyCorrected']

# Neutron data file source
NeutronDataFile   = "/home/pi/UKRAA_PicoMuon/data/neutrons/" \
                 + datetime.strftime(datetime.now() - timedelta(1), '%Y') \
                 + "/" \
                 + datetime.strftime(datetime.now() - timedelta(1), '%Y-%m') \
                 + "/" \
                 + datetime.strftime(datetime.now() - timedelta(1), '%Y-%m-%d') \
                 + ".txt"

# Processed data path
ProcessedPath = '/home/pi/UKRAA_PicoMuon/data/processed/day/ACM0/'\
                + datetime.strftime(datetime.now() - timedelta(1), '%Y') \
                + "/" \
                + datetime.strftime(datetime.now() - timedelta(1), '%Y-%m')

# check if the specific path exists
pathExists = os.path.exists(ProcessedPath)
if not pathExists:
    # create directory structure
    os.makedirs(ProcessedPath)

# Processed data file name
ProcessedDataFile = "/home/pi/UKRAA_PicoMuon/data/processed/day/ACM0/" \
                     + datetime.strftime(datetime.now() - timedelta(1), '%Y') \
                     + "/" \
                     + datetime.strftime(datetime.now() - timedelta(1), '%Y-%m') \
                     + "/" \
                     + datetime.strftime(datetime.now() - timedelta(1), '%Y-%m-%d') \
                     + ".txt"

# =============================================================================
# Main program

StartTime_str = datetime.strftime(datetime.now() - timedelta(1), '%Y-%m-%d') \
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
    minutes      =  5,
    hours        =  0,
    weeks        =  0)
# uncomment next lines to print the response
print('Value of variable (minute): ', minute)

# set up variable to use in loop
ProcessedTime = StartTime_datetime - minute

# number of 5 minutes in a day
n = 288

# open file to store data in and append to end
ProcessedData = open(file=ProcessedDataFile, mode='a', encoding='UTF-8')

for i in range(1, n+1):
    # add a minute to each time value from 00:00:00 to 23:59:00
    ProcessedTime = ProcessedTime + minute
    
    StartBinTime = ProcessedTime

    EndBinTime = StartBinTime + minute

    # using csv.DictReader
    RawFile = open(file=RawDataFile, mode='r', encoding='UTF-8')
    RawCSV_reader = csv.DictReader(RawFile,RawFieldNames)

    # using csv.DictReader
    NeutronFile = open(file=NeutronDataFile, mode='r', encoding='UTF-8')
    NeutronCSV_reader = csv.DictReader(NeutronFile,NeutronFieldNames)

    # set counters to zero
    count_T     = 0
    count_B     = 0
    count_M     = 0
    temperature = 0.0
    pressure    = 0.0
    count_N     = 0.0

    for RawLine in RawCSV_reader:
        # try to get raw data after start StartBinTime
        # convert string to datetime.datetime format
        RawDatetime = datetime.strptime(RawLine['RawDateTime'], 
                                        '%Y-%m-%d %H:%M:%S.%f')
        
        # search file for data between two time points
        if (RawDatetime >= StartBinTime) and (RawDatetime < EndBinTime):
            # increase relevant counter
            if RawLine['RawPosition'] == 'T':
                temperature = temperature + float(RawLine['RawPicoTemp'])
                pressure = pressure + float(RawLine['RawPicoPres'])
                count_T +=1
            elif RawLine['RawPosition'] == 'B':
                temperature = temperature + float(RawLine['RawPicoTemp'])
                pressure = pressure + float(RawLine['RawPicoPres'])
                count_B +=1
            elif RawLine['RawPosition'] == 'C':
                temperature = temperature + float(RawLine['RawPicoTemp'])
                pressure = pressure + float(RawLine['RawPicoPres'])
                count_M +=1

    for NeutronLine in NeutronCSV_reader:
        # try to get raw data after start StartBinTime
        # convert string to datetime.datetime format
        NeutronDatetime = datetime.strptime(NeutronLine['NeutronDateTime'], 
                                        '%Y-%m-%d %H:%M:%S')
        
        # search file for data between two time points
        if (NeutronDatetime >= StartBinTime) and (NeutronDatetime < EndBinTime):
            # increase relevant counter
            count_N = count_N + float(NeutronLine['EfficiencyCorrected'])
  

    ProcessedCPM_T = count_T
    ProcessedCPM_B = count_B
    ProcessedCPM_M = count_M
    ProcessedTemp  = temperature /(count_T + count_B + count_M)
    ProcessedPres  = pressure /(count_T + count_B + count_M)
    ProcessedCPM_N = count_N


    # write to file
    ProcessedData.write(str(ProcessedTime))          # Data time date
    ProcessedData.write(",")                         # "," separator
    ProcessedData.write(str(ProcessedCPM_T))         # Top detector count over 5 minutes
    ProcessedData.write(",")                         # "," separator
    ProcessedData.write(str(ProcessedCPM_B))         # Bottom detector count over 5 minutes
    ProcessedData.write(",")                         # "," separator
    ProcessedData.write(str(ProcessedCPM_M))         # Muon count over 5 minutes
    ProcessedData.write(",")                         # "," separator
    ProcessedData.write("%.1f" % (ProcessedTemp))    # Detector temperature over 5 minutes
    ProcessedData.write(",")                         # "," separator
    ProcessedData.write("%.1f" % (ProcessedPres))    # eeDetector pressure over 5 minutes
    ProcessedData.write(",")                         # "," separator
    ProcessedData.write("%.3f" % (ProcessedCPM_N))   # Neutron count over 5 minutes
    ProcessedData.write("\n")                        # new line

    # close open RawFile
    RawFile.close()

# close open ProcessedData file
ProcessedData.close()

# =============================================================================
# Message to log file at end of program

# print message to log file to say completed
print('Completed processing ACM0 day data for ', \
      datetime.strftime(datetime.now() - timedelta(1), '%Y-%m-%d'), \
      'on',datetime.strftime(datetime.now(), '%Y-%m-%d'), \
      'at',datetime.strftime(datetime.now(), '%H:%M:%S'))
      

# =============================================================================
# END of program