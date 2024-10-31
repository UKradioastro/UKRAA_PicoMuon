#!/usr/bin/env python3

from datetime import datetime, timedelta
import csv
import os

# print message to log file to say started
print('Started processing ACM0 muon adc data for', \
      datetime.strftime(datetime.now() - timedelta(1), '%Y-%m-%d'), \
      'on', datetime.strftime(datetime.now(), '%Y-%m-%d'), \
      'at',datetime.strftime(datetime.now(), '%H:%M:%S'))

# Set file headers for data file structure
RawFieldNames    = ['RawDateTime','RawPosition', 'RawCount', 'RawADC', \
                    'RawPicoTime', 'RawDeadTime', 'RawPicoTemp', 'RawPicoPres']

# Set path for data file structure

# raw data file source
RawDataFile   = "/home/pi/UKRAA_muons/data/raw/ACM0/" \
                 + datetime.strftime(datetime.now() - timedelta(1), '%Y') \
                 + "/" \
                 + datetime.strftime(datetime.now() - timedelta(1), '%Y-%m') \
                 + "/" \
                 + datetime.strftime(datetime.now() - timedelta(1), '%Y-%m-%d') \
                 + ".txt"

# Processed data path
ProcessedPath = '/home/pi/UKRAA_muons/data/processed/adc/ACM0/'\
                + datetime.strftime(datetime.now() - timedelta(1), '%Y') \
                + "/" \
                + datetime.strftime(datetime.now() - timedelta(1), '%Y-%m')

# check if the specific path exists
pathExists = os.path.exists(ProcessedPath)
if not pathExists:
    # create directory structure
    os.makedirs(ProcessedPath)

# Processed data file name
ProcessedDataFile = "/home/pi/UKRAA_muons/data/processed/adc/ACM0/" \
                     + datetime.strftime(datetime.now() - timedelta(1), '%Y') \
                     + "/" \
                     + datetime.strftime(datetime.now() - timedelta(1), '%Y-%m') \
                     + "/" \
                     + datetime.strftime(datetime.now() - timedelta(1), '%Y-%m-%d') \
                     + ".txt"

# =============================================================================
# Main program

# define what bin size will be
BinAdc = 1

# set up variable to use in loop
ProcessedAdc = -1

# number of adc values - 0 to 4095 (2^12)
n = 1024

# open file to store data in and append data
ProcessedData = open(file=ProcessedDataFile, mode='a', encoding='UTF-8')

for i in range(0, n):
    # add bin size to Adc value from 0 to 4095
    ProcessedAdc = ProcessedAdc + BinAdc
    
    StartBinAdc = ProcessedAdc

    EndBinAdc = StartBinAdc + BinAdc

    # using csv.DictReader
    RawFile = open(file=RawDataFile, mode='r', encoding='UTF-8')
    RawCSV_reader = csv.DictReader(RawFile,RawFieldNames)

    count_T = 0
    count_B = 0
    count_M = 0

    for RawLine in RawCSV_reader:
        # try to get raw data after start StartBinTime
        RawAdc = int(RawLine['RawADC'])
        
        # search file for data between two time points
        if (RawAdc >= StartBinAdc) and (RawAdc < EndBinAdc):
            # add counts to positions
            if RawLine['RawPosition'] == 'T':
                count_T +=1
            elif RawLine['RawPosition'] == 'B':
                count_B +=1
            elif RawLine['RawPosition'] == 'C':
                count_M +=1
            
    CountADC_T = count_T
    CountADC_B = count_B
    CountADC_M = count_M
   
    # write to file
    ProcessedData.write(str(ProcessedAdc))         # Data time date
    ProcessedData.write(",")                       # "," separator
    ProcessedData.write(str(CountADC_T))           # top SiPM ADC values
    ProcessedData.write(",")                       # "," separator
    ProcessedData.write(str(CountADC_B))           # bottom ADC value
    ProcessedData.write(",")                       # "," separator
    ProcessedData.write(str(CountADC_M))           # muon ADC value
    ProcessedData.write("\n")                      # new line

    # close open RawFile
    RawFile.close()

# close open ProcessedData file
ProcessedData.close()

# print message to log file to say completed
print('Completed processing ACM0 muon adc data for ', \
      datetime.strftime(datetime.now() - timedelta(1), '%Y-%m-%d'), \
      'on',datetime.strftime(datetime.now(), '%Y-%m-%d'), \
      'at',datetime.strftime(datetime.now(), '%H:%M:%S'))

# ==========================================================================================
# END of program