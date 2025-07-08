#!/usr/bin/env python3

import datetime as dt
import csv
import os

# print message to log file to say started
print('ProcessDataAdcACM0.py       :',
      dt.datetime.strftime(dt.datetime.now(), '%Y-%m-%d %H:%M:%S'),
      ': Started ADC ACM0 data processing for',
      dt.datetime.strftime(dt.datetime.now() - dt.timedelta(1), '%Y-%m-%d'))

# Set file headers for data file structure
RawFieldNames    = ['RawDateTime',
                    'RawPosition',
                    'RawCount',
                    'RawADC',
                    'RawPicoTime',
                    'RawDeadTime',
                    'RawPicoTemp',
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
ProcessedPath = '/home/pi/UKRAA_PicoMuon/data/processed/adc/ACM0/'\
                + dt.datetime.strftime(dt.datetime.now() - dt.timedelta(1), '%Y') \
                + "/" \
                + dt.datetime.strftime(dt.datetime.now() - dt.timedelta(1), '%Y-%m')

# check if the specific path exists
pathExists = os.path.exists(ProcessedPath)
if not pathExists:
    # create directory structure
    os.makedirs(ProcessedPath)
    print('ProcessDataAdcACM0.py       :',
          dt.datetime.strftime(dt.datetime.now(), '%Y-%m-%d %H:%M:%S'),
          ': New ACM0 ADC directory created :',
          ProcessedPath)

# Processed data file name
ProcessedDataFile = "/home/pi/UKRAA_PicoMuon/data/processed/adc/ACM0/" \
                     + dt.datetime.strftime(dt.datetime.now() - dt.timedelta(1), '%Y') \
                     + "/" \
                     + dt.datetime.strftime(dt.datetime.now() - dt.timedelta(1), '%Y-%m') \
                     + "/" \
                     + dt.datetime.strftime(dt.datetime.now() - dt.timedelta(1), '%Y-%m-%d') \
                     + ".txt"

# =============================================================================
# Main program

# define what bin size will be
BinAdc = 1

# set up variable to use in loop
ProcessedAdc = -1

# number of adc values - 0 to 1023 (2^10)
n = 1024

# open file to store data in and append data
ProcessedData = open(file=ProcessedDataFile,
                     mode='a',
                     encoding='UTF-8')

for i in range(0, n):
    # add bin size to Adc value from 0 to 1023
    ProcessedAdc = ProcessedAdc + BinAdc
    
    StartBinAdc = ProcessedAdc

    EndBinAdc = StartBinAdc + BinAdc

    # using csv.DictReader
    RawFile = open(file=RawDataFile,
                   mode='r',
                   encoding='UTF-8')
    
    RawCSV_reader = csv.DictReader(RawFile,
                                   RawFieldNames)

    count_T = 0
    count_B = 0
    count_M = 0

    for RawLine in RawCSV_reader:
        # try to get raw data for ADC value
        RawAdc = int(RawLine['RawADC'])
        
        # search file for data between two ADC points
        if (RawAdc >= StartBinAdc) and (RawAdc < EndBinAdc):
            # add counts to positions
            if RawLine['RawPosition'] == 'T':
                count_T +=1
            elif RawLine['RawPosition'] == 'B':
                count_B +=1
            elif RawLine['RawPosition'] == 'C':
                count_M +=1
    
    # close open RawFile
    RawFile.close()

    CountADC_T = '{:.0f}'.format(count_T)
    CountADC_B = '{:.0f}'.format(count_B)
    CountADC_M = '{:.0f}'.format(count_M)

    # write to file
    ProcessedData.write(str(ProcessedAdc))         # ADC value
    ProcessedData.write(",")                       # "," separator
    ProcessedData.write(str(CountADC_T))           # top SiPM ADC count value
    ProcessedData.write(",")                       # "," separator
    ProcessedData.write(str(CountADC_B))           # bottom ADC count value
    ProcessedData.write(",")                       # "," separator
    ProcessedData.write(str(CountADC_M))           # muon ADC count value
    ProcessedData.write("\n")                      # new line

# close open ProcessedData file
ProcessedData.close()

# =============================================================================
# Message to log file at end of program

# print message to log file to say completed
print('ProcessDataAdcACM0.py       :',
      dt.datetime.strftime(dt.datetime.now(), '%Y-%m-%d %H:%M:%S'),
      ': Completed ADC ACM0 data processing for',
      dt.datetime.strftime(dt.datetime.now() - dt.timedelta(1), '%Y-%m-%d'))
      

# ==========================================================================================
# END of program