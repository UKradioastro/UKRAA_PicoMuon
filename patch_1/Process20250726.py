#!/usr/bin/env python3

#imports
import datetime as dt
import csv
import os

# print message to log file to say started
print('ProcessDataDayACM0.py:',
      dt.datetime.strftime(dt.datetime.now(), '%Y-%m-%d %H:%M:%S'),
      ': Started ACM0 days % deviation data processing for 2025-07-26')

# Set file headers for data file structure
RawFieldNames    = ['RawDateTime',
                    'RawPosition',
                    'RawCount',
                    'RawADC',
                    'RawPicoTime',
                    'RawPicoDeadTime',
                    'RawPicoTemp',
                    'RawPicoPres',
                    'RawPicoName']

# Set path for data file structure

# raw data file source
RawDataFile   = "/home/pi/UKRAA_PicoMuon/data/raw/ACM0/2025/2025-07/2025-07-26.txt"

# Set file headers for data file structure
NeutronFieldNames    = ['NeutronDateTime',
                        'NeutronPressure',
                        'Uncorrected',
                        'PressureCorrected',
                        'EfficiencyCorrected']

# Neutron data file source
NeutronDataFile   = "/home/pi/UKRAA_PicoMuon/data/NMDB/neutrons/2025/2025-07/2025-07-26.txt"

# Processed data path
ProcessedPath = "/home/pi/UKRAA_PicoMuon/data/processed/day/ACM0/2025/2025-07"

# check if the specific path exists
pathExists = os.path.exists(ProcessedPath)
if not pathExists:
    # create directory structure
    os.makedirs(ProcessedPath)
    print('ProcessDataDayACM0.py       :',
          dt.datetime.strftime(dt.datetime.now(), '%Y-%m-%d %H:%M:%S'),
          ': New ACM0 day directory created :',
          ProcessedPath)

# Processed data file name
ProcessedDataFile = "/home/pi/UKRAA_PicoMuon/data/processed/day/ACM0/2025/2025-07/2025-07-26.txt"

# =============================================================================
# Main program

StartTime_str = "2025-07-26 00:00:00.000000"

StartTime_datetime = dt.datetime.strptime(StartTime_str, '%Y-%m-%d %H:%M:%S.%f')

EndTime_str = "2025-07-26 23:59:59.999999"

EndTime_datetime = dt.datetime.strptime(EndTime_str, '%Y-%m-%d %H:%M:%S.%f')

# define what the time change will be
minute = dt.timedelta(
    days         =  0,
    seconds      =  0,
    microseconds =  0,
    milliseconds =  0,
    minutes      =  5,
    hours        =  0,
    weeks        =  0)

# set up variable to use in loop
ProcessedTime = StartTime_datetime - minute

# number of 5 minutes in a day
n = 288

# open file to store data in and append to end
ProcessedData = open(file=ProcessedDataFile,
                     mode='a',
                     encoding='UTF-8')

for i in range(1, n+1):
    # add a timedelta to each time value from 00:00:00 to 23:59:00
    ProcessedTime = ProcessedTime + minute
    
    StartBinTime = ProcessedTime

    EndBinTime = StartBinTime + minute

    # using csv.DictReader
    RawFile = open(file=RawDataFile,
                   mode='r',
                   encoding='UTF-8')
    
    RawCSV_reader = csv.DictReader(RawFile,
                                   RawFieldNames)

    # set counters to zero
    count_T     = 0
    count_B     = 0
    count_M     = 0
    temperature = 0.0
    pressure    = 0.0
    count_N     = 0.0

    for RawLine in RawCSV_reader:
        # try to get raw data after start StartBinTime
        # convert string to dt.datetime.datetime format
        RawDatetime = dt.datetime.strptime(RawLine['RawDateTime'],
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

    # close open RawFile
    RawFile.close()

    # check if neutron data file exists
    if os.path.exists(NeutronDataFile):

        # using csv.DictReader
        NeutronFile = open(file=NeutronDataFile,
                           mode='r',
                           encoding='UTF-8')
        
        NeutronCSV_reader = csv.DictReader(NeutronFile,
                                           NeutronFieldNames)

        for NeutronLine in NeutronCSV_reader:
            # try to get neutron data after start StartBinTime
            # convert string to dt.datetime.datetime format
            NeutronDatetime = dt.datetime.strptime(NeutronLine['NeutronDateTime'], 
                                            '%Y-%m-%d %H:%M:%S')
            
            # search file for data between two time points
            if (NeutronDatetime >= StartBinTime) and (NeutronDatetime < EndBinTime):
                # increase relevant counter
                count_N = count_N + float(NeutronLine['EfficiencyCorrected'])
      
        # close open NeutronFile
        NeutronFile.close()

    # check if there is some top counts data
    if (count_T != 0):
        ProcessedCPM_T = '{:.0f}'.format(count_T)
    else:
        ProcessedCPM_T = float('nan')
    # check if there is some bottom counts data
    if (count_B != 0):
        ProcessedCPM_B = '{:.0f}'.format(count_B)
    else:
        ProcessedCPM_B = float('nan')
    # check if there is some coincidence counts data
    if (count_M != 0):
        ProcessedCPM_M = '{:.0f}'.format(count_M)
    else:
        ProcessedCPM_M = float('nan')

    # check if there is some count data
    if ((count_T + count_B + count_M) != 0):
        ProcessedTemp  = '{:.1f}'.format(temperature /(count_T + count_B + count_M))
        ProcessedPres  = '{:.1f}'.format(pressure /(count_T + count_B + count_M))
    else:
        ProcessedTemp = float('nan')
        ProcessedPres = float('nan')

    # check if there is some neutron counts data
    if (count_N > 400):
        ProcessedCPM_N = '{:.3f}'.format(count_N)
    else:
        ProcessedCPM_N = float('nan')

    # write to file
    ProcessedData.write(str(ProcessedTime))          # Data time date
    ProcessedData.write(",")                         # "," separator
    ProcessedData.write(str(ProcessedCPM_T))         # Top detector count over 5 minutes
    ProcessedData.write(",")                         # "," separator
    ProcessedData.write(str(ProcessedCPM_B))         # Bottom detector count over 5 minutes
    ProcessedData.write(",")                         # "," separator
    ProcessedData.write(str(ProcessedCPM_M))         # Muon count over 5 minutes
    ProcessedData.write(",")                         # "," separator
    ProcessedData.write(str(ProcessedTemp))          # Detector temperature over 5 minutes
    ProcessedData.write(",")                         # "," separator
    ProcessedData.write(str(ProcessedPres))          # Detector pressure over 5 minutes
    ProcessedData.write(",")                         # "," separator
    ProcessedData.write(str(ProcessedCPM_N))         # Neutron count over 5 minutes
    ProcessedData.write("\n")                        # new line

# close open ProcessedData file
ProcessedData.close()

# =============================================================================
# Message to log file at end of program

# print message to log file to say completed
print('ProcessDataDayACM0.py:',
      dt.datetime.strftime(dt.datetime.now(), '%Y-%m-%d %H:%M:%S'),
      ': Completed ACM0 days % deviation data processing for 2025-07-26')
      

# =============================================================================
# END of program